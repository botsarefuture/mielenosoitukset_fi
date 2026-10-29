package main

import (
	"context"
	"errors"
	"go.mongodb.org/mongo-driver/v2/bson"

	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"strings"
	"testing"
	"time"
)

type fakeStore struct {
	doc   bson.M
	err   error
	calls int
}

func (s *fakeStore) FindPublic(ctx context.Context, id bson.ObjectID) (bson.M, error) {
	s.calls++
	if _, ok := ctx.Deadline(); !ok {
		panic("missing query deadline")
	}
	return s.doc, s.err
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
		{"GET", "/api/demonstrations/bad", nil, 400, 0},
		{"GET", "/api/demonstrations/" + demoID + "?lang=en&lang=sv", nil, 400, 0},
		{"GET", "/api/demonstrations/" + demoID + "?approved=false", nil, 400, 0},
		{"GET", "/api/demonstrations/" + demoID + "?lang=%ZZ", nil, 400, 0},
		{"GET", "/api/demonstrations/" + demoID, mongo.ErrNoDocuments, 404, 1},
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
