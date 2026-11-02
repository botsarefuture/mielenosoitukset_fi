package main

import (
	"context"
	"encoding/json"
	"errors"
	"go.mongodb.org/mongo-driver/v2/bson"
	"strconv"

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
	ResolvePublicID(context.Context, string) (bson.ObjectID, error)
	Ping(context.Context) error
}
type mongoStore struct {
	collection *mongo.Collection
	client     *mongo.Client
}

// publicVisibility is the single definition of what a public event is. Callers
// combine it with the identity they resolved, so an alias can never widen it.
func publicVisibility() bson.M {
	return bson.M{"approved": true, "$expr": bson.M{"$and": bson.A{
		bson.M{"$eq": bson.A{bson.M{"$type": "$approved"}, "bool"}},
		bson.M{"$in": bson.A{bson.M{"$type": "$hide"}, bson.A{"missing", "bool"}}},
		bson.M{"$in": bson.A{bson.M{"$type": "$rejected"}, bson.A{"missing", "bool"}}},
	}}, "$and": bson.A{
		bson.M{"$or": bson.A{bson.M{"hide": bson.M{"$exists": false}}, bson.M{"hide": false}}},
		bson.M{"$or": bson.A{bson.M{"rejected": bson.M{"$exists": false}}, bson.M{"rejected": false}}},
	}}
}

func publicFilter(id bson.ObjectID) bson.M {
	filter := publicVisibility()
	filter["_id"] = id
	return filter
}

// errInvalidIdentifier marks input that cannot be any supported identifier.
var errInvalidIdentifier = errors.New("invalid identifier")

func validIdentifier(raw string) bool {
	if raw == "" || len(raw) > 200 {
		return false
	}
	for _, r := range raw {
		if !(r >= 'a' && r <= 'z' || r >= 'A' && r <= 'Z' || r >= '0' && r <= '9' || r == '-') {
			return false
		}
	}
	return true
}

func (s mongoStore) resolveID(ctx context.Context, filter bson.M) (bson.ObjectID, error) {
	var result struct {
		ID bson.ObjectID `bson:"_id"`
	}
	err := s.collection.FindOne(ctx, filter, options.FindOne().SetProjection(bson.M{"_id": 1})).Decode(&result)
	return result.ID, err
}

// ResolvePublicID mirrors the site's long-standing identifier precedence:
// ObjectId, then alias, then running number, then slug. A nonpublic original
// never resolves through one of its aliases.
func (s mongoStore) ResolvePublicID(ctx context.Context, raw string) (bson.ObjectID, error) {
	if !validIdentifier(raw) {
		return bson.NilObjectID, errInvalidIdentifier
	}
	if id, err := bson.ObjectIDFromHex(raw); err == nil {
		// Public ObjectIds are the common path: resolve them in one indexed read.
		if resolved, err := s.resolveID(ctx, publicFilter(id)); !errors.Is(err, mongo.ErrNoDocuments) {
			return resolved, err
		}
		var probe struct {
			ID bson.ObjectID `bson:"_id"`
		}
		err := s.collection.FindOne(ctx, bson.M{"_id": id}, options.FindOne().SetProjection(bson.M{"_id": 1})).Decode(&probe)
		if err == nil {
			// A nonpublic original still prevents fallback through an alias.
			return bson.NilObjectID, mongo.ErrNoDocuments
		}
		if !errors.Is(err, mongo.ErrNoDocuments) {
			return bson.NilObjectID, err
		}
		filter := publicVisibility()
		filter["aliases"] = id
		if resolved, err := s.resolveID(ctx, filter); !errors.Is(err, mongo.ErrNoDocuments) {
			return resolved, err
		}
	}
	if runningNumber, err := strconv.Atoi(raw); err == nil && len(raw) <= 18 && runningNumber >= 0 {
		filter := publicVisibility()
		filter["running_number"] = runningNumber
		if resolved, err := s.resolveID(ctx, filter); !errors.Is(err, mongo.ErrNoDocuments) {
			return resolved, err
		}
	}
	filter := publicVisibility()
	filter["slug"] = raw
	return s.resolveID(ctx, filter)
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
	mux.HandleFunc("GET /api/demonstrations", a.getListing)
	mux.HandleFunc("GET /api/cities", a.getCities)
	mux.HandleFunc("GET /api/demonstrations/{id}", a.getDemonstrationCached)
	mux.HandleFunc("GET /api/series/{parent}", a.getSeries)
	mux.HandleFunc("GET /api/organizations/{id}", a.getOrganization)
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
	lang, err := parseQuery(r.URL.RawQuery)
	if err != nil {
		writeError(w, 400, "invalid query parameters")
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
	defer cancel()
	id, err := a.store.ResolvePublicID(ctx, r.PathValue("id"))
	if errors.Is(err, errInvalidIdentifier) {
		writeError(w, 400, "invalid demonstration ID")
		return
	}
	if errors.Is(err, mongo.ErrNoDocuments) {
		writeError(w, 404, "demonstration not found")
		return
	}
	if err != nil {
		log.Print("Demonstration identifier lookup failed")
		writeError(w, 503, "service unavailable")
		return
	}
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
	var shared responseCache
	if rawURL := os.Getenv("PUBLIC_REDIS_URL"); rawURL != "" {
		source, err := publicCacheSource(uri, database)
		if err != nil {
			log.Fatal("Public Redis cache source is invalid")
		}
		redisCache, err := newRedisResponseCache(rawURL, source)
		if err != nil {
			log.Fatal("Public Redis cache configuration is invalid")
		}
		defer redisCache.client.Close()
		shared = redisCache
	}

	submissionConfig, err := submissionConfigFromEnv()
	if err != nil {
		log.Fatal("Public submission configuration is invalid")
	}
	handler := publicSubmissionHandler(publicResponseCache(a.handler(), shared), client.Database(database), submissionConfig)
	if submissionConfig.Origin != "" {
		indexContext, cancelIndexCheck := context.WithTimeout(context.Background(), 3*time.Second)
		indexError := checkSubmissionIndexes(indexContext, client.Database(database))
		cancelIndexCheck()
		if indexError != nil {
			log.Fatal("Existing unique submission token index is required before enabling writes")
		}
		recoveryContext, stopRecovery := context.WithCancel(context.Background())
		defer stopRecovery()
		go runSubmissionRecovery(recoveryContext, client.Database(database))
	}
	server := &http.Server{Addr: env("API_ADDR", "127.0.0.1:8080"), Handler: handler, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 30 * time.Second, WriteTimeout: 30 * time.Second, IdleTimeout: 60 * time.Second, MaxHeaderBytes: 16 * 1024}
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
