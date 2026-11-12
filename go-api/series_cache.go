package main

import (
	"context"
	"errors"
	"sync"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"golang.org/x/sync/singleflight"
)

// A series page is four database reads. A list is fresh for five minutes; after
// that, within the same Helsinki day it is served at once while one background
// load refreshes it. A list from an earlier day waits for the new load, but is
// still served if the database fails: a day-old occurrence list is more useful
// than an error page. Not-public answers are remembered for a minute.
const (
	seriesFreshTTL    = 5 * time.Minute
	seriesStaleTTL    = 24 * time.Hour
	seriesNegativeTTL = time.Minute
	seriesMaxItems    = 2000
)

type seriesCacheEntry struct {
	payload  seriesPayload
	notFound bool
	day      string
	savedAt  time.Time
}

type seriesCache struct {
	source seriesStore
	now    func() time.Time
	mu     sync.Mutex
	items  map[bson.ObjectID]seriesCacheEntry
	group  singleflight.Group
}

// cacheLoadTimeout bounds a database load that no longer has a waiting caller.
const cacheLoadTimeout = 5 * time.Second

func newSeriesCache(source seriesStore) *seriesCache {
	return &seriesCache{source: source, now: time.Now, items: map[bson.ObjectID]seriesCacheEntry{}}
}

func (c *seriesCache) find(ctx context.Context, parent bson.ObjectID) (seriesPayload, error) {
	now := c.now()
	c.mu.Lock()
	entry, hit := c.items[parent]
	c.mu.Unlock()
	usable := hit && !entry.notFound && now.Sub(entry.savedAt) < seriesStaleTTL
	if hit {
		age := now.Sub(entry.savedAt)
		switch {
		case entry.notFound && age < seriesNegativeTTL:
			return seriesPayload{}, mongo.ErrNoDocuments
		case usable && age < seriesFreshTTL && entry.day == localDay(now):
			return entry.payload, nil
		}
	}
	// One detached load per parent: it outlives a caller that gives up, so the
	// next request finds the result.
	result := c.group.DoChan(parent.Hex(), func() (any, error) {
		loadCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), cacheLoadTimeout)
		defer cancel()
		payload, err := c.source.FindSeries(loadCtx, parent)
		loadedAt := c.now()
		switch {
		case err == nil:
			c.store(parent, seriesCacheEntry{payload: payload, day: localDay(loadedAt), savedAt: loadedAt})
		case errors.Is(err, mongo.ErrNoDocuments):
			c.store(parent, seriesCacheEntry{notFound: true, savedAt: loadedAt})
		}
		return payload, err
	})
	if usable && entry.day == localDay(now) {
		// Same day, older than five minutes: answer now, the refresh runs on.
		return entry.payload, nil
	}
	select {
	case <-ctx.Done():
		if usable {
			return entry.payload, nil
		}
		return seriesPayload{}, ctx.Err()
	case done := <-result:
		switch {
		case done.Err == nil:
			return done.Val.(seriesPayload), nil
		case usable && !errors.Is(done.Err, mongo.ErrNoDocuments):
			// Yesterday's list beats an error page while the database is failing.
			return entry.payload, nil
		default:
			return seriesPayload{}, done.Err
		}
	}
}

func (c *seriesCache) store(parent bson.ObjectID, entry seriesCacheEntry) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if _, exists := c.items[parent]; !exists && len(c.items) >= seriesMaxItems {
		c.items = map[bson.ObjectID]seriesCacheEntry{}
	}
	c.items[parent] = entry
}
