package main

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
)

type fakeResolveStore struct {
	mu      sync.Mutex
	answers map[string]bson.ObjectID
	err     error
	gate    chan struct{} // when set, each lookup waits for it
	calls   atomic.Int32
}

func (s *fakeResolveStore) FindPublic(context.Context, bson.ObjectID) (bson.M, error) {
	return nil, mongo.ErrNoDocuments
}
func (s *fakeResolveStore) Ping(context.Context) error { return nil }
func (s *fakeResolveStore) ResolvePublicID(ctx context.Context, raw string) (bson.ObjectID, error) {
	s.calls.Add(1)
	if s.gate != nil {
		<-s.gate
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.err != nil {
		return bson.NilObjectID, s.err
	}
	if id, ok := s.answers[raw]; ok {
		return id, nil
	}
	return bson.NilObjectID, mongo.ErrNoDocuments
}

func (s *fakeResolveStore) set(err error) {
	s.mu.Lock()
	s.err = err
	s.mu.Unlock()
}

type fakeClock struct {
	mu  sync.Mutex
	now time.Time
}

func (c *fakeClock) Now() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.now
}
func (c *fakeClock) add(d time.Duration) {
	c.mu.Lock()
	c.now = c.now.Add(d)
	c.mu.Unlock()
}

func waitFor(t *testing.T, condition func() bool) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for !condition() {
		if time.Now().After(deadline) {
			t.Fatal("condition not reached")
		}
		time.Sleep(time.Millisecond)
	}
}

func newResolveTestStore(source Store) (*cachedDetailStore, *fakeClock) {
	clock := &fakeClock{now: time.Date(2026, 11, 12, 10, 0, 0, 0, time.UTC)}
	store := &cachedDetailStore{source: source, resolved: newResolveCache()}
	store.resolved.now = clock.Now
	return store, clock
}

func TestResolveKnownObjectIDNeedsNoDatabase(t *testing.T) {
	id := bson.NewObjectID()
	source := &fakeResolveStore{err: errors.New("database down")}
	store, _ := newResolveTestStore(source)
	store.known.Store(&map[bson.ObjectID]int64{id: 1})
	got, err := store.ResolvePublicID(context.Background(), id.Hex())
	if err != nil || got != id || source.calls.Load() != 0 {
		t.Fatalf("got=%v err=%v calls=%d", got, err, source.calls.Load())
	}
}

// A slug resolved once keeps working through a database failure: the stale
// answer is returned at once while one background lookup retries.
func TestResolveSlugServesStaleDuringOutage(t *testing.T) {
	id := bson.NewObjectID()
	source := &fakeResolveStore{answers: map[string]bson.ObjectID{"mielenosoitus": id}}
	store, clock := newResolveTestStore(source)
	ctx := context.Background()
	for range 3 {
		if got, err := store.ResolvePublicID(ctx, "mielenosoitus"); err != nil || got != id {
			t.Fatalf("got=%v err=%v", got, err)
		}
	}
	if source.calls.Load() != 1 {
		t.Fatalf("fresh hits reached the database: %d", source.calls.Load())
	}
	clock.add(resolveFreshTTL + time.Second)
	source.set(mongo.CommandError{Labels: []string{"NetworkError"}})
	if got, err := store.ResolvePublicID(ctx, "mielenosoitus"); err != nil || got != id {
		t.Fatalf("outage answer got=%v err=%v", got, err)
	}
	waitFor(t, func() bool { return source.calls.Load() == 2 })

	clock.add(resolveStaleTTL)
	if _, err := store.ResolvePublicID(ctx, "mielenosoitus"); err == nil {
		t.Fatal("a day-old answer outlived the stale limit")
	}
}

func TestResolveNotFoundIsNotCached(t *testing.T) {
	id := bson.NewObjectID()
	source := &fakeResolveStore{answers: map[string]bson.ObjectID{}}
	store, _ := newResolveTestStore(source)
	if _, err := store.ResolvePublicID(context.Background(), "uusi"); !errors.Is(err, mongo.ErrNoDocuments) {
		t.Fatalf("err=%v", err)
	}
	source.mu.Lock()
	source.answers["uusi"] = id
	source.mu.Unlock()
	if got, err := store.ResolvePublicID(context.Background(), "uusi"); err != nil || got != id {
		t.Fatalf("published slug not found: got=%v err=%v", got, err)
	}
}

