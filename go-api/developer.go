package main

// Read-only data for the React /developer pages (docs/developer-react-proposal.md).
//
// The signed-in account comes from the auth bridge (Flask stays the authority),
// so these routes exist only when AUTH_BRIDGE_ENABLED=true. They return metadata
// for the caller's own apps and tokens. They never return a client secret, a
// token or a token hash, and every write (create, rotate, revoke, request scopes)
// stays in Flask.

import (
	"context"
	"errors"
	"log"
	"net/http"
	"strings"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

const (
	developerOverviewPath = "/api/developer/overview"
	developerAppPrefix    = "/api/developer/apps/"
	developerMaxItems     = 200
)

type developerApp struct {
	ID            string   `json:"id"`
	Name          string   `json:"name"`
	Description   string   `json:"description"`
	ClientID      string   `json:"client_id"`
	AllowedScopes []string `json:"allowed_scopes"`
	CreatedAt     string   `json:"created_at,omitempty"`
}

type developerToken struct {
	ID        string   `json:"id"`
	Type      string   `json:"type"`
	Scopes    []string `json:"scopes"`
	ExpiresAt string   `json:"expires_at,omitempty"`
	CreatedAt string   `json:"created_at,omitempty"`
}

type developerStore interface {
	AccessEnabled(ctx context.Context, user bson.ObjectID) (bool, error)
	Apps(ctx context.Context, owner bson.ObjectID) ([]developerApp, error)
	App(ctx context.Context, owner, id bson.ObjectID) (*developerApp, error)
	// Tokens returns metadata only. appID zero means the owner's personal tokens.
	Tokens(ctx context.Context, owner, appID bson.ObjectID) ([]developerToken, error)
}

type mongoDeveloperStore struct{ db *mongo.Database }

func (s mongoDeveloperStore) AccessEnabled(ctx context.Context, user bson.ObjectID) (bool, error) {
	var doc struct {
		Enabled bool `bson:"api_tokens_enabled"`
	}
	err := s.db.Collection("users").FindOne(ctx, bson.M{"_id": user},
		options.FindOne().SetProjection(bson.M{"api_tokens_enabled": 1})).Decode(&doc)
	if errors.Is(err, mongo.ErrNoDocuments) {
		return false, nil
	}
	return doc.Enabled, err
}

func isoTime(value any) string {
	if t, ok := value.(bson.DateTime); ok {
		return t.Time().UTC().Format(time.RFC3339)
	}
	return ""
}

func appFromDoc(doc bson.M) developerApp {
	app := developerApp{Name: stringField(doc, "name"), Description: stringField(doc, "description"),
		ClientID: stringField(doc, "client_id"), AllowedScopes: stringList(doc["allowed_scopes"], []string{"read"}),
		CreatedAt: isoTime(doc["created_at"])}
	if id, ok := doc["_id"].(bson.ObjectID); ok {
		app.ID = id.Hex()
	}
	return app
}

func stringField(doc bson.M, key string) string {
	if s, ok := doc[key].(string); ok {
		return s
	}
	return ""
}

func stringList(value any, fallback []string) []string {
	list, ok := value.(bson.A)
	if !ok {
		return fallback
	}
	out := []string{}
	for _, item := range list {
		if s, ok := item.(string); ok && len(out) < 50 {
			out = append(out, s)
		}
	}
	return out
}

func (s mongoDeveloperStore) Apps(ctx context.Context, owner bson.ObjectID) ([]developerApp, error) {
	cursor, err := s.db.Collection("developer_apps").Find(ctx, bson.M{"owner_id": owner},
		options.Find().SetLimit(developerMaxItems).SetSort(bson.M{"created_at": 1}).
			SetProjection(bson.M{"name": 1, "description": 1, "client_id": 1, "allowed_scopes": 1, "created_at": 1}))
	if err != nil {
		return nil, err
	}
	var docs []bson.M
	if err := cursor.All(ctx, &docs); err != nil {
		return nil, err
	}
	apps := make([]developerApp, 0, len(docs))
	for _, doc := range docs {
		apps = append(apps, appFromDoc(doc))
	}
	return apps, nil
}

func (s mongoDeveloperStore) App(ctx context.Context, owner, id bson.ObjectID) (*developerApp, error) {
	var doc bson.M
	err := s.db.Collection("developer_apps").FindOne(ctx, bson.M{"_id": id, "owner_id": owner},
		options.FindOne().SetProjection(bson.M{"name": 1, "description": 1, "client_id": 1, "allowed_scopes": 1, "created_at": 1})).Decode(&doc)
	if errors.Is(err, mongo.ErrNoDocuments) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	app := appFromDoc(doc)
	return &app, nil
}

func (s mongoDeveloperStore) Tokens(ctx context.Context, owner, appID bson.ObjectID) ([]developerToken, error) {
	filter := bson.M{"user_id": owner, "category": "user"}
	if !appID.IsZero() {
		// The app is already known to belong to the caller.
		filter = bson.M{"app_id": appID}
	}
	cursor, err := s.db.Collection("api_tokens").Find(ctx, filter, options.Find().SetLimit(developerMaxItems).
		SetSort(bson.M{"created_at": -1}).
		SetProjection(bson.M{"type": 1, "scopes": 1, "expires_at": 1, "created_at": 1}))
	if err != nil {
		return nil, err
	}
	var docs []bson.M
	if err := cursor.All(ctx, &docs); err != nil {
		return nil, err
	}
	tokens := make([]developerToken, 0, len(docs))
	for _, doc := range docs {
		t := developerToken{Type: stringField(doc, "type"), Scopes: stringList(doc["scopes"], []string{}),
			ExpiresAt: isoTime(doc["expires_at"]), CreatedAt: isoTime(doc["created_at"])}
		if id, ok := doc["_id"].(bson.ObjectID); ok {
			t.ID = id.Hex()
		}
		tokens = append(tokens, t)
	}
	return tokens, nil
}

// developerHandler serves the two read routes and passes everything else on.
func developerHandler(next http.Handler, store developerStore, resolver *sessionResolver) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path
		isApp := strings.HasPrefix(path, developerAppPrefix)
		if path != developerOverviewPath && !isApp {
			next.ServeHTTP(w, r)
			return
		}
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("Vary", "Cookie")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			writeError(w, http.StatusMethodNotAllowed, "method not allowed")
			return
		}
		if site := r.Header.Get("Sec-Fetch-Site"); site != "" && site != "same-origin" && site != "none" {
			writeError(w, http.StatusForbidden, "forbidden")
			return
		}
		var appID bson.ObjectID
		if isApp {
			raw := strings.TrimPrefix(path, developerAppPrefix)
			id, err := bson.ObjectIDFromHex(raw)
			if err != nil || !authObjectID.MatchString(raw) {
				writeError(w, http.StatusNotFound, "not found")
				return
			}
			appID = id
		}
		resolver.RequireAuthenticated(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			principal, _ := PrincipalFromContext(r.Context())
			owner, err := bson.ObjectIDFromHex(principal.ActorID)
			if err != nil {
				authDenied(w, http.StatusServiceUnavailable, "session unavailable")
				return
			}
			ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
			defer cancel()
			if err := serveDeveloper(ctx, w, store, owner, appID); err != nil {
				log.Printf("Developer read failed (%s)", dbErrorKind(err))
				writeError(w, http.StatusServiceUnavailable, "service unavailable")
			}
		})).ServeHTTP(w, r)
	})
}

func serveDeveloper(ctx context.Context, w http.ResponseWriter, store developerStore, owner, appID bson.ObjectID) error {
	enabled, err := store.AccessEnabled(ctx, owner)
	if err != nil {
		return err
	}
	if !enabled {
		// The lock state: no data, so the page can show the access request.
		writeJSON(w, http.StatusOK, map[string]any{"access": false})
		return nil
	}
	if !appID.IsZero() {
		app, err := store.App(ctx, owner, appID)
		if err != nil {
			return err
		}
		if app == nil {
			writeError(w, http.StatusNotFound, "not found")
			return nil
		}
		tokens, err := store.Tokens(ctx, owner, appID)
		if err != nil {
			return err
		}
		writeJSON(w, http.StatusOK, map[string]any{"access": true, "app": app, "tokens": tokens})
		return nil
	}
	apps, err := store.Apps(ctx, owner)
	if err != nil {
		return err
	}
	tokens, err := store.Tokens(ctx, owner, bson.NilObjectID)
	if err != nil {
		return err
	}
	writeJSON(w, http.StatusOK, map[string]any{"access": true, "apps": apps, "tokens": tokens})
	return nil
}
