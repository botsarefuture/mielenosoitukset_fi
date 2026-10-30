package main

import (
	"container/list"
	"context"
	"encoding/binary"
	"errors"
	"math/rand/v2"
	"sync"
	"sync/atomic"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"golang.org/x/sync/singleflight"
	"golang.org/x/time/rate"
)

// isNotPublic reports whether err is a definitive "doesn't exist / not public"
// answer from the source. Only these are negatively cached; timeouts and other
// transient errors never are. ADAPT THIS to whatever your Store returns.
var isNotPublic = func(err error) bool { return errors.Is(err, mongo.ErrNoDocuments) }

const (
	detailShards  = 32 // power of two; must match the shift in shardFor
	entryOverhead = 160
)

type detailCacheConfig struct {
	SoftTTL              time.Duration // after this, serve stale and refresh in background (default 15m)
	HardTTL              time.Duration // after this, entry is unusable (default 24h)
	NegativeTTL          time.Duration // not-found / non-public results (default 60s)
	MaxBytes             int64         // total memory budget for cached documents (default 128 MiB)
	MaxEntryBytes        int           // larger documents are served but not cached (default 256 KiB)
	MaxConcurrentLoads   int           // max simultaneous DB loads across all keys (default 32)
	LoadTimeout          time.Duration // per-load timeout, including time queued for a slot (default 5s)
	RefreshBackoffMax    time.Duration // cap for retry delay after failed refreshes (default 5m)
	BatchInterval        time.Duration // how often the batch version check runs (default 15m)
	UnknownLookupsPerSec float64       // global DB-lookup budget for IDs outside the snapshot (default 5)
}

func (c *detailCacheConfig) withDefaults() {
	if c.SoftTTL <= 0 {
		c.SoftTTL = 15 * time.Minute
	}
	if c.HardTTL <= 0 {
		c.HardTTL = 24 * time.Hour
	}
	if c.NegativeTTL <= 0 {
		c.NegativeTTL = 60 * time.Second
	}
	if c.MaxBytes <= 0 {
		c.MaxBytes = 128 << 20
	}
	if c.MaxEntryBytes <= 0 {
		c.MaxEntryBytes = 256 << 10
	}
	if c.MaxConcurrentLoads <= 0 {
		c.MaxConcurrentLoads = 32
	}
	if c.LoadTimeout <= 0 {
		c.LoadTimeout = 5 * time.Second
	}
	if c.RefreshBackoffMax <= 0 {
		c.RefreshBackoffMax = 5 * time.Minute
	}
	if c.BatchInterval <= 0 {
		c.BatchInterval = 15 * time.Minute
	}
	if c.UnknownLookupsPerSec <= 0 {
		c.UnknownLookupsPerSec = 5
	}
}

type detailCacheStats struct {
	Hits           uint64 // served from cache (includes stale)
	StaleHits      uint64 // subset of Hits served past the soft TTL
	NegativeHits   uint64 // not-found answered from cache
	Misses         uint64 // request had to wait for a load
	Loads          uint64 // actual DB queries issued
	LoadErrors     uint64 // DB queries that failed (excluding not-found)
	Oversize       uint64 // documents too large to cache (every request re-queries!)
	UnknownDropped uint64 // unknown-ID lookups rejected by the budget, with zero DB work
}

type detailEntry struct {
	id         bson.ObjectID
	data       bson.Raw // immutable BSON; nil for negative entries
	err        error    // non-nil for negative entries
	size       int64
	hardExpiry atomic.Int64 // unix nanos; the batch extends it for unchanged entries
	version    int64        // source version (e.g. updatedAt) from the last batch; 0 = unknown

	softExpiry atomic.Int64 // unix nanos; pushed forward after failed refreshes
	refreshing atomic.Bool
	failures   atomic.Int32
	visited    atomic.Bool // second-chance bit, set on read

	// Final JSON per language slot (0=default, 1=fi, 2=en, 3=sv), rendered at most
	// once per entry. A refresh replaces the whole entry, which resets these.
	rendered [4]atomic.Pointer[[]byte]

	elem *list.Element // guarded by shard lock
}

type detailShard struct {
	mu       sync.RWMutex
	items    map[bson.ObjectID]*detailEntry
	order    *list.List // front = eviction candidate
	bytes    int64
	maxBytes int64
}

