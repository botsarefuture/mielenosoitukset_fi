package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
)

func testResponseCache(t *testing.T) (*redisResponseCache, *miniredis.Miniredis) {
	t.Helper()
	server := miniredis.RunT(t)
	cache, err := newRedisResponseCache("redis://"+server.Addr()+"/0", t.Name())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { cache.client.Close() })
	return cache, server
}

func TestSharedResponseCacheKeys(t *testing.T) {
	firstSource, err := publicCacheSource("mongodb://user:fake-password@host-a:27017", "public")
	if err != nil || strings.Contains(firstSource, "fake-password") || strings.Contains(firstSource, "user") {
		t.Fatal("credentials entered cache namespace")
	}
	secondSource, _ := publicCacheSource("mongodb://host-b:27017", "public")
	if firstSource == secondSource {
		t.Fatal("different Mongo sources shared a namespace")
	}
	now := time.Date(2026, 11, 2, 12, 0, 0, 0, time.UTC)
	key := func(path string, at time.Time) responsePolicy {
		t.Helper()
		policy, ok := publicResponsePolicy(httptest.NewRequest("GET", path, nil), at)
		if !ok {
			t.Fatal(path)
		}
		return policy
	}
	first := key("/api/demonstrations?city=Tampere,Helsinki,Helsinki&search=TEST", now)
	for path, ttl := range map[string]time.Duration{
		"/api/home": 5 * time.Minute, "/api/demonstrations": 5 * time.Minute,
		"/api/demonstrations/example":                 15 * time.Minute,
		"/api/series/66fa58601102367d5d52887f":        5 * time.Minute,
		"/api/organizations/66fa58601102367d5d52887f": time.Hour,
	} {
		if key(path, now).ttl != ttl {
			t.Fatal("unexpected public policy", path)
		}
	}
	equal := key("/api/demonstrations?search=test&city=helsinki,tampere", now)
	if first != equal {
		t.Fatal("equivalent queries do not share a key")
	}
	for _, path := range []string{"/api/demonstrations?page=2", "/api/demonstrations?lang=en", "/api/demonstrations?tag=rights", "/api/demonstrations?organization_id=66fa58601102367d5d52887f"} {
		if key(path, now).key == first.key {
			t.Fatal("different scope shared cache", path)
		}
	}
	if first.key == key("/api/demonstrations?search=test&city=helsinki,tampere", now.Add(24*time.Hour)).key {
		t.Fatal("day boundary omitted")
	}
	late := time.Date(2026, 11, 2, 21, 59, 55, 0, time.UTC)
	if responseLifetime(first, late) != 5 {
		t.Fatal("shared TTL crosses Helsinki midnight")
	}
	if key("/api/demonstrations/example", now).key == key("/api/demonstrations/example?lang=fi", now).key {
		t.Fatal("default language confused with Finnish")
	}
	for _, path := range []string{"/health", "/api/session", "/admin", "/api/demonstrations?unknown=1", "/api/home?lang=en&lang=sv"} {
		if _, ok := publicResponsePolicy(httptest.NewRequest("GET", path, nil), now); ok {
			t.Fatal("invalid/private route cached", path)
		}
	}
}

func TestSharedResponseCachePreservesListingHTTPContract(t *testing.T) {
	cache, _ := testResponseCache(t)
	source := &fakeListingStore{}
	handler := publicResponseCache((&API{source}).handler(), cache)
	for _, query := range []string{"city=Helsinki&per_page=12", "per_page=12&city=helsinki"} {
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest("GET", "/api/demonstrations?"+query, nil))
		if w.Code != 200 || !strings.Contains(w.Body.String(), `"per_page":12`) {
			t.Fatal(w.Code, w.Body)
		}
	}
	if source.loads.Load() != 1 {
		t.Fatal("equivalent HTTP queries did not share Redis")
	}
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, httptest.NewRequest("GET", "/api/demonstrations?per_page=12&city=helsinki&page=2", nil))
	if source.loads.Load() != 2 || !strings.Contains(w.Body.String(), `"page":2`) {
		t.Fatal("pagination collapsed", w.Body)
	}
}

