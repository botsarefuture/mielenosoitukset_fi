package main

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestPublicGatePrecedesCachedResponsesAndPreservesHealth(t *testing.T) {
	for _, failed := range []bool{false, true} {
		calls, served := 0, 0
		handler := publicAvailability(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			served++
			w.WriteHeader(200)
		}), func(context.Context) (bool, error) {
			calls++
			if failed {
				return false, errors.New("database unavailable")
			}
			return true, nil
		})
		for _, path := range []string{"/api/home", "/api/demonstrations", "/api/submit"} {
			w := httptest.NewRecorder()
			handler.ServeHTTP(w, httptest.NewRequest("GET", path, nil))
			if w.Code != 503 || w.Header().Get("Cache-Control") != "no-store" {
				t.Fatal(path, w.Code)
			}
		}
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest("GET", "/health", nil))
		if served != 1 || calls != 1 || w.Code != 200 {
			t.Fatal(served, calls, w.Code)
		}
		w = httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest("GET", "/api/public-status", nil))
		if w.Code != 200 || w.Body.String() != "{\"available\":false}\n" {
			t.Fatal(w.Code, w.Body.String())
		}
	}
}

func TestPublicGateRidesOutBriefReadFailuresButNotLockdowns(t *testing.T) {
	now := time.Date(2026, 11, 9, 12, 0, 0, 0, time.UTC)
	clock = func() time.Time { return now }
	defer func() { clock = time.Now }()
	type answer struct {
		locked bool
		err    error
	}
	var next answer
	handler := publicAvailability(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(200) }),
		func(context.Context) (bool, error) { return next.locked, next.err })
	status := func() int {
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest("GET", "/api/home", nil))
		return w.Code
	}
	failed := errors.New("database unavailable")
	next = answer{err: failed}
	if status() != 503 {
		t.Fatal("a failed first read must fail closed")
	}
	now = now.Add(2 * time.Second)
	next = answer{}
	if status() != 200 {
		t.Fatal("an open read opens the site")
	}
	now = now.Add(2 * time.Second)
	next = answer{err: failed}
	if status() != 200 {
		t.Fatal("a failed read within the grace period keeps the last open answer")
	}
	now = now.Add(availabilityGrace)
	if status() != 503 {
		t.Fatal("a failure outlasting the grace period fails closed")
	}
	now = now.Add(2 * time.Second)
	next = answer{}
	status()
	now = now.Add(2 * time.Second)
	next = answer{locked: true}
	if status() != 503 {
		t.Fatal("an explicit lockdown applies at once, even within the grace period")
	}
	now = now.Add(2 * time.Second)
	next = answer{err: failed}
	if status() != 503 {
		t.Fatal("a failed read after a lockdown must not reopen the site")
	}
}