// get takes only a read lock; recency is tracked with an atomic bit instead of
// reordering a list, so concurrent hits on a shard never serialize.
func (sh *detailShard) get(id bson.ObjectID) *detailEntry {
	sh.mu.RLock()
	e := sh.items[id]
	sh.mu.RUnlock()
	if e != nil && !e.visited.Load() {
		e.visited.Store(true)
	}
	return e
}

func (sh *detailShard) put(e *detailEntry) {
	sh.mu.Lock()
	defer sh.mu.Unlock()
	if old := sh.items[e.id]; old != nil {
		sh.removeLocked(old)
	}
	e.elem = sh.order.PushBack(e)
	sh.items[e.id] = e
	sh.bytes += e.size
	// Second-chance (CLOCK-style) eviction: recently read entries survive one pass.
	for sh.bytes > sh.maxBytes && sh.order.Len() > 1 {
		front := sh.order.Front()
		victim := front.Value.(*detailEntry)
		if victim == e || victim.visited.Swap(false) {
			sh.order.MoveToBack(front)
			continue
		}
		sh.removeLocked(victim)
	}
}

func (sh *detailShard) remove(id bson.ObjectID) {
	sh.mu.Lock()
	if e := sh.items[id]; e != nil {
		sh.removeLocked(e)
	}
	sh.mu.Unlock()
}

func (sh *detailShard) removeLocked(e *detailEntry) {
	sh.order.Remove(e.elem)
	delete(sh.items, e.id)
	sh.bytes -= e.size
}

// cachedDetailStore caches public event details to keep load off the database.
//
//   - Hits are a sharded map lookup under a read lock: no DB call, no allocation.
//   - After SoftTTL, stale data is served instantly while ONE background refresh
//     runs; failed refreshes back off exponentially instead of hammering the DB.
//   - Misses for the same ID are collapsed (singleflight); total concurrent DB
//     loads are capped so a slow DB is never flooded.
//   - Not-found / non-public IDs are cached briefly (negative cache).
//   - TTLs are jittered so entries don't all expire at the same instant.
type cachedDetailStore struct {
	source Store
	cfg    detailCacheConfig
	shards [detailShards]*detailShard
	group  singleflight.Group
	sem    chan struct{}

	base   context.Context
	cancel context.CancelFunc

	known        atomic.Pointer[map[bson.ObjectID]int64] // public IDs as of the last batch; nil until the first success
	unknownLimit *rate.Limiter
	home         *homeCache // nil if the source has no FindHome

	hits, staleHits, negHits, misses, loads, loadErrors, oversize, unknownDropped atomic.Uint64
}

func newCachedDetailStore(src Store) *cachedDetailStore {
	return newCachedDetailStoreWithConfig(src, detailCacheConfig{})
}

func newCachedDetailStoreWithConfig(src Store, cfg detailCacheConfig) *cachedDetailStore {
	cfg.withDefaults()
	base, cancel := context.WithCancel(context.Background())
	s := &cachedDetailStore{
		source:       src,
		cfg:          cfg,
		sem:          make(chan struct{}, cfg.MaxConcurrentLoads),
		unknownLimit: rate.NewLimiter(rate.Limit(cfg.UnknownLookupsPerSec), int(cfg.UnknownLookupsPerSec)+1),
		base:         base,
		cancel:       cancel,
	}
	for i := range s.shards {
		s.shards[i] = &detailShard{
			items:    make(map[bson.ObjectID]*detailEntry),
			order:    list.New(),
			maxBytes: cfg.MaxBytes / detailShards,
		}
	}
	if hs, ok := src.(homeStore); ok {
		s.home = newHomeCache(hs, base)
		go s.home.Warm(base)
	}
	return s
}

// Close stops background refreshes and cancels in-flight loads.
func (s *cachedDetailStore) Close() { s.cancel() }

func (s *cachedDetailStore) Ping(ctx context.Context) error { return s.source.Ping(ctx) }

func (s *cachedDetailStore) shardFor(id bson.ObjectID) *detailShard {
	// Last 4 bytes of an ObjectID are the counter; mix them for an even spread.
	h := binary.LittleEndian.Uint32(id[8:12]) * 2654435761
	return s.shards[h>>27] // top 5 bits -> 32 shards
}