func TestSharedResponseCacheCrossInstanceHEADAgeAndETag(t *testing.T) {
	cache, server := testResponseCache(t)
	other, err := newRedisResponseCache("redis://"+server.Addr()+"/0", t.Name())
	if err != nil {
		t.Fatal(err)
	}
	defer other.client.Close()
	calls := 0
	loader := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.Method != "GET" {
			t.Fatal("HEAD miss did not load GET")
		}
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", "public, max-age=30")
		_, _ = w.Write([]byte("{\"events\":[]}\n"))
	})
	read := func(handler http.Handler, method, etag string) *httptest.ResponseRecorder {
		r := httptest.NewRequest(method, "/api/home", nil)
		r.Header.Set("If-None-Match", etag)
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, r)
		return w
	}
	head := read(publicResponseCache(loader, cache), "HEAD", "")
	get := read(publicResponseCache(loader, other), "GET", "")
	if calls != 1 || head.Body.Len() != 0 || get.Body.String() != "{\"events\":[]}\n" {
		t.Fatal("shared representation or HEAD contract lost")
	}
	if get.Header().Get("Cache-Control") != "public, max-age=60, s-maxage=300" {
		t.Fatal(get.Header())
	}
	validated := read(publicResponseCache(loader, other), "GET", "W/"+get.Header().Get("ETag"))
	if validated.Code != 304 || validated.Body.Len() != 0 || calls != 1 {
		t.Fatal("conditional hit reloaded data")
	}
	policy, _ := publicResponsePolicy(httptest.NewRequest("GET", "/api/home", nil), time.Now())
	cache.put(context.Background(), policy.key, cachedResponse{Body: []byte(`{"events":[]}`), Stored: time.Now().Add(-70 * time.Second).Unix(), Lifetime: 300})
	aged := read(publicResponseCache(loader, other), "GET", "")
	age, _ := strconv.Atoi(aged.Header().Get("Age"))
	if age < 70 || age > 72 {
		t.Fatal("CDN freshness restarted", aged.Header())
	}
	server.FastForward(6 * time.Minute)
	read(publicResponseCache(loader, other), "GET", "")
	if calls != 2 {
		t.Fatal("expired response did not reload")
	}
}

func TestSharedResponseCacheBypassesUnsafeAndOversizeResponses(t *testing.T) {
	for _, control := range []string{"no-store", "private, max-age=300", "no-cache", "cookie", "vary", "error", "oversize"} {
		t.Run(control, func(t *testing.T) {
			cache, _ := testResponseCache(t)
			calls := 0
			h := publicResponseCache(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				calls++
				w.Header().Set("Content-Type", "application/json")
				w.Header().Set("Cache-Control", control)
				if control == "cookie" {
					w.Header().Set("Set-Cookie", "private=1")
				}
				if control == "vary" {
					w.Header().Set("Vary", "Cookie")
				}
				if control == "error" {
					w.WriteHeader(503)
				}
				body := `{"ok":true}`
				if control == "oversize" {
					body = `"` + strings.Repeat("x", responseMaxBytes) + `"`
				}
				_, _ = w.Write([]byte(body))
			}), cache)
			for range 2 {
				w := httptest.NewRecorder()
				h.ServeHTTP(w, httptest.NewRequest("GET", "/api/home", nil))
				if control == "oversize" && w.Body.Len() != responseMaxBytes+2 {
					t.Fatal("streamed body was truncated")
				}
				if control == "error" && (w.Code != 503 || w.Header().Get("Cache-Control") != "no-store") {
					t.Fatal("error cached")
				}
			}
			if calls != 2 {
				t.Fatal("unsafe response was shared")
			}
		})
	}
}

func TestSharedResponseCacheBoundAndRedisOutage(t *testing.T) {
	cache, server := testResponseCache(t)
	for i := range 270 {
		cache.put(context.Background(), strconv.Itoa(i), cachedResponse{Body: []byte(`{}`), Stored: time.Now().Unix(), Lifetime: 300})
	}
	if len(server.Keys()) > 257 {
		t.Fatal("Redis namespace grew beyond budget", len(server.Keys()))
	}
	server.Close()
	calls := 0
	h := publicResponseCache(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", "public")
		_, _ = w.Write([]byte(`{}`))
	}), cache)
	for range 2 {
		w := httptest.NewRecorder()
		h.ServeHTTP(w, httptest.NewRequest("GET", "/api/home", nil))
		if w.Code != 200 {
			t.Fatal("Redis outage broke API", w.Code)
		}
	}
	if calls != 2 || cache.unavailableUntil.Load() <= time.Now().UnixNano() {
		t.Fatal("Redis outage did not fail open with backoff")
	}
}
