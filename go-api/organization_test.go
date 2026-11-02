package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

type fakeOrganizationStore struct {
	fakeStore
	organizationErr error
	profile         organizationProfile
	loads           atomic.Int32
	active          atomic.Int32
	peak            atomic.Int32
	gate            chan struct{}
}

func (s *fakeOrganizationStore) FindOrganization(ctx context.Context, id bson.ObjectID) (organizationProfile, error) {
	if _, ok := ctx.Deadline(); !ok {
		panic("missing organization deadline")
	}
	s.loads.Add(1)
	active := s.active.Add(1)
	defer s.active.Add(-1)
	for peak := s.peak.Load(); active > peak && !s.peak.CompareAndSwap(peak, active); peak = s.peak.Load() {
	}
	if s.gate != nil {
		select {
		case <-s.gate:
		case <-ctx.Done():
			return organizationProfile{}, ctx.Err()
		}
	}
	profile := s.profile
	profile.ID = id.Hex()
	return profile, s.organizationErr
}

func TestOrganizationHTTPContract(t *testing.T) {
	id := bson.NewObjectID()
	for _, tc := range []struct {
		path   string
		err    error
		status int
		calls  int32
	}{
		{"/api/organizations/" + id.Hex(), nil, 200, 1},
		{"/api/organizations/" + id.Hex() + "?lang=en", nil, 200, 1},
		{"/api/organizations/nope", nil, 404, 0},
		{"/api/organizations/000000000000000000000000", nil, 404, 0},
		{"/api/organizations/" + id.Hex() + "?include_private=true", nil, 400, 0},
		{"/api/organizations/" + id.Hex() + "?lang=fi&lang=en", nil, 400, 0},
		{"/api/organizations/" + id.Hex(), mongo.ErrNoDocuments, 404, 1},
		{"/api/organizations/" + id.Hex(), errors.New("mongodb://secret"), 503, 1},
	} {
		source := &fakeOrganizationStore{organizationErr: tc.err,
			profile: organizationProfile{Name: "Yhteinen Helsinki", Socials: map[string]string{}}}
		w := httptest.NewRecorder()
		(&API{source}).handler().ServeHTTP(w, httptest.NewRequest("GET", tc.path, nil))
		if w.Code != tc.status || source.loads.Load() != tc.calls || strings.Contains(w.Body.String(), "secret") {
			t.Fatalf("%s: status=%d calls=%d body=%s", tc.path, w.Code, source.loads.Load(), w.Body.String())
		}
		cacheControl := "no-store"
		if tc.status == 200 {
			cacheControl = "public, max-age=30, s-maxage=60"
			var payload map[string]any
			if err := json.Unmarshal(w.Body.Bytes(), &payload); err != nil || len(payload) != 8 || payload["_id"] != id.Hex() {
				t.Fatalf("public contract changed: %s", w.Body.String())
			}
		}
		if w.Header().Get("Cache-Control") != cacheControl || w.Header().Get("Access-Control-Allow-Origin") != "*" {
			t.Fatalf("unexpected headers: %v", w.Header())
		}
	}
	source := &fakeOrganizationStore{profile: organizationProfile{Name: "Public", Socials: map[string]string{}}}
	cache := newCachedDetailStore(source)
	defer cache.Close()
	var body string
	for _, cookie := range []string{"", "session=admin"} {
		request := httptest.NewRequest("GET", "/api/organizations/"+id.Hex(), nil)
		request.Header.Set("Cookie", cookie)
		w := httptest.NewRecorder()
		(&API{cache}).handler().ServeHTTP(w, request)
		if w.Code != 200 || (body != "" && body != w.Body.String()) {
			t.Fatalf("cookie changed public response: %d %s", w.Code, w.Body.String())
		}
		body = w.Body.String()
	}
	if source.loads.Load() != 1 {
		t.Fatal("public cookie variants did not share cache")
	}
}

func TestOrganizationPublicProjectionAndURLs(t *testing.T) {
	profile := publicOrganization(bson.NewObjectID(), bson.M{
		"name": "Public", "description": "<p>Plain text</p>", "email": "public@example.org",
		"website": "https://example.org", "logo": "/static/logo.png", "verified": true,
		"social_media_links": bson.M{"facebook": "https://facebook.com/public", "unsafe": "javascript:alert(1)",
			"credentials": "https://user:pass@example.org", "control": "https://example.org/\nprivate"},
		"members": bson.A{"PRIVATE_MEMBER"}, "invitations": bson.A{"PRIVATE_INVITE"}, "permissions": "PRIVATE_PERMISSION",
	})
	data, _ := json.Marshal(profile)
	if strings.Contains(string(data), "PRIVATE") || len(profile.Socials) != 1 || !profile.Verified || profile.Logo != "/static/logo.png" || profile.Email != "public@example.org" {
		t.Fatalf("public projection unsafe: %s", data)
	}
	for _, value := range []any{nil, 42, "javascript:alert(1)", "data:image/png;base64,test", "//example.org/logo.png", "/\\example.org/x", "https://user:pass@example.org"} {
		if organizationURL(value) != "" {
			t.Fatalf("unsafe organization URL accepted: %v", value)
		}
	}
	if publicOrganization(bson.NewObjectID(), bson.M{"verified": "true"}).Verified {
		t.Fatal("malformed verification flag granted a badge")
	}
}

