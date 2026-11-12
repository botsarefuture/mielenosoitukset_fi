package main

import (
	"context"
	"errors"
	"sync"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
)

// Identifier resolution used to reach MongoDB on every detail request, with up
// to four sequential reads for a slug. The React host gives the API 1.5 s, so a
// short database stall turned into a "temporarily unavailable" page even when
// the event itself was cached. Resolution now needs the database only for an
// identifier it has not seen, and a known answer survives a database failure.
const (
	resolveFreshTTL = 10 * time.Minute
	resolveStaleTTL = 24 * time.Hour
	resolveMaxItems = 20000
)

type resolveEntry struct {
	id      bson.ObjectID
	savedAt time.Time
}

type resolveCache struct {
	mu    sync.Mutex
	items map[string]resolveEntry
	now   func() time.Time
}

func newResolveCache() *resolveCache {
	return &resolveCache{items: map[string]resolveEntry{}, now: time.Now}
}

func (c *resolveCache) get(raw string) (resolveEntry, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	entry, ok := c.items[raw]
	if ok && c.now().Sub(entry.savedAt) >= resolveStaleTTL {
		delete(c.items, raw)
		return resolveEntry{}, false
	}
	return entry, ok
}

func (c *resolveCache) put(raw string, id bson.ObjectID) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if _, exists := c.items[raw]; !exists && len(c.items) >= resolveMaxItems {
		// Bounded memory against scanners; real identifiers repopulate quickly.
		c.items = map[string]resolveEntry{}
	}
	c.items[raw] = resolveEntry{id: id, savedAt: c.now()}
}

func (c *resolveCache) forget(raw string) {
	c.mu.Lock()
	delete(c.items, raw)
	c.mu.Unlock()
}

// ResolvePublicID answers from memory when it can:
//   - an ObjectId that the last batch saw as public is its own answer, which is
//     exactly the first query the database path would run;
//   - a resolved slug, running number or alias is reused for 10 minutes, then
//     served for up to 24 hours while one background lookup refreshes it, so a
//     known identifier never waits on, or fails with, the database.
//
// Visibility is still decided by the detail read that follows, so a cached
// mapping never exposes an event that has since been hidden.
func (s *cachedDetailStore) ResolvePublicID(ctx context.Context, raw string) (bson.ObjectID, error) {
	if !validIdentifier(raw) {
		return bson.NilObjectID, errInvalidIdentifier
	}
	if id, err := bson.ObjectIDFromHex(raw); err == nil {
		if known := s.known.Load(); known != nil {
			if _, ok := (*known)[id]; ok {
				return id, nil
			}
		}
	}
	cached, hit := s.resolved.get(raw)
	if hit && s.resolved.now().Sub(cached.savedAt) < resolveFreshTTL {
		return cached.id, nil
	}
	// Shared and detached: concurrent requests for one identifier make one
	// lookup, and it completes for the next request even if this caller leaves.
	result := s.resolveGroup.DoChan(raw, func() (any, error) {
		loadCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), cacheLoadTimeout)
		defer cancel()
		id, err := s.source.ResolvePublicID(loadCtx, raw)
		switch {
		case err == nil:
			s.resolved.put(raw, id)
		case errors.Is(err, mongo.ErrNoDocuments), errors.Is(err, errInvalidIdentifier):
			s.resolved.forget(raw)
		}
		return id, err
	})
	if hit {
		// Stale but under a day old: answer now, the refresh runs on.
		return cached.id, nil
	}
	select {
	case <-ctx.Done():
		return bson.NilObjectID, ctx.Err()
	case done := <-result:
		id, _ := done.Val.(bson.ObjectID)
		return id, done.Err
	}
}
