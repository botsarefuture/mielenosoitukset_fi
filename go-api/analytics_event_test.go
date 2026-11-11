package main

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"reflect"
	"strings"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

func TestAnalyticsEvent(t *testing.T) {
	cases := []struct {
		name, body, contentType, referrer, userAgent string
		headers                                      map[string]string
		disabled, skip                               bool
		resource, device, referral                   string
	}{
		{name: "map", body: `{"event":"map_interaction","resource_id":" /demo "}`, resource: "/demo"},
		{name: "external", body: `{"event":"external_link","resource_id":"example.org","ignored":true}`, resource: "example.org"},
		{name: "form first value", body: "event=map_interaction&resource_id=first&resource_id=second", contentType: "application/x-www-form-urlencoded", resource: "first"},
		{name: "multipart form", body: "--beacon\r\nContent-Disposition: form-data; name=\"event\"\r\n\r\nmap_interaction\r\n--beacon--\r\n", contentType: "multipart/form-data; boundary=beacon"},
		{name: "search", body: `{"event":" demo_search ","resource_id":" climate "}`, referrer: "https://site.test/demonstrations?search=climate", resource: "climate", referral: "internal"},
		{name: "city search", body: `{"event":"demo_search","resource_id":"ab"}`, referrer: "https://site.test/city/Helsinki/tanaan", resource: "ab", referral: "internal"},
		{name: "unknown", body: `{"event":"demo_submitted"}`, skip: true},
		{name: "array", body: `[]`, skip: true},
		{name: "null", body: `null`, skip: true},
		{name: "broken JSON", body: `{`, skip: true},
		{name: "trailing JSON", body: `{"event":"map_interaction"}{}`, skip: true},
		{name: "bad UTF8", body: "{\"event\":\"map_interaction\",\"resource_id\":\"\xff\"}", skip: true},
		{name: "text plain", body: `{"event":"map_interaction"}`, contentType: "text/plain", skip: true},
		{name: "vendor JSON", body: `{"event":"map_interaction"}`, contentType: "application/vnd.test+json"},
		{name: "cross host", body: `{"event":"map_interaction"}`, referrer: "https://evil.test/", skip: true},
		{name: "malformed referer", body: `{"event":"map_interaction"}`, referrer: "https://[bad", skip: true},
		{name: "map hostname only", body: `{"event":"map_interaction"}`, referrer: "http://site.test:99/", referral: "internal"},
		{name: "map ignores fetch metadata and origin", body: `{"event":"map_interaction"}`, headers: map[string]string{"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.test"}},
		{name: "search missing referer", body: `{"event":"demo_search","resource_id":"ab"}`, skip: true},
		{name: "search too short", body: `{"event":"demo_search","resource_id":"a"}`, referrer: "https://site.test/cities", skip: true},
		{name: "search wrong scheme", body: `{"event":"demo_search","resource_id":"ab"}`, referrer: "http://site.test/cities", skip: true},
		{name: "search wrong port", body: `{"event":"demo_search","resource_id":"ab"}`, referrer: "https://site.test:443/cities", skip: true},
		{name: "search cross site", body: `{"event":"demo_search","resource_id":"ab"}`, referrer: "https://site.test/cities", headers: map[string]string{"Sec-Fetch-Site": "cross-site"}, skip: true},
		{name: "pride search excluded", body: `{"event":"demo_search","resource_id":"ab"}`, referrer: "https://site.test/pride-nakyvaksi", skip: true},
		{name: "encoded listing excluded", body: `{"event":"demo_search","resource_id":"ab"}`, referrer: "https://site.test/%63ities", skip: true},
		{name: "trailing slash excluded", body: `{"event":"demo_search","resource_id":"ab"}`, referrer: "https://site.test/cities/", skip: true},
		{name: "bot", body: `{"event":"map_interaction"}`, userAgent: "Mozilla Googlebot", skip: true},
		{name: "DNT", body: `{"event":"map_interaction"}`, headers: map[string]string{"DNT": "1"}, skip: true},
		{name: "DNT zero", body: `{"event":"map_interaction"}`, headers: map[string]string{"DNT": "0"}},
		{name: "disabled", body: `{"event":"map_interaction"}`, disabled: true, skip: true},
		{name: "prefetch still counts", body: `{"event":"map_interaction"}`, headers: map[string]string{"Purpose": "prefetch", "Sec-Purpose": "prefetch;prerender"}},
		{name: "mobile before tablet", body: `{"event":"map_interaction"}`, userAgent: "Android Mobile Tablet", device: "mobile"},
		{name: "tablet", body: `{"event":"map_interaction"}`, userAgent: "iPad Macintosh", device: "tablet"},
		{name: "desktop", body: `{"event":"map_interaction"}`, userAgent: "Mozilla X11 Linux", device: "desktop"},
		{name: "unicode cap", body: `{"event":"external_link","resource_id":"` + strings.Repeat("ä", 201) + `"}`, resource: strings.Repeat("ä", 200)},
		{name: "no proposed 1024 byte cap", body: `{"event":"map_interaction","ignored":"` + strings.Repeat("x", 2048) + `"}`},
		{name: "false resource omitted", body: `{"event":"map_interaction","resource_id":false}`},
		{name: "numeric resource", body: `{"event":"map_interaction","resource_id":123}`, resource: "123"},
		{name: "float resource", body: `{"event":"map_interaction","resource_id":1e2}`, resource: "100.0"},
		{name: "zero resource omitted", body: `{"event":"map_interaction","resource_id":0e2}`},
		{name: "duplicate structured keys", body: `{"event":"map_interaction","resource_id":{"x":1,"x":2}}`, resource: "{'x': 2}"},
		{name: "structured resource", body: `{"event":"map_interaction","resource_id":{"key":[true,null,"x"]}}`, resource: "{'key': [True, None, 'x']}"},
	}
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			var got bson.M
			handler := analyticsEventHandler(http.NotFoundHandler(), !test.disabled, func(ctx context.Context, key bson.M) error {
				if _, ok := ctx.Deadline(); !ok {
					t.Fatal("missing write deadline")
				}
				got = key
				return nil
			})
			request := httptest.NewRequest("POST", "https://site.test/api/analytics/event", strings.NewReader(test.body))
			contentType := test.contentType
			if contentType == "" {
				contentType = "application/json"
			}
			request.Header.Set("Content-Type", contentType)
			request.Header.Set("Referer", test.referrer)
			request.Header.Set("User-Agent", test.userAgent)
			for name, value := range test.headers {
				request.Header.Set(name, value)
			}
			response := httptest.NewRecorder()
			handler.ServeHTTP(response, request)
			if response.Code != 200 || response.Body.String() != "{\"ok\":true}\n" || response.Header().Get("Cache-Control") != "no-store" || response.Header().Get("Access-Control-Allow-Origin") != "" {
				t.Fatal(response.Code, response.Body.String(), response.Header())
			}
			if test.skip {
				if got != nil {
					t.Fatal("unexpected write", got)
				}
				return
			}
			device, referral := test.device, test.referral
			if device == "" {
				device = "other"
			}
			if referral == "" {
				referral = "direct"
			}
			if got == nil || got["device"] != device || got["referrer"] != referral || got["language"] != "fi" {
				t.Fatal(got)
			}
			if test.resource == "" {
				if _, ok := got["resource_id"]; ok {
					t.Fatal("empty resource must be absent", got)
				}
			} else if got["resource_id"] != test.resource {
				t.Fatal(got)
			}
		})
	}
}

