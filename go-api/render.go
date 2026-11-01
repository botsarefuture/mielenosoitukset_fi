package main

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
)

// Cache-Control values for Cloudflare and browsers. s-maxage is what the CDN
// obeys; max-age is what browsers obey. The demo route is long-lived (the
// in-process cache refreshes it in batches), the home route is short-lived.
const (
	demoCacheControl     = "public, max-age=60, s-maxage=900, stale-while-revalidate=3600, stale-if-error=86400"
	homeCacheControl     = "public, max-age=30, s-maxage=60, stale-while-revalidate=120, stale-if-error=900"
	notFoundCacheControl = "public, max-age=30, s-maxage=60"
)

// detailJSONStore is implemented by *cachedDetailStore. Stores that don't
// implement it (e.g. test fakes) fall back to the original handlers.
type detailJSONStore interface {
	FindPublicJSON(ctx context.Context, id bson.ObjectID, lang string, render func(bson.M, string) ([]byte, error)) ([]byte, error)
}

// renderDemonstration builds the final response bytes for one language. The
// cache runs it once per entry per language and memoizes the result.
func renderDemonstration(doc bson.M, lang string) ([]byte, error) {
	data, err := json.Marshal(publicPayload(doc, lang))
	if err != nil {
		return nil, err
	}
	return append(data, '\n'), nil
}

func writeJSONBytes(w http.ResponseWriter, status int, data []byte) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_, _ = w.Write(data)
}

func (a *API) getDemonstrationCached(w http.ResponseWriter, r *http.Request) {
	cached, ok := a.store.(detailJSONStore)
	if !ok {
		a.getDemonstration(w, r)
		return
	}
	id, err := bson.ObjectIDFromHex(r.PathValue("id"))
	if err != nil {
		writeError(w, 400, "invalid demonstration ID") // no cache, no DB
		return
	}
	lang, err := parseQuery(r.URL.RawQuery)
	if err != nil {
		writeError(w, 400, "invalid query parameters")
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
	defer cancel()
	data, err := cached.FindPublicJSON(ctx, id, lang, renderDemonstration)
	switch {
	case err == nil:
		w.Header().Set("Cache-Control", demoCacheControl)
		writeJSONBytes(w, 200, data)
	case errors.Is(err, mongo.ErrNoDocuments):
		w.Header().Set("Cache-Control", notFoundCacheControl)
		writeError(w, 404, "demonstration not found")
	default:
		log.Print("Demonstration database read failed")
		writeError(w, 503, "service unavailable") // stays no-store
	}
}

func (a *API) getHomeCached(w http.ResponseWriter, r *http.Request) {
	cached, ok := a.store.(homeJSONStore)
	if !ok {
		a.getHome(w, r)
		return
	}
	lang, err := parseQuery(r.URL.RawQuery)
	if err != nil {
		writeError(w, 400, "invalid query parameters")
		return
	}
	if lang == "" {
		lang = "fi"
	}
	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
	defer cancel()
	data, err := cached.FindHomeJSON(ctx, lang)
	if err != nil {
		log.Print("Home database read failed")
		writeError(w, 503, "service unavailable")
		return
	}
	w.Header().Set("Cache-Control", homeCacheControl)
	writeJSONBytes(w, 200, data)
}
