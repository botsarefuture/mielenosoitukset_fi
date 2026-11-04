package main

import (
	"container/list"
	"context"
	"encoding/json"
	"errors"
	"sync"
	"time"

	"golang.org/x/sync/singleflight"
)

const (
	listingFreshTTL = 30 * time.Second
	listingHardTTL  = 120 * time.Second
	listingMaxBytes = 8 << 20
	listingMaxItems = 128
)

type listingEntry struct {
	key        string
	data       []byte
	loaded     time.Time
	retryAfter time.Time
}

type listingResult struct {
	data  []byte
	stale bool
}

type listingCache struct {
	source listingStore
	base   context.Context
	now    func() time.Time
	mu     sync.Mutex
	items  map[string]*list.Element
	order  *list.List
	bytes  int
	group  singleflight.Group
	sem    chan struct{}
	queue  chan struct{}
}

func newListingCache(source listingStore, base context.Context) *listingCache {
	return &listingCache{source: source, base: base, now: time.Now,
		items: map[string]*list.Element{}, order: list.New(),
		sem: make(chan struct{}, 4), queue: make(chan struct{}, 16)}
}

func (c *listingCache) remove(element *list.Element) {
	entry := element.Value.(*listingEntry)
	delete(c.items, entry.key)
	c.bytes -= len(entry.key) + len(entry.data)
	c.order.Remove(element)
}

func (c *listingCache) read(key string) (listingResult, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	element := c.items[key]
	if element == nil {
		return listingResult{}, false
	}
	entry := element.Value.(*listingEntry)
	now := c.now()
	if !now.Before(entry.loaded.Add(listingHardTTL)) {
		c.remove(element)
		return listingResult{}, false
	}
	c.order.MoveToFront(element)
	stale := !now.Before(entry.loaded.Add(listingFreshTTL))
	return listingResult{entry.data, stale}, !stale || now.Before(entry.retryAfter)
}

func (c *listingCache) staleAfterFailure(key string) (listingResult, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if element := c.items[key]; element != nil {
		entry := element.Value.(*listingEntry)
		if now := c.now(); now.Before(entry.loaded.Add(listingHardTTL)) {
			entry.retryAfter = now.Add(5 * time.Second)
			return listingResult{entry.data, true}, true
		}
		c.remove(element)
	}
	return listingResult{}, false
}

func (c *listingCache) put(key string, data []byte) {
	// Large pages can be returned but cannot evict the whole useful working set.
	if len(key)+len(data) > 256<<10 {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if old := c.items[key]; old != nil {
		c.remove(old)
	}
	c.items[key] = c.order.PushFront(&listingEntry{key: key, data: data, loaded: c.now()})
	c.bytes += len(key) + len(data)
	for len(c.items) > listingMaxItems || c.bytes > listingMaxBytes {
		c.remove(c.order.Back())
	}
}

func (c *listingCache) get(ctx context.Context, query listingQuery) ([]byte, bool, error) {
	serialized, _ := json.Marshal(query)
	key := string(serialized)
	if result, ready := c.read(key); ready {
		return result.data, result.stale, nil
	}
	result := c.group.DoChan(key, func() (any, error) {
		if result, ready := c.read(key); ready {
			return result, nil
		}
		// Bound both running DB reads and distinct queued loads under cache misses.
		select {
		case c.queue <- struct{}{}:
			defer func() { <-c.queue }()
		default:
			if stale, ok := c.staleAfterFailure(key); ok {
				return stale, nil
			}
			return nil, errors.New("listing queue full")
		}
		loadCtx, cancel := context.WithTimeout(c.base, 3*time.Second)
		defer cancel()
		select {
		case c.sem <- struct{}{}:
			defer func() { <-c.sem }()
		case <-loadCtx.Done():
			if stale, ok := c.staleAfterFailure(key); ok {
				return stale, nil
			}
			return nil, loadCtx.Err()
		}
		page, err := c.source.FindListing(loadCtx, query)
		if err != nil {
			if stale, ok := c.staleAfterFailure(key); ok {
				return stale, nil
			}
			return nil, err
		}
		data, err := json.Marshal(page)
		if err != nil {
			return nil, err
		}
		data = append(data, '\n')
		c.put(key, data)
		return listingResult{data: data}, nil
	})
	select {
	case loaded := <-result:
		if loaded.Err != nil {
			return nil, false, loaded.Err
		}
		value := loaded.Val.(listingResult)
		return value.data, value.stale, nil
	case <-ctx.Done():
		return nil, false, ctx.Err()
	}
}

func (s *cachedDetailStore) FindListingJSON(ctx context.Context, query listingQuery) ([]byte, bool, error) {
	if s.listing == nil {
		return nil, false, errors.New("listing store unavailable")
	}
	return s.listing.get(ctx, query)
}