func TestOrganizationCacheCoalescingExpiryAndBounds(t *testing.T) {
	source := &fakeOrganizationStore{gate: make(chan struct{}), profile: organizationProfile{Name: "Public", Socials: map[string]string{}}}
	cache := newOrganizationCache(source, context.Background())
	id := bson.NewObjectID()
	var wg sync.WaitGroup
	for range 8 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if _, err := cache.get(context.Background(), id); err != nil {
				t.Error(err)
			}
		}()
	}
	for source.loads.Load() == 0 {
		time.Sleep(time.Millisecond)
	}
	close(source.gate)
	wg.Wait()
	if source.loads.Load() != 1 {
		t.Fatalf("identical loads were not coalesced: %d", source.loads.Load())
	}
	now := time.Now()
	cache.now = func() time.Time { return now.Add(61 * time.Second) }
	source.organizationErr = mongo.ErrNoDocuments
	for range 2 {
		if _, err := cache.get(context.Background(), id); !errors.Is(err, mongo.ErrNoDocuments) {
			t.Fatalf("expired/missing organization was cached: %v", err)
		}
	}
	if source.loads.Load() != 3 {
		t.Fatal("missing organizations were cached")
	}
	source.organizationErr = nil
	for range 140 {
		if _, err := cache.get(context.Background(), bson.NewObjectID()); err != nil {
			t.Fatal(err)
		}
	}
	if len(cache.items) > organizationMaxItems || cache.bytes > organizationMaxBytes {
		t.Fatal("organization cache exceeded its bounds")
	}
	oversize := bson.NewObjectID()
	cache.put(oversize, make([]byte, 65<<10))
	if _, ok := cache.read(oversize); ok {
		t.Fatal("oversize organization entered the cache")
	}
}

func TestOrganizationCacheLimitsConcurrentDatabaseWork(t *testing.T) {
	source := &fakeOrganizationStore{gate: make(chan struct{})}
	cache := newOrganizationCache(source, context.Background())
	var wg sync.WaitGroup
	for range 16 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _ = cache.get(context.Background(), bson.NewObjectID())
		}()
	}
	deadline := time.Now().Add(2 * time.Second)
	for len(cache.queue) < 16 && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
	}
	if len(cache.queue) != 16 {
		close(source.gate)
		wg.Wait()
		t.Fatal("could not fill bounded organization queue")
	}
	if _, err := cache.get(context.Background(), bson.NewObjectID()); err == nil {
		t.Error("full organization queue accepted a new variant")
	}
	close(source.gate)
	wg.Wait()
	if source.peak.Load() > 4 {
		t.Fatalf("database concurrency exceeded limit: %d", source.peak.Load())
	}
}

func TestMongoOrganizationProfileRead(t *testing.T) {
	uri := os.Getenv("TEST_MONGODB_URI")
	if uri == "" {
		t.Skip("set TEST_MONGODB_URI for isolated MongoDB integration")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	client, err := mongo.Connect(options.Client().ApplyURI(uri))
	if err != nil {
		t.Fatal(err)
	}
	defer client.Disconnect(context.Background())
	db := client.Database("moso_go_organization_test_" + bson.NewObjectID().Hex())
	defer db.Drop(context.Background())
	id := bson.NewObjectID()
	_, err = db.Collection("organizations").InsertOne(ctx, bson.M{"_id": id, "name": "Unverified public group",
		"email": "public@example.org", "verified": false, "social_media_links": bson.M{"facebook": "https://facebook.com/public"},
		"members": bson.A{bson.M{"password_hash": "PRIVATE"}}, "invitations": bson.A{"PRIVATE"}})
	if err != nil {
		t.Fatal(err)
	}
	store := mongoStore{db.Collection("demonstrations"), client}
	profile, err := store.FindOrganization(ctx, id)
	if err != nil || profile.Name != "Unverified public group" || profile.Verified || profile.Email != "public@example.org" {
		t.Fatalf("organization read lost public fields: %+v %v", profile, err)
	}
	data, _ := json.Marshal(profile)
	if strings.Contains(string(data), "PRIVATE") {
		t.Fatal("private organization data leaked")
	}
	if _, err := store.FindOrganization(ctx, bson.NewObjectID()); !errors.Is(err, mongo.ErrNoDocuments) {
		t.Fatalf("unknown organization: %v", err)
	}
}
