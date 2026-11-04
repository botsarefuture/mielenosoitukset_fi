package main

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
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