// The React host abandons a request after 1.5 s. The lookup it started still
// completes and is cached, so the retry does not wait on the database again.
func TestResolveCompletesAfterCallerLeaves(t *testing.T) {
	id := bson.NewObjectID()
	source := &fakeResolveStore{answers: map[string]bson.ObjectID{"hidas": id}, gate: make(chan struct{})}
	store, _ := newResolveTestStore(source)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := store.ResolvePublicID(ctx, "hidas"); !errors.Is(err, context.Canceled) {
		t.Fatalf("err=%v", err)
	}
	close(source.gate)
	waitFor(t, func() bool { _, ok := store.resolved.get("hidas"); return ok })
	if got, err := store.ResolvePublicID(context.Background(), "hidas"); err != nil || got != id || source.calls.Load() != 1 {
		t.Fatalf("got=%v err=%v calls=%d", got, err, source.calls.Load())
	}
}

type fakeSeriesSource struct {
	mu      sync.Mutex
	payload seriesPayload
	err     error
	calls   atomic.Int32
}

func (s *fakeSeriesSource) FindSeries(context.Context, bson.ObjectID) (seriesPayload, error) {
	s.calls.Add(1)
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.payload, s.err
}

func (s *fakeSeriesSource) set(payload seriesPayload, err error) {
	s.mu.Lock()
	s.payload, s.err = payload, err
	s.mu.Unlock()
}

func TestSeriesCacheFreshStaleAndOutage(t *testing.T) {
	parent := bson.NewObjectID()
	first := seriesPayload{ID: parent.Hex(), Occurrences: []seriesOccurrence{{ID: "a", Date: "2026-11-20"}}}
	second := seriesPayload{ID: parent.Hex(), Occurrences: []seriesOccurrence{{ID: "b", Date: "2026-11-27"}}}
	source := &fakeSeriesSource{payload: first}
	clock := &fakeClock{now: time.Date(2026, 11, 12, 10, 0, 0, 0, time.UTC)}
	cache := newSeriesCache(source)
	cache.now = clock.Now
	ctx := context.Background()

	for range 2 {
		if got, err := cache.find(ctx, parent); err != nil || got.Occurrences[0].ID != "a" {
			t.Fatalf("got=%+v err=%v", got, err)
		}
	}
	if source.calls.Load() != 1 {
		t.Fatalf("calls=%d", source.calls.Load())
	}

	// Same day, past the fresh window: old list now, new list next time.
	clock.add(seriesFreshTTL + time.Second)
	source.set(second, nil)
	if got, _ := cache.find(ctx, parent); got.Occurrences[0].ID != "a" {
		t.Fatalf("stale hit did not answer at once: %+v", got)
	}
	waitFor(t, func() bool { got, _ := cache.find(ctx, parent); return got.Occurrences[0].ID == "b" })

	// Next day with the database down: yesterday's list, not a 503.
	clock.add(20 * time.Hour)
	source.set(seriesPayload{}, mongo.CommandError{Labels: []string{"NetworkError"}})
	if got, err := cache.find(ctx, parent); err != nil || got.Occurrences[0].ID != "b" {
		t.Fatalf("outage got=%+v err=%v", got, err)
	}
	// Beyond the stale limit the failure is reported.
	clock.add(seriesStaleTTL)
	if _, err := cache.find(ctx, parent); err == nil || errors.Is(err, mongo.ErrNoDocuments) {
		t.Fatalf("err=%v", err)
	}
}

func TestSeriesCacheNotPublicIsShortLived(t *testing.T) {
	parent := bson.NewObjectID()
	source := &fakeSeriesSource{err: mongo.ErrNoDocuments}
	clock := &fakeClock{now: time.Date(2026, 11, 12, 10, 0, 0, 0, time.UTC)}
	cache := newSeriesCache(source)
	cache.now = clock.Now
	for range 2 {
		if _, err := cache.find(context.Background(), parent); !errors.Is(err, mongo.ErrNoDocuments) {
			t.Fatalf("err=%v", err)
		}
	}
	if source.calls.Load() != 1 {
		t.Fatalf("calls=%d", source.calls.Load())
	}
	clock.add(seriesNegativeTTL + time.Second)
	source.set(seriesPayload{ID: parent.Hex(), Occurrences: []seriesOccurrence{}}, nil)
	if _, err := cache.find(context.Background(), parent); err != nil {
		t.Fatalf("approved series still hidden: %v", err)
	}
}
