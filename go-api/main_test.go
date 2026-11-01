package main

import (
	"context"
	"errors"
	"go.mongodb.org/mongo-driver/v2/bson"

	"go.mongodb.org/mongo-driver/v2/event"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

type fakeStore struct {
	doc        bson.M
	err        error
	resolveErr error
	calls      int
}

func (s *fakeStore) FindPublic(ctx context.Context, id bson.ObjectID) (bson.M, error) {
	s.calls++
	if _, ok := ctx.Deadline(); !ok {
		panic("missing query deadline")
	}
	return s.doc, s.err
}
func (s *fakeStore) ResolvePublicID(ctx context.Context, raw string) (bson.ObjectID, error) {
	if _, ok := ctx.Deadline(); !ok {
		panic("missing query deadline")
	}
	if s.resolveErr != nil {
		return bson.NilObjectID, s.resolveErr
	}
	if !validIdentifier(raw) {
		return bson.NilObjectID, errInvalidIdentifier
	}
	return bson.ObjectIDFromHex(demoID)
}
func (s *fakeStore) Ping(context.Context) error { return s.err }

const demoID = "66fa58601102367d5d52887f"

func TestPublicHTTPContract(t *testing.T) {
	id, _ := bson.ObjectIDFromHex(demoID)
	store := &fakeStore{doc: bson.M{"_id": id, "title": "Public", "email": "secret@example.test", "unknown": "secret", "organizers": bson.A{bson.M{"name": "Hidden name", "is_private": true, "show_name_public": false, "email": "hidden@example.test"}, bson.M{"name": "Visible", "email": "private@example.test"}}, "translations": bson.M{"en": bson.M{"title": "English", "email": "translated-secret"}}}}
	server := httptest.NewServer((&API{store}).handler())
	defer server.Close()
	response, err := http.Get(server.URL + "/api/demonstrations/" + demoID + "?lang=en")
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	body, _ := io.ReadAll(response.Body)
	if response.StatusCode != 200 || !strings.Contains(string(body), "English") || !strings.Contains(string(body), "Visible") {
		t.Fatalf("unexpected response %d %s", response.StatusCode, body)
	}
	for _, private := range []string{"secret", "Hidden name", "@example.test", "translations", "approved"} {
		if strings.Contains(string(body), private) {
			t.Fatalf("leaked %q: %s", private, body)
		}
	}
	if response.Header.Get("Access-Control-Allow-Origin") != "*" || response.Header.Get("Access-Control-Allow-Credentials") != "" || response.Header.Get("Cache-Control") != "no-store" {
		t.Fatal(response.Header)
	}
}
func TestValidationMethodsAndFailures(t *testing.T) {
	for _, tc := range []struct {
		method, path  string
		err           error
		status, calls int
	}{
		{"GET", "/api/demonstrations/bad%20slug!", nil, 400, 0},
		{"GET", "/api/demonstrations/" + demoID, mongo.ErrNoDocuments, 404, 1},
		{"GET", "/api/demonstrations/may-day-2026", nil, 200, 1},
		{"GET", "/api/demonstrations/123456", nil, 200, 1},
		{"GET", "/api/demonstrations/" + demoID + "?lang=en&lang=sv", nil, 400, 0},
		{"GET", "/api/demonstrations/" + demoID + "?approved=false", nil, 400, 0},
		{"GET", "/api/demonstrations/" + demoID + "?lang=%ZZ", nil, 400, 0},
		{"GET", "/api/demonstrations/" + demoID, errors.New("mongodb://secret"), 503, 1},
		{"POST", "/api/demonstrations/" + demoID, nil, 405, 0},
		{"DELETE", "/api/demonstrations/" + demoID, nil, 405, 0},
		{"OPTIONS", "/api/demonstrations/" + demoID, nil, 204, 0},
		{"HEAD", "/api/demonstrations/" + demoID, mongo.ErrNoDocuments, 404, 1},
		{"GET", "/health", errors.New("secret"), 503, 0},
	} {
		t.Run(tc.method+tc.path+strconv.Itoa(tc.status), func(t *testing.T) {
			s := &fakeStore{err: tc.err}
			w := httptest.NewRecorder()
			r := httptest.NewRequest(tc.method, tc.path, nil)
			r.Header.Set("Origin", "https://other.example")
			(&API{s}).handler().ServeHTTP(w, r)
			if w.Code != tc.status || s.calls != tc.calls || strings.Contains(w.Body.String(), "secret") {
				t.Fatalf("status=%d calls=%d body=%s", w.Code, s.calls, w.Body.String())
			}
		})
	}
}

// Identifier resolution runs before the body read, so a lookup failure must not
// touch FindPublic and must not leak driver detail.
func TestResolveFailures(t *testing.T) {
	for _, tc := range []struct {
		lookup error
		status int
	}{{mongo.ErrNoDocuments, 404}, {errors.New("mongodb://secret"), 503}} {
		s := &fakeStore{resolveErr: tc.lookup}
		w := httptest.NewRecorder()
		(&API{s}).handler().ServeHTTP(w, httptest.NewRequest("GET", "/api/demonstrations/may-day-2026", nil))
		if w.Code != tc.status || s.calls != 0 || strings.Contains(w.Body.String(), "secret") {
			t.Fatalf("lookup=%v status=%d calls=%d body=%s", tc.lookup, w.Code, s.calls, w.Body.String())
		}
	}
}

// Public output must expose the series parent identifier and nothing about the
// parent's content, so a host can link a recurring occurrence.
func TestPayloadSeriesParent(t *testing.T) {
	parent, alias := bson.NewObjectID(), bson.NewObjectID()
	payload := publicPayload(bson.M{"parent": parent, "aliases": bson.A{alias}}, "fi")
	if payload["parent"] != parent.Hex() {
		t.Fatalf("parent lost: %v", payload)
	}
	if _, leaked := payload["aliases"]; leaked {
		t.Fatalf("aliases leaked: %v", payload)
	}
	for _, value := range []any{nil, "", 42, bson.A{parent}} {
		if got := publicPayload(bson.M{"parent": value}, "fi")["parent"]; got != nil {
			t.Fatalf("non-ObjectId parent exposed: %v", got)
		}
	}
}

func TestLocalizationLegacyAndMalformedValues(t *testing.T) {
	doc := bson.M{"_id": bson.NewObjectID(), "title": "Original", "description": "Fallback", "tags": bson.A{"one", 42}, "latitude": "60.1", "longitude": "NaN", "start_time": nil, "date": bson.NewDateTimeFromTime(time.Date(2026, 10, 29, 0, 0, 0, 0, time.UTC)), "translations": bson.M{"en": bson.M{"title": "English", "description": "", "tags": bson.A{}}}}
	payload := publicPayload(doc, "en")
	if payload["title"] != "English" || payload["description"] != "Fallback" || payload["date"] != "2026-10-29" || payload["latitude"] != 60.1 || payload["longitude"] != nil || payload["start_time"] != nil {
		t.Fatal(payload)
	}
	if len(payload["tags"].([]string)) != 1 || len(payload["organizers"].([]bson.M)) != 0 {
		t.Fatal(payload)
	}
	doc["translations"] = "invalid"
	doc["organizers"] = "invalid"
	doc["tags"] = nil
	_ = publicPayload(doc, "")
}

// Real MongoDB confirms missing-vs-null visibility semantics and nested projection.
// Opt-in, isolated database only; never opens the production database.
func TestMongoPublicBoundary(t *testing.T) {
	uri := os.Getenv("TEST_MONGODB_URI")
	if uri == "" {
		t.Skip("set TEST_MONGODB_URI for isolated MongoDB integration")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	client, err := mongo.Connect(options.Client().ApplyURI(uri))
	if err != nil {
		t.Fatal(err)
	}
	defer client.Disconnect(context.Background())
	db := client.Database("moso_go_api_test_" + bson.NewObjectID().Hex())
	defer db.Drop(context.Background())
	collection := db.Collection("demonstrations")
	store := mongoStore{collection, client}
	for _, tc := range []struct {
		name    string
		fields  bson.M
		visible bool
	}{
		{"legacy public", bson.M{"approved": true}, true},
		{"explicit public", bson.M{"approved": true, "hide": false, "rejected": false}, true},
		{"unapproved", bson.M{"approved": false}, false},
		{"missing approval", bson.M{}, false},
		{"array approval", bson.M{"approved": bson.A{true}}, false},
		{"array hide", bson.M{"approved": true, "hide": bson.A{false}}, false},
		{"hidden", bson.M{"approved": true, "hide": true}, false},
		{"rejected", bson.M{"approved": true, "rejected": true}, false},
		{"null hide", bson.M{"approved": true, "hide": nil}, false},
		{"null rejection", bson.M{"approved": true, "rejected": nil}, false},
		{"cancelled public", bson.M{"approved": true, "cancelled": true}, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			id := bson.NewObjectID()
			tc.fields["_id"] = id
			tc.fields["title"] = "Public"
			tc.fields["email"] = "secret"
			tc.fields["moderation"] = bson.M{"token": "secret"}
			tc.fields["organizers"] = bson.A{bson.M{"name": "Visible", "email": "secret", "unknown": "secret"}}
			tc.fields["translations"] = bson.M{"en": bson.M{"title": "English", "email": "secret"}}
			if _, err := collection.InsertOne(ctx, tc.fields); err != nil {
				t.Fatal(err)
			}
			doc, err := store.FindPublic(ctx, id)
			if !tc.visible {
				if !errors.Is(err, mongo.ErrNoDocuments) {
					t.Fatalf("nonpublic returned: %v %v", doc, err)
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			encoded, _ := bson.MarshalExtJSON(doc, false, false)
			if strings.Contains(string(encoded), "secret") {
				t.Fatalf("projection leaked: %s", encoded)
			}
			payload := publicPayload(doc, "en")
			if payload["title"] != "English" || len(payload["organizers"].([]bson.M)) != 1 {
				t.Fatalf("real BSON localization/organizers lost: %v", payload)
			}
			// Moderation changes must apply immediately, with no cache bypass via headers.
			_, _ = collection.UpdateByID(ctx, id, bson.M{"$set": bson.M{"hide": true}})
			if _, err := store.FindPublic(ctx, id); !errors.Is(err, mongo.ErrNoDocuments) {
				t.Fatal("withdrawn event remained public", err)
			}
		})
	}
}

// Real MongoDB confirms identifier precedence and that nonpublic originals never
// resolve through an alias. Opt-in, isolated database only.
func TestMongoResolvePublicID(t *testing.T) {
	uri := os.Getenv("TEST_MONGODB_URI")
	if uri == "" {
		t.Skip("set TEST_MONGODB_URI for isolated MongoDB integration")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	var reads atomic.Int64
	monitor := &event.CommandMonitor{Started: func(_ context.Context, command *event.CommandStartedEvent) {
		if command.CommandName == "find" {
			reads.Add(1)
		}
	}}
	client, err := mongo.Connect(options.Client().ApplyURI(uri).SetMonitor(monitor))
	if err != nil {
		t.Fatal(err)
	}
	defer client.Disconnect(context.Background())
	db := client.Database("moso_go_api_test_" + bson.NewObjectID().Hex())
	defer db.Drop(context.Background())
	collection := db.Collection("demonstrations")
	store := mongoStore{collection, client}
	publicID, aliasID, parentID := bson.NewObjectID(), bson.NewObjectID(), bson.NewObjectID()
	privateID, hiddenAliasID := bson.NewObjectID(), bson.NewObjectID()
	for _, doc := range []bson.M{
		{"_id": publicID, "approved": true, "slug": "series-child", "running_number": int32(4242), "aliases": bson.A{aliasID}, "parent": parentID, "title": "Public"},
		{"_id": privateID, "approved": false, "slug": "private-original", "aliases": bson.A{hiddenAliasID}, "title": "Private"},
		// A public record pointing at the private original must not revive it.
		{"_id": bson.NewObjectID(), "approved": true, "slug": "unrelated", "aliases": bson.A{privateID}, "title": "Unrelated"},
	} {
		if _, err := collection.InsertOne(ctx, doc); err != nil {
			t.Fatal(err)
		}
	}
	for _, tc := range []struct {
		name, raw string
		want      bson.ObjectID
		missing   bool
	}{
		{"slug", "series-child", publicID, false},
		{"running number", "4242", publicID, false},
		{"alias", aliasID.Hex(), publicID, false},
		{"object id", publicID.Hex(), publicID, false},
		{"unknown slug", "no-such-event", bson.NilObjectID, true},
		{"hidden slug", "private-original", bson.NilObjectID, true},
		{"hidden alias", hiddenAliasID.Hex(), bson.NilObjectID, true},
		// A public alias pointing at a private original still resolves to nothing.
		{"private original by id", privateID.Hex(), bson.NilObjectID, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			before := reads.Load()
			got, err := store.ResolvePublicID(ctx, tc.raw)
			if tc.name == "object id" && reads.Load()-before != 1 {
				t.Fatalf("public ObjectId resolution used %d reads, want 1", reads.Load()-before)
			}
			if tc.missing {
				if !errors.Is(err, mongo.ErrNoDocuments) {
					t.Fatalf("resolved nonpublic %q: %v %v", tc.raw, got, err)
				}
				return
			}
			if err != nil || got != tc.want {
				t.Fatalf("resolved %q: %v %v", tc.raw, got, err)
			}
		})
	}
	if _, err := store.ResolvePublicID(ctx, "bad slug!"); !errors.Is(err, errInvalidIdentifier) {
		t.Fatalf("invalid identifier accepted: %v", err)
	}
	// The alias check for the public record itself must not resurrect its parent.
	doc, err := store.FindPublic(ctx, publicID)
	if err != nil || identifier(doc["parent"]) != parentID.Hex() {
		t.Fatalf("parent not projected: %v %v", doc, err)
	}
}

func TestLegacyRouteGalleryAndBlankTranslation(t *testing.T) {
	doc := bson.M{"route": bson.A{"First", "Second"}, "images": bson.A{" image.jpg ", "image.jpg"}, "title": "Original", "translations": bson.M{"en": bson.M{"title": "   ", "description": ""}}}
	result := publicPayload(doc, "en")
	if result["title"] != "Original" || len(result["route"].([]string)) != 2 || len(result["gallery_images"].([]string)) != 1 || len(result["available_languages"].([]string)) != 1 {
		t.Fatal(result)
	}
	if len(routeStops(`["First","Second"]`)) != 2 || len(routeStops("First, Second")) != 2 {
		t.Fatal("legacy route")
	}
	w := httptest.NewRecorder()
	(&API{&fakeStore{}}).handler().ServeHTTP(w, httptest.NewRequest("GET", "/unknown", nil))
	if w.Code != 404 || !strings.HasPrefix(w.Header().Get("Content-Type"), "application/json") {
		t.Fatal(w)
	}
}

func TestOrganizerPublicConsentAndPlaceholders(t *testing.T) {
	organizationID := bson.NewObjectID()
	for _, flag := range []any{nil, false, "true", 1, bson.A{true}, bson.M{"value": true}} {
		org := bson.M{"name": "Public organizer", "email": "hidden-address@example.test", "show_email_public": flag}
		result := publicPayload(bson.M{"organizers": bson.A{org}}, "fi")
		if got := result["organizers"].([]bson.M)[0]["email"]; got != nil {
			t.Fatalf("non-boolean consent exposed email: flag=%v got=%v", flag, got)
		}
	}
	result := publicPayload(bson.M{"cover_source": "manual", "organizers": bson.A{
		bson.M{"name": "Hidden private identity", "is_private": true, "show_name_public": false,
			"website": "https://private.example.test", "logo": "private-photo.jpg", "organization_id": organizationID,
			"email": "public-address@example.test", "show_email_public": true},
		bson.M{"name": "Visible private name", "is_private": true, "show_name_public": true, "organization_id": organizationID},
		bson.M{"name": "Public organization", "organization_id": organizationID, "logo": "public-logo.jpg",
			"email": "public-address@example.test", "show_email_public": true, "unknown": "private-value"},
	}}, "fi")
	organizers := result["organizers"].([]bson.M)
	hidden := organizers[0]
	if result["cover_source"] != "manual" || hidden["name"] != nil || hidden["is_private"] != true || hidden["website"] != nil || hidden["logo"] != nil || hidden["organization_id"] != nil || hidden["email"] != "public-address@example.test" {
		t.Fatalf("private placeholder or explicit email consent lost: %v", result)
	}
	if organizers[1]["name"] != "Visible private name" || organizers[1]["organization_id"] != nil || organizers[1]["email"] != nil {
		t.Fatal("visible private name exposed unconsented identifying fields", organizers[1])
	}
	if organizers[2]["organization_id"] != organizationID.Hex() || organizers[2]["logo"] != "public-logo.jpg" || organizers[2]["email"] != "public-address@example.test" {
		t.Fatal("public organizer fields lost", organizers[2])
	}
	if _, exists := organizers[2]["unknown"]; exists {
		t.Fatal("unknown organizer field exposed")
	}
}

func TestMongoOrganizerConsentProjection(t *testing.T) {
	uri := os.Getenv("TEST_MONGODB_URI")
	if uri == "" {
		t.Skip("set TEST_MONGODB_URI for isolated MongoDB integration")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	client, err := mongo.Connect(options.Client().ApplyURI(uri))
	if err != nil {
		t.Fatal(err)
	}
	defer client.Disconnect(context.Background())
	db := client.Database("moso_go_api_test_" + bson.NewObjectID().Hex())
	defer db.Drop(context.Background())
	collection := db.Collection("demonstrations")
	store := mongoStore{collection, client}
	for _, tc := range []struct {
		name       string
		consent    any
		setConsent bool
		public     bool
	}{
		{"explicit true", true, true, true},
		{"missing", nil, false, false},
		{"false", false, true, false},
		{"null", nil, true, false},
		{"string", "true", true, false},
		{"number", 1, true, false},
		{"array", bson.A{true}, true, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			id := bson.NewObjectID()
			org := bson.M{"name": "Private identity", "is_private": true, "show_name_public": false,
				"website": "https://identity.example.test", "logo": "identity.jpg", "organization_id": bson.NewObjectID(),
				"email": "contact-address@example.test", "private_token": "unprojected-secret"}
			if tc.setConsent {
				org["show_email_public"] = tc.consent
			}
			_, err := collection.InsertOne(ctx, bson.M{"_id": id, "approved": true, "cover_source": "manual", "organizers": bson.A{org}})
			if err != nil {
				t.Fatal(err)
			}
			doc, err := store.FindPublic(ctx, id)
			if err != nil {
				t.Fatal(err)
			}
			projected, _ := bson.MarshalExtJSON(doc, false, false)
			if strings.Contains(string(projected), "unprojected-secret") || (!tc.public && strings.Contains(string(projected), "contact-address")) {
				t.Fatal("projection returned private contact fields", string(projected))
			}
			payload := publicPayload(doc, "fi")
			organizers := payload["organizers"].([]bson.M)
			if payload["cover_source"] != "manual" || len(organizers) != 1 {
				t.Fatal("cover source or anonymous organizer lost", payload)
			}
			got := organizers[0]
			if got["name"] != nil || got["website"] != nil || got["logo"] != nil || got["organization_id"] != nil || got["is_private"] != true {
				t.Fatal("private identity returned", got)
			}
			if tc.public {
				if got["email"] != "contact-address@example.test" {
					t.Fatal("explicit public contact lost", got)
				}
			} else if got["email"] != nil {
				t.Fatal("unconsented email returned", got)
			}
		})
	}
}

// fakeJSONStore implements detailJSONStore, so the cached handler path runs
// without MongoDB while still counting resolver and body reads.
type fakeJSONStore struct {
	id           bson.ObjectID
	resolveErr   error
	documentErr  error
	resolveCalls int
	findCalls    int
	lastID       bson.ObjectID
}

func (s *fakeJSONStore) FindPublic(context.Context, bson.ObjectID) (bson.M, error) {
	return nil, mongo.ErrNoDocuments
}
func (s *fakeJSONStore) Ping(context.Context) error { return nil }
func (s *fakeJSONStore) ResolvePublicID(ctx context.Context, raw string) (bson.ObjectID, error) {
	if _, ok := ctx.Deadline(); !ok {
		panic("missing query deadline")
	}
	s.resolveCalls++
	if s.resolveErr != nil {
		return bson.NilObjectID, s.resolveErr
	}
	if !validIdentifier(raw) {
		return bson.NilObjectID, errInvalidIdentifier
	}
	return s.id, nil
}
func (s *fakeJSONStore) FindPublicJSON(ctx context.Context, id bson.ObjectID, lang string, render func(bson.M, string) ([]byte, error)) ([]byte, error) {
	if _, ok := ctx.Deadline(); !ok {
		panic("missing query deadline")
	}
	s.findCalls++
	s.lastID = id
	if s.documentErr != nil {
		return nil, s.documentErr
	}
	return []byte(`{"_id":"` + id.Hex() + `"}`), nil
}

// Existing site URLs use slugs, running numbers and aliases, so the cached
// handler must resolve them before touching the cache.
func TestCachedHandlerResolvesPublicIdentifiers(t *testing.T) {
	id, _ := bson.ObjectIDFromHex(demoID)
	for _, tc := range []struct {
		name                    string
		path                    string
		resolveErr, documentErr error
		status                  int
		resolveCalls, findCalls int
	}{
		{"slug", "/api/demonstrations/may-day-2026", nil, nil, 200, 1, 1},
		{"objectid", "/api/demonstrations/" + demoID, nil, nil, 200, 1, 1},
		{"running number", "/api/demonstrations/4242", nil, nil, 200, 1, 1},
		{"unknown slug", "/api/demonstrations/no-such-event", mongo.ErrNoDocuments, nil, 404, 1, 0},
		// The resolver is asked once and rejects the input without a database read.
		{"invalid identifier", "/api/demonstrations/bad%20slug!", nil, nil, 400, 1, 0},
		{"resolver failure", "/api/demonstrations/may-day-2026", errors.New("mongodb://secret"), nil, 503, 1, 0},
		{"invalid query", "/api/demonstrations/may-day-2026?lang=en&lang=sv", nil, nil, 400, 0, 0},
		{"body read failure", "/api/demonstrations/may-day-2026", nil, errors.New("mongodb://secret"), 503, 1, 1},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s := &fakeJSONStore{id: id, resolveErr: tc.resolveErr, documentErr: tc.documentErr}
			w := httptest.NewRecorder()
			(&API{s}).handler().ServeHTTP(w, httptest.NewRequest("GET", tc.path, nil))
			if w.Code != tc.status || s.resolveCalls != tc.resolveCalls || s.findCalls != tc.findCalls || strings.Contains(w.Body.String(), "secret") {
				t.Fatalf("status=%d resolve=%d find=%d body=%s", w.Code, s.resolveCalls, s.findCalls, w.Body.String())
			}
			if tc.findCalls > 0 && s.lastID != id {
				t.Fatalf("cache must be keyed by the resolved id, got %s", s.lastID)
			}
			if tc.status == 200 && w.Header().Get("Cache-Control") != demoCacheControl {
				t.Fatalf("missing public cache header: %v", w.Header())
			}
			if tc.status == 404 && w.Header().Get("Cache-Control") != notFoundCacheControl {
				t.Fatalf("missing not-found cache header: %v", w.Header())
			}
		})
	}
}

// A renamed slug or moderation change must take effect immediately, so the
// identifier is resolved on every request even when the body is cached.
func TestCachedHandlerResolvesOnEveryRequest(t *testing.T) {
	id, _ := bson.ObjectIDFromHex(demoID)
	s := &fakeJSONStore{id: id}
	handler := (&API{s}).handler()
	for _, identifier := range []string{"may-day-2026", "4242", demoID} {
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest("GET", "/api/demonstrations/"+identifier, nil))
		if w.Code != 200 {
			t.Fatalf("%s: status=%d body=%s", identifier, w.Code, w.Body.String())
		}
	}
	if s.resolveCalls != 3 || s.findCalls != 3 {
		t.Fatalf("expected one resolution and one body read per request, got %d/%d", s.resolveCalls, s.findCalls)
	}
}
