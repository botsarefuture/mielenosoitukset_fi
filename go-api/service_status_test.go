package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestServiceStatusCachesFailuresAndRecovers(t *testing.T) {
	now := time.Date(2026, 11, 10, 12, 0, 0, 0, time.UTC)
	clock = func() time.Time { return now }
	defer func() { clock = time.Now }()
	calls := 0
	var failure error = errors.New("private-host: secret connection string and stack trace")
	handler := serviceStatusHandler(func(ctx context.Context) error {
		calls++
		deadline, ok := ctx.Deadline()
		if !ok || time.Until(deadline) > time.Second {
			t.Fatal("probe must have a short deadline")
		}
		return failure
	})
	get := func(path string) serviceStatus {
		t.Helper()
		recorder := httptest.NewRecorder()
		handler.ServeHTTP(recorder, httptest.NewRequest("GET", path, nil))
		if recorder.Code != 200 || recorder.Header().Get("Cache-Control") != "no-store" || strings.Contains(recorder.Body.String(), "private-host") {
			t.Fatal(recorder.Code, recorder.Body.String(), recorder.Header())
		}
		var result serviceStatus
		if err := json.Unmarshal(recorder.Body.Bytes(), &result); err != nil {
			t.Fatal(err)
		}
		if len(result.Services) != 1 || result.Services[0].Name != "Tietokanta" || result.LatencyMS < 0 {
			t.Fatal(result)
		}
		if _, err := time.Parse("02.01.2006 15:04:05 UTC", result.UpdatedAt); err != nil {
			t.Fatal(err)
		}
		return result
	}
	if result := get("/api/status"); result.OverallOK || result.Services[0].Message != "Ei vastaa" {
		t.Fatal(result)
	}
	failure = nil
	for _, path := range []string{"/api/status?force_reload=1", "/api/status?lang=sv"} {
		if get(path).OverallOK {
			t.Fatal("query parameters must not bypass cached failure")
		}
	}
	if calls != 1 {
		t.Fatal(calls)
	}
	now = now.Add(time.Minute)
	if result := get("/api/status"); !result.OverallOK || result.Services[0].Message != "Yhteys kunnossa" || calls != 2 {
		t.Fatal(result, calls)
	}
}

func TestServiceStatusCoalescesConcurrentProbes(t *testing.T) {
	var calls atomic.Int32
	handler := serviceStatusHandler(func(context.Context) error { calls.Add(1); return nil })
	var requests sync.WaitGroup
	for range 30 {
		requests.Go(func() {
			handler.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/api/status", nil))
		})
	}
	requests.Wait()
	if calls.Load() != 1 {
		t.Fatal(calls.Load())
	}
}

func TestServiceStatusProbeTimeout(t *testing.T) {
	handler := serviceStatusHandler(func(ctx context.Context) error {
		<-ctx.Done()
		return ctx.Err()
	})
	started := time.Now()
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, httptest.NewRequest("GET", "/api/status", nil))
	if recorder.Code != 200 || time.Since(started) > 2*time.Second || !strings.Contains(recorder.Body.String(), `"status":"err"`) {
		t.Fatal(recorder.Code, recorder.Body.String(), time.Since(started))
	}
}

func TestServiceStatusRemainsReadOnlyAndBypassesLockdown(t *testing.T) {
	api := &API{store: &fakeStore{err: errors.New("unavailable")}}
	handler := publicAvailability(api.handler(), func(context.Context) (bool, error) {
		t.Fatal("status must not read the lockdown collection")
		return true, nil
	})
	for method, expected := range map[string]int{"GET": 200, "HEAD": 200, "POST": 405, "PUT": 405, "DELETE": 405, "OPTIONS": 204} {
		recorder := httptest.NewRecorder()
		handler.ServeHTTP(recorder, httptest.NewRequest(method, "/api/status", nil))
		if recorder.Code != expected {
			t.Fatal(method, recorder.Code)
		}
		if (method == "HEAD" || method == "OPTIONS") && recorder.Body.Len() != 0 {
			t.Fatal(method, recorder.Body.String())
		}
	}
}