func TestAnalyticsListingPathsAndProxy(t *testing.T) {
	for _, path := range []string{"/demonstrations", "/cities", "/mielenosoitukset-tanaan", "/submit", "/city/Helsinki", "/city/Helsinki/tanaan", "/tag/climate", "/organization/ABCDEF0123456789ABCDEF01"} {
		for _, peer := range []string{"127.0.0.1:1234", "[::1]:1234", "192.0.2.1:1234"} {
			t.Run(path+peer, func(t *testing.T) {
				request := httptest.NewRequest("POST", "http://upstream.test/api/analytics/event", strings.NewReader(`{"event":"demo_search","resource_id":"ab"}`))
				request.RemoteAddr = peer
				request.Header.Set("Content-Type", "application/json")
				request.Header.Set("X-Forwarded-Host", "ignored.test, site.test")
				request.Header.Set("X-Forwarded-Proto", "http, https")
				request.Header.Set("Referer", "https://site.test"+path)
				key := analyticsEventKey(request, time.Now())
				if (key != nil) != (peer != "192.0.2.1:1234") {
					t.Fatal(peer, path, key)
				}
			})
		}
	}
}

func TestAnalyticsSettingsFailClosed(t *testing.T) {
	for _, value := range []string{"", "false", "0", "1", "TRUE", "garbage", "true"} {
		t.Run(value, func(t *testing.T) {
			t.Setenv("SITE_ANALYTICS_ENABLED", value)
			if analyticsEnabledFromEnv() != (value == "true") {
				t.Fatal(value)
			}
		})
	}
}

