package main

import (
	"context"
	"net/http"
	"sync"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
)

// availabilityGrace is how long a failed lockdown read keeps the last
// successful "not locked" answer. A lockdown that was read is applied at once.
const availabilityGrace = 30 * time.Second

// clock is replaceable in tests.
var clock = time.Now

// The gate is outside response caches, including Redis. One coalesced Mongo
// read per second per process bounds activation latency without a read per hit.
// A failed read is not a lockdown: within availabilityGrace of the last
// successful "not locked" read the site stays open; otherwise it fails closed,
// including right after start.
func publicAvailability(next http.Handler, read func(context.Context) (bool, error)) http.Handler {
	var mu sync.Mutex
	var checked, lastOpen time.Time
	var locked bool
	var readErr error
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/health" || r.URL.Path == "/api/status" {
			next.ServeHTTP(w, r)
			return
		}
		mu.Lock()
		if clock().Sub(checked) >= time.Second {
			ctx, cancel := context.WithTimeout(r.Context(), time.Second)
			locked, readErr = read(ctx)
			cancel()
			checked = clock()
			switch {
			case readErr != nil:
			case locked:
				// Never let a later failed read reopen a site that was locked.
				lastOpen = time.Time{}
			default:
				lastOpen = checked
			}
		}
		unavailable := locked
		if readErr != nil {
			unavailable = lastOpen.IsZero() || clock().Sub(lastOpen) > availabilityGrace
		}
		mu.Unlock()
		if r.URL.Path == "/api/public-status" {
			w.Header().Set("Cache-Control", "no-store")
			writeJSON(w, http.StatusOK, map[string]bool{"available": !unavailable})
			return
		}
		if unavailable {
			w.Header().Set("Cache-Control", "no-store")
			w.Header().Set("Retry-After", "60")
			writeError(w, http.StatusServiceUnavailable, "service temporarily unavailable")
			return
		}
		next.ServeHTTP(w, r)
	})
}

func readPublicLockdown(db *mongo.Database) func(context.Context) (bool, error) {
	return func(ctx context.Context) (bool, error) {
		count, err := db.Collection("panic").CountDocuments(ctx, bson.M{
			"name": bson.M{"$in": bson.A{"global", "security"}}, "panic": true,
		})
		return count > 0, err
	}
}
