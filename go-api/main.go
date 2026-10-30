package main

import (
	"context"
	"encoding/json"
	"errors"
	"go.mongodb.org/mongo-driver/v2/bson"

	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

// buildSHA is set by the release build, never read from a mutable checkout.
var buildSHA = "development"

type Store interface {
	FindPublic(context.Context, bson.ObjectID) (bson.M, error)
	Ping(context.Context) error
}
type mongoStore struct {
	collection *mongo.Collection
	client     *mongo.Client
}

func publicFilter(id bson.ObjectID) bson.M {
	return bson.M{"_id": id, "approved": true, "$expr": bson.M{"$and": bson.A{
		bson.M{"$eq": bson.A{bson.M{"$type": "$approved"}, "bool"}},
		bson.M{"$in": bson.A{bson.M{"$type": "$hide"}, bson.A{"missing", "bool"}}},
		bson.M{"$in": bson.A{bson.M{"$type": "$rejected"}, bson.A{"missing", "bool"}}},
	}}, "$and": bson.A{
		bson.M{"$or": bson.A{bson.M{"hide": bson.M{"$exists": false}}, bson.M{"hide": false}}},
		bson.M{"$or": bson.A{bson.M{"rejected": bson.M{"$exists": false}}, bson.M{"rejected": false}}},
	}}
}
func (s mongoStore) FindPublic(ctx context.Context, id bson.ObjectID) (bson.M, error) {
	var doc bson.M
	err := s.collection.FindOne(ctx, publicFilter(id), options.FindOne().SetProjection(publicProjection())).Decode(&doc)
	return doc, err
}

func (s mongoStore) Ping(ctx context.Context) error { return s.client.Ping(ctx, nil) }

type API struct{ store Store }

func (a *API) handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/demonstrations/{id}", a.getDemonstrationCached)
	mux.HandleFunc("GET /api/home", a.getHomeCached)
	mux.HandleFunc("GET /health", a.health)
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) { writeError(w, 404, "not found") })
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		// Default for everything; the cached handlers override it per response.
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		if r.Method == http.MethodOptions {
			w.Header().Set("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
			w.WriteHeader(204)
			return
		}
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			w.Header().Set("Allow", "GET, HEAD, OPTIONS")
			writeError(w, 405, "method not allowed")
			return
		}
		mux.ServeHTTP(w, r)
	})
}

// Original uncached handler, still used as the fallback when the store is not
// the cache (for example a test fake).
func (a *API) getDemonstration(w http.ResponseWriter, r *http.Request) {
	id, err := bson.ObjectIDFromHex(r.PathValue("id"))
	if err != nil {
		writeError(w, 400, "invalid demonstration ID")
		return
	}
	lang, err := parseQuery(r.URL.RawQuery)
	if err != nil {
		writeError(w, 400, "invalid query parameters")
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
	defer cancel()
	doc, err := a.store.FindPublic(ctx, id)
	if errors.Is(err, mongo.ErrNoDocuments) {
		writeError(w, 404, "demonstration not found")
		return
	}
	if err != nil {
		log.Print("Demonstration database read failed")
		writeError(w, 503, "service unavailable")
		return
	}
	writeJSON(w, 200, publicPayload(doc, lang))
}
func (a *API) health(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), time.Second)
	defer cancel()
	if a.store.Ping(ctx) != nil {
		writeError(w, 503, "service unavailable")
		return
	}
	writeJSON(w, 200, map[string]string{"status": "ok", "build_sha": buildSHA})
}
func main() {
	uri, database := os.Getenv("MONGODB_URI"), os.Getenv("MONGODB_DATABASE")
	if uri == "" || database == "" {
		log.Fatal("MONGODB_URI and MONGODB_DATABASE are required")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	client, err := mongo.Connect(options.Client().ApplyURI(uri).SetMaxPoolSize(20).SetServerSelectionTimeout(3 * time.Second))
	if err == nil {
		err = client.Ping(ctx, nil)
	}
	cancel()
	if err != nil {
		log.Fatal("MongoDB connection unavailable")
	}
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = client.Disconnect(ctx)
	}()

	// Deferred after the Disconnect above, so it runs first: background loads
	// stop before the client closes.
	cache := newCachedDetailStore(mongoStore{client.Database(database).Collection("demonstrations"), client})
	defer cache.Close()
	if err := cache.StartBatchRefresh(); err != nil {
		log.Print("Batch refresh disabled: ", err)
	}
	a := &API{store: cache}

	server := &http.Server{Addr: env("API_ADDR", "127.0.0.1:8080"), Handler: a.handler(), ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 60 * time.Second, MaxHeaderBytes: 16 * 1024}
	shutdownDone := make(chan struct{})
	stopped := make(chan os.Signal, 1)
	signal.Notify(stopped, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-stopped
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = server.Shutdown(ctx)
		close(shutdownDone)
	}()
	log.Printf("Public API listening on %s", server.Addr)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatal("HTTP server failed")
	}
	<-shutdownDone
}
func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}
func writeJSON(w http.ResponseWriter, status int, value any) {
	data, err := json.Marshal(value)
	if err != nil {
		status = 500
		data = []byte(`{"error":"response unavailable"}`)
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_, _ = w.Write(append(data, '\n'))
}
func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
