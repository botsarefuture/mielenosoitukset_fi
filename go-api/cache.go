package main

import (
	"context"
	"sync"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
)

const detailCacheTTL = 15 * time.Minute
const detailCacheEntries = 1024
const detailCacheMaxDocumentBytes = 32 * 1024

type publicDetailStore interface {
	Store
	CheckPublic(context.Context, bson.ObjectID) error
}

type detailCacheEntry struct {
	data      []byte
	expiresAt time.Time
}

// Cache projected content across languages, but recheck visibility on every hit.
// Serialized entries prevent callers from mutating shared cached BSON documents.
type cachedDetailStore struct {
	source  publicDetailStore
	mu      sync.Mutex
	entries map[bson.ObjectID]detailCacheEntry
}

func newCachedDetailStore(source publicDetailStore) *cachedDetailStore {
	return &cachedDetailStore{source: source, entries: make(map[bson.ObjectID]detailCacheEntry)}
}

func (s *cachedDetailStore) Ping(ctx context.Context) error { return s.source.Ping(ctx) }

func (s *cachedDetailStore) FindPublic(ctx context.Context, id bson.ObjectID) (bson.M, error) {
	now := time.Now()
	s.mu.Lock()
	entry, hit := s.entries[id]
	if hit && !now.Before(entry.expiresAt) {
		delete(s.entries, id)
		hit = false
	}
	s.mu.Unlock()
	if hit {
		// A cached public event must disappear immediately after moderation.
		if err := s.source.CheckPublic(ctx, id); err != nil {
			s.mu.Lock()
			delete(s.entries, id)
			s.mu.Unlock()
			return nil, err
		}
		var document bson.M
		if err := bson.Unmarshal(entry.data, &document); err == nil {
			return document, nil
		}
	}

	document, err := s.source.FindPublic(ctx, id)
	if err != nil {
		return nil, err // Never cache errors or missing/nonpublic records.
	}
	data, err := bson.Marshal(document)
	if err != nil || len(data) > detailCacheMaxDocumentBytes {
		return document, nil
	}

	now = time.Now()
	s.mu.Lock()
	defer s.mu.Unlock()
	for key, cached := range s.entries {
		if !now.Before(cached.expiresAt) {
			delete(s.entries, key)
		}
	}
	if len(s.entries) >= detailCacheEntries {
		var oldest bson.ObjectID
		var earliest time.Time
		for key, cached := range s.entries {
			if earliest.IsZero() || cached.expiresAt.Before(earliest) {
				oldest, earliest = key, cached.expiresAt
			}
		}
		delete(s.entries, oldest)
	}
	s.entries[id] = detailCacheEntry{data: data, expiresAt: now.Add(detailCacheTTL)}
	return document, nil
}