func TestAnalyticsDispatchAndWriteFailure(t *testing.T) {
	handler := analyticsEventHandler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(418) }), true,
		func(context.Context, bson.M) error { return errors.New("private database error") })
	for _, test := range []struct{ method, path string }{{"GET", "/api/analytics/event"}, {"HEAD", "/api/analytics/event"}, {"OPTIONS", "/api/analytics/event"}, {"POST", "/api/analytics/event/"}, {"POST", "/api/analytics/pageview"}} {
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, httptest.NewRequest(test.method, test.path, nil))
		if response.Code != 418 {
			t.Fatal(test, response.Code)
		}
	}
	response := httptest.NewRecorder()
	request := httptest.NewRequest("POST", "https://site.test/api/analytics/event", strings.NewReader(`{"event":"map_interaction"}`))
	request.Header.Set("Content-Type", "application/json")
	handler.ServeHTTP(response, request)
	if response.Code != 200 || response.Body.String() != "{\"ok\":true}\n" {
		t.Fatal(response.Code, response.Body.String())
	}
}

func TestAnalyticsAggregateKeyHelsinkiDST(t *testing.T) {
	for _, test := range []struct {
		utc, date string
		hour      int
	}{
		{"2026-01-01T22:30:00Z", "2026-01-02", 0},
		{"2026-07-01T21:30:00Z", "2026-07-02", 0},
		{"2026-10-25T00:30:00Z", "2026-10-25", 3},
		{"2026-10-25T01:30:00Z", "2026-10-25", 3},
	} {
		request := httptest.NewRequest("POST", "https://site.test/api/analytics/event", strings.NewReader(`{"event":"map_interaction","resource_id":"/"}`))
		request.Header.Set("Content-Type", "application/json")
		moment, _ := time.Parse(time.RFC3339, test.utc)
		want := bson.M{"date": test.date, "hour": test.hour, "event": "map_interaction", "resource_id": "/", "device": "other", "language": "fi", "referrer": "direct"}
		if got := analyticsEventKey(request, moment); !reflect.DeepEqual(got, want) {
			t.Fatal(got, want)
		}
	}
}

func TestAnalyticsMongoCounter(t *testing.T) {
	uri := os.Getenv("TEST_MONGODB_URI")
	if uri == "" {
		t.Skip("set TEST_MONGODB_URI for isolated MongoDB integration")
	}
	client, err := mongo.Connect(options.Client().ApplyURI(uri))
	if err != nil {
		t.Fatal(err)
	}
	defer client.Disconnect(context.Background())
	db := client.Database("moso_go_api_test_" + bson.NewObjectID().Hex())
	defer db.Drop(context.Background())
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	key := bson.M{"date": "2026-11-11", "hour": 12, "event": "external_link", "language": "fi", "device": "desktop", "referrer": "internal", "resource_id": "example.org"}
	for range 2 {
		if err := incrementAnalyticsEvent(db)(ctx, key); err != nil {
			t.Fatal(err)
		}
	}
	var document bson.M
	if err := db.Collection("site_analytics").FindOne(ctx, key).Decode(&document); err != nil {
		t.Fatal(err)
	}
	if document["count"] != int32(2) || len(document) != len(key)+2 {
		t.Fatal(document)
	}
	count, err := db.Collection("site_analytics").CountDocuments(ctx, bson.M{})
	if err != nil || count != 1 {
		t.Fatal(count, err)
	}
	collections, err := db.ListCollectionNames(ctx, bson.M{})
	if err != nil || len(collections) != 1 || collections[0] != "site_analytics" {
		t.Fatal(collections, err)
	}
}
