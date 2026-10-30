package main

import (
	"context"
	"encoding/json"
	"errors"
	"sync/atomic"
	"time"

	"golang.org/x/sync/singleflight"
)

// The home route is short-lived data (upcoming events + recommendations), so it
// gets a separate, much shorter policy than the demo detail cache: no batch, no
// 24h lifetime. There are only three possible responses (fi, en, sv), so memory
// is fixed and attackers cannot grow it or bypass it with different parameters.
const (
	homeSoftTTL     = 60 * time.Second // after this: serve stale, refresh in background
	homeHardTTL     = 15 * time.Minute // after this: stale copy is no longer served
	homeLoadTimeout = 3 * time.Second
)

var homeLangs = [3]string{"fi", "en", "sv"}

type homeJSONStore interface {
	FindHomeJSON(ctx context.Context, lang string) ([]byte, error)
}

type homeValue struct {
	data       []byte // final JSON, newline-terminated
	hardExpiry int64  // unix nanos
}

type homeSlot struct {
	cur          atomic.Pointer[homeValue]
	refreshAfter atomic.Int64 // unix nanos; pushed out after failures (backoff)
	refreshing   atomic.Bool
	failures     atomic.Int32
}

type homeCache struct {
	source homeStore
	base   context.Context
	group  singleflight.Group
	slots  [3]homeSlot
}

func newHomeCache(source homeStore, base context.Context) *homeCache {
	return &homeCache{source: source, base: base}
}

func homeSlotIndex(lang string) int {
	switch lang {
	case "en":
		return 1
	case "sv":
		return 2
	}
	return 0
}

// Get returns the JSON for lang. At most three DB loads (one per language) can
// ever be in flight, however much traffic arrives.
func (h *homeCache) Get(ctx context.Context, lang string) ([]byte, error) {
	idx := homeSlotIndex(lang)
	slot := &h.slots[idx]
	now := time.Now().UnixNano()

	if v := slot.cur.Load(); v != nil && now < v.hardExpiry {
		if now >= slot.refreshAfter.Load() {
			h.refreshAsync(idx)
		}
		return v.data, nil
	}

	select {
	case r := <-h.load(idx):
		if r.Err != nil {
			return nil, r.Err
		}
		return r.Val.([]byte), nil
	case <-ctx.Done():
		return nil, ctx.Err() // only this caller gives up; the load still fills the cache
	}
}

func (h *homeCache) load(idx int) <-chan singleflight.Result {
	lang := homeLangs[idx] // canonical value only: arbitrary input never reaches the source
	slot := &h.slots[idx]
	return h.group.DoChan(lang, func() (any, error) {
		ctx, cancel := context.WithTimeout(h.base, homeLoadTimeout)
		defer cancel()
		result, err := h.source.FindHome(ctx, lang)
		if err != nil {
			return nil, err
		}
		data, err := json.Marshal(result)
		if err != nil {
			return nil, err
		}
		data = append(data, '\n')
		now := time.Now()
		slot.cur.Store(&homeValue{data: data, hardExpiry: now.Add(homeHardTTL).UnixNano()})
		slot.refreshAfter.Store(now.Add(jitter(homeSoftTTL)).UnixNano())
		slot.failures.Store(0)
		return data, nil
	})
}

// refreshAsync refreshes one language in the background. On failure it backs
// off (10s, 20s, ... capped at 2m) while the stale copy keeps serving.
func (h *homeCache) refreshAsync(idx int) {
	slot := &h.slots[idx]
	if !slot.refreshing.CompareAndSwap(false, true) {
		return
	}
	go func() {
		defer slot.refreshing.Store(false)
		if r := <-h.load(idx); r.Err != nil {
			n := min(slot.failures.Add(1), 5)
			delay := min(5*time.Second<<n, 2*time.Minute)
			slot.refreshAfter.Store(time.Now().Add(delay).UnixNano())
		}
	}()
}

// Warm loads all three languages so the first real requests are cache hits.
func (h *homeCache) Warm(ctx context.Context) {
	for _, lang := range homeLangs {
		if ctx.Err() != nil {
			return
		}
		_, _ = h.Get(ctx, lang)
	}
}

// FindHomeJSON makes cachedDetailStore satisfy homeJSONStore.
func (s *cachedDetailStore) FindHomeJSON(ctx context.Context, lang string) ([]byte, error) {
	if s.home == nil {
		return nil, errors.New("home store unavailable")
	}
	return s.home.Get(ctx, lang)
}
