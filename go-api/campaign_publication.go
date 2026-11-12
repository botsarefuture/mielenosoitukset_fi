package main

import (
	"context"
	"net/http"
	"sync"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
)

const campaignPublicationPath = "/api/campaign/publication"

// campaignPublication answers whether the volunteer campaign page is public,
// mirroring Flask's campaign_pages_public(): only an explicit published: true
// counts, and a failed read reports the page as private. One coalesced read per
// second per process, outside the response caches, like the lockdown gate.
func campaignPublication(next http.Handler, read func(context.Context) (bool, error)) http.Handler {
	var mu sync.Mutex
	var checked time.Time
	var published bool
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != campaignPublicationPath {
			next.ServeHTTP(w, r)
			return
		}
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			writeError(w, http.StatusMethodNotAllowed, "method not allowed")
			return
		}
		mu.Lock()
		if time.Since(checked) >= time.Second {
			ctx, cancel := context.WithTimeout(r.Context(), time.Second)
			value, err := read(ctx)
			cancel()
			published = err == nil && value
			checked = time.Now()
		}
		current := published
		mu.Unlock()
		w.Header().Set("Cache-Control", "no-store")
		writeJSON(w, http.StatusOK, map[string]bool{"published": current})
	})
}

func readCampaignPublication(db *mongo.Database) func(context.Context) (bool, error) {
	return func(ctx context.Context) (bool, error) {
		var state struct {
			Published any `bson:"published"`
		}
		err := db.Collection("campaign_settings").FindOne(ctx, bson.M{"_id": "public_pages"}).Decode(&state)
		if err == mongo.ErrNoDocuments {
			return false, nil
		}
		if err != nil {
			return false, err
		}
		value, ok := state.Published.(bool)
		return ok && value, nil
	}
}