// FindPublic implements Store. It decodes the cached BSON into a fresh bson.M,
// so callers may mutate the result freely. Prefer FindPublicRaw on hot paths.
func (s *cachedDetailStore) FindPublic(ctx context.Context, id bson.ObjectID) (bson.M, error) {
	raw, err := s.FindPublicRaw(ctx, id)
	if err != nil {
		return nil, err
	}
	var doc bson.M
	if err := bson.Unmarshal(raw, &doc); err != nil {
		return nil, err
	}
	return doc, nil
}

// FindPublicRaw returns the cached BSON document with zero copying or decoding.
// The returned bytes are SHARED and MUST NOT be modified. Read fields with
// raw.Lookup("name"), or decode into a typed struct (much cheaper than bson.M).
func (s *cachedDetailStore) FindPublicRaw(ctx context.Context, id bson.ObjectID) (bson.Raw, error) {
	_, raw, err := s.lookup(ctx, id)
	return raw, err
}

// FindPublicJSON returns the final response bytes for (id, lang). render is run
// at most once per cache entry per language; every later hit is just a pointer
// load, with no BSON decoding, payload building or JSON encoding.
// The returned bytes are SHARED and MUST NOT be modified.
func (s *cachedDetailStore) FindPublicJSON(ctx context.Context, id bson.ObjectID, lang string, render func(bson.M, string) ([]byte, error)) ([]byte, error) {
	e, raw, err := s.lookup(ctx, id)
	if err != nil {
		return nil, err
	}
	slot := langSlot(lang)
	if e != nil {
		if p := e.rendered[slot].Load(); p != nil {
			return *p, nil
		}
	}
	var doc bson.M
	if err := bson.Unmarshal(raw, &doc); err != nil {
		return nil, err
	}
	out, err := render(doc, lang)
	if err != nil {
		return nil, err
	}
	if e != nil {
		e.rendered[slot].Store(&out)
	}
	return out, nil
}

func langSlot(lang string) int {
	switch lang {
	case "fi":
		return 1
	case "en":
		return 2
	case "sv":
		return 3
	}
	return 0
}

// lookup returns the cache entry when the answer came from cache (nil on a load).
func (s *cachedDetailStore) lookup(ctx context.Context, id bson.ObjectID) (*detailEntry, bson.Raw, error) {
	now := time.Now().UnixNano()

	if e := s.shardFor(id).get(id); e != nil && now < e.hardExpiry.Load() {
		if e.err != nil {
			if now < e.softExpiry.Load() {
				s.negHits.Add(1)
				return nil, nil, e.err
			}
			// negative entry expired: fall through and re-check
		} else {
			s.hits.Add(1)
			if now >= e.softExpiry.Load() {
				s.staleHits.Add(1)
				s.refreshAsync(e)
			}
			return e, e.data, nil
		}
	}

	// ID not public as of the last batch: this is what scanners and cache-busting
	// floods look like. Allow only a tiny GLOBAL budget of DB lookups for such IDs
	// (so a newly published event still appears within seconds) and drop the rest
	// without any DB work.
	if k := s.known.Load(); k != nil {
		if _, ok := (*k)[id]; !ok && !s.unknownLimit.Allow() {
			s.unknownDropped.Add(1)
			return nil, nil, mongo.ErrNoDocuments
		}
	}

	s.misses.Add(1)
	raw, err := s.wait(ctx, s.doLoad(id, false))
	return nil, raw, err
}

func (s *cachedDetailStore) wait(ctx context.Context, ch <-chan singleflight.Result) (bson.Raw, error) {
	select {
	case r := <-ch:
		if r.Err != nil {
			return nil, r.Err
		}
		return r.Val.(bson.Raw), nil
	case <-ctx.Done():
		// Only this caller gives up; the load continues and still fills the cache.
		return nil, ctx.Err()
	}
}

