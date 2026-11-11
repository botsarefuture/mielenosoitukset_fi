package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"go.mongodb.org/mongo-driver/v2/bson"
)

type adminCountStore struct {
	fakeStatusStore
	counts map[string]int
	err    error
	calls  int
}

type fakeStatusStore struct{}

func (fakeStatusStore) FindPublic(context.Context, bson.ObjectID) (bson.M, error) { return nil, nil }
func (fakeStatusStore) ResolvePublicID(context.Context, string) (bson.ObjectID, error) {
	return bson.ObjectID{}, nil
}
func (fakeStatusStore) Ping(context.Context) error { return nil }

func (s *adminCountStore) CountCityAdmins(_ context.Context, key string) (int, error) {
	s.calls++
	return s.counts[key], s.err
}

func TestCityAdminStatusOnlyExposesTheCoverageBand(t *testing.T) {
	for count, want := range map[int]string{0: "none", 1: "single", 2: "team", 7: "team"} {
		if got := cityAdminStatus(count); got != want {
			t.Fatalf("cityAdminStatus(%d) = %q, want %q", count, got, want)
		}
	}
}

func TestActiveAccountMatchesFlaskRules(t *testing.T) {
	cases := []struct {
		doc  bson.M
		want bool
	}{
		{bson.M{"confirmed": true}, true},
		{bson.M{"confirmed": true, "active": true, "banned": false}, true},
		{bson.M{"confirmed": false}, false},
		{bson.M{"confirmed": true, "active": false}, false},
		{bson.M{"confirmed": true, "banned": true}, false},
		{bson.M{"confirmed": true, "security_suspension": bson.M{"active": true}}, false},
	}
	for _, c := range cases {
		if got := activeAccount(c.doc); got != c.want {
			t.Fatalf("activeAccount(%v) = %v, want %v", c.doc, got, c.want)
		}
	}
}

func TestCityAdminStatusHandler(t *testing.T) {
	adminStatusCache = &cityAdminStatusCache{entries: map[string]cityAdminStatusEntry{}}
	store := &adminCountStore{counts: map[string]int{"helsinki": 3, "turku": 1}}
	api := &API{store: store}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/cities/{key}/admin-status", api.getCityAdminStatus)

	get := func(path string) (*httptest.ResponseRecorder, map[string]string) {
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, httptest.NewRequest("GET", path, nil))
		body := map[string]string{}
		_ = json.Unmarshal(rec.Body.Bytes(), &body)
		return rec, body
	}

	rec, body := get("/api/cities/helsinki/admin-status")
	if rec.Code != 200 || body["status"] != "national" || body["key"] != "helsinki" {
		t.Fatalf("helsinki is managed nationally: %d %v", rec.Code, body)
	}
	store.counts["tampere"] = 3
	rec, body = get("/api/cities/tampere/admin-status")
	if rec.Code != 200 || body["status"] != "team" {
		t.Fatalf("tampere: %d %v", rec.Code, body)
	}
	if _, leaked := body["count"]; leaked {
		t.Fatal("exact counts must not be exposed")
	}
	if _, body = get("/api/cities/turku/admin-status"); body["status"] != "single" {
		t.Fatalf("turku: %v", body)
	}
	if _, body = get("/api/cities/oulu/admin-status"); body["status"] != "none" {
		t.Fatalf("oulu: %v", body)
	}
	if rec, _ = get("/api/cities/not-a-city/admin-status"); rec.Code != 404 {
		t.Fatalf("unknown city: %d", rec.Code)
	}

	calls := store.calls
	get("/api/cities/tampere/admin-status")
	if store.calls != calls {
		t.Fatal("repeat reads within the TTL must come from the cache")
	}

	adminStatusCache = &cityAdminStatusCache{entries: map[string]cityAdminStatusEntry{}}
	store.err = errors.New("database unavailable")
	if rec, _ = get("/api/cities/tampere/admin-status"); rec.Code != 503 {
		t.Fatalf("read failure: %d", rec.Code)
	}
}

func TestCachedStoreForwardsCityAdminCounts(t *testing.T) {
	wrapped := &cachedDetailStore{source: &adminCountStore{counts: map[string]int{"oulu": 1}}}
	if count, err := wrapped.CountCityAdmins(context.Background(), "oulu"); err != nil || count != 1 {
		t.Fatalf("forwarded count = %d, %v", count, err)
	}
	if _, err := (&cachedDetailStore{source: fakeStatusStore{}}).CountCityAdmins(context.Background(), "oulu"); err == nil {
		t.Fatal("a source without counts must report an error, not zero admins")
	}
}
