package main

import (
	"context"
	"errors"
	"log/slog"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
)

// batchSource is what the underlying Store must additionally implement to
// enable batch refresh.
//
//	PublicVersions: ONE cheap query returning _id -> version for every public
//	  demo event. Version is anything that changes on every edit (updatedAt as
//	  unix millis, or a rev counter). With an index on {public:1, updatedAt:1}
//	  and a projection of just those two fields, Mongo answers it from the index
//	  alone without reading a single document.
//	FindPublicMany: ONE query ({_id: {$in: ids}, public: true}) for changed docs.
type batchSource interface {
	PublicVersions(ctx context.Context) (map[bson.ObjectID]int64, error)
	FindPublicMany(ctx context.Context, ids []bson.ObjectID) (map[bson.ObjectID]bson.M, error)
}

const (
	batchChunk = 200
	batchPace  = 50 * time.Millisecond // pause between chunks so the batch never floods the DB
)

// peek reads an entry without marking it as recently used.
func (sh *detailShard) peek(id bson.ObjectID) *detailEntry {
	sh.mu.RLock()
	e := sh.items[id]
	sh.mu.RUnlock()
	return e
}

// StartBatchRefresh returns immediately. In the background it runs one batch
// (warming the cache and building the known-ID set), then repeats every
// BatchInterval until Close. A failed batch changes nothing (the cache keeps
// serving what it has) and is retried after about a minute.
func (s *cachedDetailStore) StartBatchRefresh() error {
	bs, ok := s.source.(batchSource)
	if !ok {
		return errors.New("detail cache: source does not implement batchSource")
	}
	go func() {
		ctx, cancel := context.WithTimeout(s.base, 2*time.Minute)
		err := s.refreshBatch(ctx, bs)
		cancel()
		if err != nil {
			slog.Error("detail cache: initial batch failed", "err", err)
		}
		s.batchLoop(bs, err != nil)
	}()
	return nil
}

func (s *cachedDetailStore) batchLoop(bs batchSource, retrySoon bool) {
	next := func(failed bool) time.Duration {
		if failed {
			return jitter(time.Minute)
		}
		return jitter(s.cfg.BatchInterval) // jitter keeps replicas from syncing up
	}
	timer := time.NewTimer(next(retrySoon))
	defer timer.Stop()
	for {
		select {
		case <-s.base.Done():
			return
		case <-timer.C:
		}
		ctx, cancel := context.WithTimeout(s.base, 2*time.Minute)
		err := s.refreshBatch(ctx, bs)
		cancel()
		if err != nil {
			slog.Error("detail cache: batch failed", "err", err)
		}
		timer.Reset(next(err != nil))
	}
}

// refreshBatch compares versions in one query, then fetches only what changed.
//
//	unchanged entries -> expiries pushed forward (the batch vouches for them)
//	new/changed       -> fetched with $in in paced chunks
//	no longer public  -> evicted
//	known-ID set      -> replaced, so unknown IDs can be rejected without the DB
func (s *cachedDetailStore) refreshBatch(ctx context.Context, bs batchSource) error {
	versions, err := bs.PublicVersions(ctx)
	if err != nil {
		return err // keep everything as-is
	}

	now := time.Now()
	var need []bson.ObjectID
	for id, v := range versions {
		e := s.shardFor(id).peek(id)
		// v == 0 means the document has no version field: can't prove it's unchanged.
		if e == nil || e.err != nil || v == 0 || e.version != v {
			need = append(need, id)
			continue
		}
		e.softExpiry.Store(now.Add(jitter(s.cfg.SoftTTL)).UnixNano())
		e.hardExpiry.Store(now.Add(s.cfg.HardTTL).UnixNano())
	}

	var loadErr error
	for start := 0; start < len(need); start += batchChunk {
		end := min(start+batchChunk, len(need))
		docs, err := bs.FindPublicMany(ctx, need[start:end])
		if err != nil {
			loadErr = err // DB struggling: stop loading, but still apply what we know
			break
		}
		for id, doc := range docs {
			raw, err := bson.Marshal(doc)
			if err != nil {
				continue
			}
			if len(raw) > s.cfg.MaxEntryBytes {
				s.oversize.Add(1)
				continue
			}
			e := s.newEntry(id, raw, nil, s.cfg.SoftTTL, s.cfg.HardTTL)
			e.version = versions[id]
			s.shardFor(id).put(e)
		}
		if end < len(need) {
			select {
			case <-time.After(batchPace):
			case <-ctx.Done():
				loadErr = ctx.Err()
				start = len(need) // ends the loop
			}
		}
	}

	// Evict events that are no longer public (negative entries age out on their own).
	for _, sh := range s.shards {
		sh.mu.Lock()
		for id, e := range sh.items {
			if e.err != nil {
				continue
			}
			if _, ok := versions[id]; !ok {
				sh.removeLocked(e)
			}
		}
		sh.mu.Unlock()
	}

	s.known.Store(&versions) // never mutated after this point
	return loadErr
}