// doLoad runs (or joins) the single in-flight load for id. It uses the store's
// own context, not the caller's, so one cancelled request can't fail the others.
// slotHeld means the caller already holds a concurrency slot.
func (s *cachedDetailStore) doLoad(id bson.ObjectID, slotHeld bool) <-chan singleflight.Result {
	return s.group.DoChan(id.Hex(), func() (any, error) {
		ctx, cancel := context.WithTimeout(s.base, s.cfg.LoadTimeout)
		defer cancel()

		if !slotHeld {
			select {
			case s.sem <- struct{}{}:
				defer func() { <-s.sem }()
			case <-ctx.Done():
				return nil, ctx.Err()
			}
		}

		s.loads.Add(1)
		doc, err := s.source.FindPublic(ctx, id)
		if err != nil {
			if isNotPublic(err) {
				s.shardFor(id).put(s.newEntry(id, nil, err, s.cfg.NegativeTTL, s.cfg.NegativeTTL))
			} else {
				s.loadErrors.Add(1)
			}
			return nil, err
		}
		raw, err := bson.Marshal(doc)
		if err != nil {
			return nil, err
		}
		if len(raw) <= s.cfg.MaxEntryBytes {
			s.shardFor(id).put(s.newEntry(id, raw, nil, s.cfg.SoftTTL, s.cfg.HardTTL))
		} else {
			s.oversize.Add(1)
		}
		return bson.Raw(raw), nil
	})
}

// refreshAsync starts at most one background refresh per entry. It never blocks
// the request, never queues behind foreground loads (it skips if the DB is
// saturated), and backs off after failures while the stale copy keeps serving.
func (s *cachedDetailStore) refreshAsync(e *detailEntry) {
	if !e.refreshing.CompareAndSwap(false, true) {
		return
	}
	select {
	case s.sem <- struct{}{}:
	default: // DB busy: try again shortly, keep serving stale
		e.softExpiry.Store(time.Now().Add(5 * time.Second).UnixNano())
		e.refreshing.Store(false)
		return
	}
	go func() {
		defer func() {
			<-s.sem
			e.refreshing.Store(false)
		}()
		r := <-s.doLoad(e.id, true)
		if r.Err != nil && !isNotPublic(r.Err) {
			n := min(e.failures.Add(1), 5)
			delay := min(10*time.Second<<n, s.cfg.RefreshBackoffMax)
			e.softExpiry.Store(time.Now().Add(delay).UnixNano())
		}
		// On success, doLoad already replaced this entry with a fresh one.
	}()
}

func (s *cachedDetailStore) newEntry(id bson.ObjectID, data bson.Raw, err error, soft, hard time.Duration) *detailEntry {
	now := time.Now()
	e := &detailEntry{
		id:   id,
		data: data,
		err:  err,
		size: int64(len(data))*3 + entryOverhead, // x3: room for memoized JSON renderings
	}
	e.hardExpiry.Store(now.Add(hard).UnixNano())
	e.softExpiry.Store(now.Add(jitter(soft)).UnixNano())
	return e
}

// jitter spreads d by +-10% so entries loaded together don't expire together.
func jitter(d time.Duration) time.Duration {
	if d < 10 {
		return d
	}
	return d - d/10 + rand.N(d/5)
}

// Invalidate drops an entry immediately (e.g. an emergency takedown endpoint).
func (s *cachedDetailStore) Invalidate(id bson.ObjectID) { s.shardFor(id).remove(id) }

// Warm preloads ids with limited concurrency. Call at startup with your most
// viewed events so deploys don't send a burst of cold misses to the DB.
func (s *cachedDetailStore) Warm(ctx context.Context, ids []bson.ObjectID) {
	var wg sync.WaitGroup
	gate := make(chan struct{}, 4)
	for _, id := range ids {
		if ctx.Err() != nil {
			break
		}
		gate <- struct{}{}
		wg.Add(1)
		go func(id bson.ObjectID) {
			defer func() { <-gate; wg.Done() }()
			_, _ = s.FindPublicRaw(ctx, id)
		}(id)
	}
	wg.Wait()
}

func (s *cachedDetailStore) Stats() detailCacheStats {
	return detailCacheStats{
		Hits:           s.hits.Load(),
		StaleHits:      s.staleHits.Load(),
		NegativeHits:   s.negHits.Load(),
		Misses:         s.misses.Load(),
		Loads:          s.loads.Load(),
		LoadErrors:     s.loadErrors.Load(),
		Oversize:       s.oversize.Load(),
		UnknownDropped: s.unknownDropped.Load(),
	}
}
