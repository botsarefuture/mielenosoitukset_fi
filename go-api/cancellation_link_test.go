package main

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
)

var cancellationNow = time.Date(2026, 11, 12, 12, 0, 0, 0, time.UTC)

func readyRecord() cancellationLinkRecord {
	return cancellationLinkRecord{Found: true, DemoFound: true, Expires: time.Date(2100, 1, 1, 0, 0, 0, 0, time.UTC),
		Demo: bson.M{"title": "Marssi", "date": "2026-12-01", "city": "Turku"}}
}

func TestCancellationLinkStatusFollowsFlaskPrecedence(t *testing.T) {
	cases := []struct {
		name   string
		change func(*cancellationLinkRecord)
		want   string
	}{
		{"unknown", func(r *cancellationLinkRecord) { r.Found = false }, "invalid"},
		{"ready", func(r *cancellationLinkRecord) {}, "ready"},
		{"expired", func(r *cancellationLinkRecord) { r.Expires = cancellationNow.Add(-time.Second) }, "expired"},
		{"no expiry is valid", func(r *cancellationLinkRecord) { r.Expires = time.Time{} }, "ready"},
		{"used", func(r *cancellationLinkRecord) { r.Used = true }, "used"},
		{"used beats expired", func(r *cancellationLinkRecord) { r.Used = true; r.Expires = cancellationNow.Add(-time.Hour) }, "used"},
		{"missing demonstration beats used", func(r *cancellationLinkRecord) { r.Used = true; r.DemoFound = false }, "missing-demonstration"},
	}
	for _, c := range cases {
		record := readyRecord()
		c.change(&record)
		got := cancellationLinkStatus(record, cancellationNow)
		if got.State != c.want {
			t.Fatal(c.name, got.State)
		}
		if got.State != "ready" && (got.Demo != nil || got.CanCancelDirectly || got.CancellationPending) {
			t.Fatal(c.name, "leaks demonstration data")
		}
	}
}

func TestCancellationLinkStatusReadyFields(t *testing.T) {
	record := readyRecord()
	record.Official = true
	record.Demo["cancelled"] = true
	record.Demo["cancellation_requested"] = true
	got := cancellationLinkStatus(record, cancellationNow)
	if got.Demo.Title != "Marssi" || got.Demo.Date != "01.12.2026" || got.Demo.City != "Turku" || !got.Demo.Cancelled ||
		!got.CancellationPending || !got.CanCancelDirectly {
		t.Fatalf("%+v %+v", got, got.Demo)
	}
}

func TestCancellationDate(t *testing.T) {
	for in, want := range map[any]string{
		"2026-12-01":          "01.12.2026",
		"2026-12-01T10:00:00": "01.12.2026",
		"huomenna":            "huomenna",
		bson.NewDateTimeFromTime(cancellationNow): "12.11.2026",
		nil: "",
	} {
		if got := cancellationDate(in); got != want {
			t.Fatal(in, got, want)
		}
	}
}

func TestCancellationLinkHandler(t *testing.T) {
	var hashes []string
	handler := cancellationLinkHandler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(204) }),
		func(_ context.Context, hash string) (cancellationLinkRecord, error) {
			hashes = append(hashes, hash)
			if strings.HasPrefix(hash, "fail") {
				return cancellationLinkRecord{}, errors.New("down")
			}
			return readyRecord(), nil
		})
	token := strings.Repeat("a", 43)
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, httptest.NewRequest("GET", cancellationLinkPrefix+token, nil))
	// sha256 of 43 "a" characters, never the token itself.
	if w.Code != 200 || w.Header().Get("Cache-Control") != "no-store" || !strings.Contains(w.Body.String(), `"state":"ready"`) {
		t.Fatal(w.Code, w.Body.String(), w.Header())
	}
	if len(hashes) != 1 || len(hashes[0]) != 64 || strings.Contains(hashes[0], "aaaa") {
		t.Fatal(hashes)
	}
	if strings.Contains(w.Body.String(), "email") || strings.Contains(w.Body.String(), "hash") {
		t.Fatal("private fields in response", w.Body.String())
	}
	for _, bad := range []string{"", "a/b", "a%20b", strings.Repeat("a", 129), "%C3%A4"} {
		hashes = nil
		w = httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest("GET", cancellationLinkPrefix+bad, nil))
		if w.Code != 200 || !strings.Contains(w.Body.String(), `"invalid"`) || len(hashes) != 0 {
			t.Fatal(bad, w.Code, w.Body.String(), hashes)
		}
	}
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, httptest.NewRequest("POST", cancellationLinkPrefix+token, nil))
	if w.Code != 405 {
		t.Fatal("post", w.Code)
	}
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, httptest.NewRequest("GET", "/api/home", nil))
	if w.Code != 204 || w.Header().Get("Cache-Control") != "" {
		t.Fatal("passthrough", w.Code)
	}
}

func TestCancellationLinkHandlerReadFailureIs503(t *testing.T) {
	handler := cancellationLinkHandler(http.NotFoundHandler(),
		func(context.Context, string) (cancellationLinkRecord, error) {
			return cancellationLinkRecord{}, errors.New("down")
		})
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, httptest.NewRequest("GET", cancellationLinkPrefix+"abc", nil))
	if w.Code != 503 || w.Header().Get("Cache-Control") != "no-store" {
		t.Fatal(w.Code)
	}
}
