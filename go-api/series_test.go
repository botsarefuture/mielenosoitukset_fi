package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

// fakeSeriesStore satisfies Store so it can be handed to API, and seriesStore so
// the series handler reads from it.
type fakeSeriesStore struct {
	payload seriesPayload
	err     error
	calls   int
	lastID  bson.ObjectID
}

func (s *fakeSeriesStore) FindPublic(context.Context, bson.ObjectID) (bson.M, error) {
	return nil, mongo.ErrNoDocuments
}
func (s *fakeSeriesStore) ResolvePublicID(context.Context, string) (bson.ObjectID, error) {
	return bson.NilObjectID, errInvalidIdentifier
}
func (s *fakeSeriesStore) Ping(context.Context) error { return nil }
func (s *fakeSeriesStore) FindSeries(ctx context.Context, parent bson.ObjectID) (seriesPayload, error) {
	if _, ok := ctx.Deadline(); !ok {
		panic("missing query deadline")
	}
	s.calls++
	s.lastID = parent
	return s.payload, s.err
}

func TestSeriesHTTPContract(t *testing.T) {
	parent := bson.NewObjectID()
	payload := seriesPayload{ID: parent.Hex(), Occurrences: []seriesOccurrence{
		{ID: "66fa58601102367d5d52887f", Slug: "first", Date: "2026-12-01", StartTime: "14:00", EndTime: "15:00"},
		{ID: "66fa58601102367d5d52888a", Date: "2026-12-08", StartTime: "14:00", Cancelled: true},
	}}
	for _, tc := range []struct {
		name      string
		method    string
		path      string
		err       error
		status    int
		calls     int
		bodyMatch []string
	}{
		{"public series", "GET", "/api/series/" + parent.Hex(), nil, 200, 1,
			[]string{parent.Hex(), `"slug":"first"`, `"cancelled":true`, "2026-12-08"}},
		{"unknown or nonpublic series", "GET", "/api/series/" + parent.Hex(), mongo.ErrNoDocuments, 404, 1, nil},
		{"database failure", "GET", "/api/series/" + parent.Hex(), errors.New("mongodb://secret"), 503, 1, nil},
		{"invalid parent", "GET", "/api/series/not-an-id", nil, 404, 0, nil},
		{"unknown parameter", "GET", "/api/series/" + parent.Hex() + "?lang=en&page=2", nil, 400, 0, nil},
		{"duplicate language", "GET", "/api/series/" + parent.Hex() + "?lang=en&lang=sv", nil, 400, 0, nil},
		{"post", "POST", "/api/series/" + parent.Hex(), nil, 405, 0, nil},
	} {
		t.Run(tc.name, func(t *testing.T) {
			store := &fakeSeriesStore{payload: payload, err: tc.err}
			// A payload for the parent under test, even when the request is rejected.
			store.payload.ID = parent.Hex()
			w := httptest.NewRecorder()
			(&API{store}).handler().ServeHTTP(w, httptest.NewRequest(tc.method, tc.path, nil))
			if w.Code != tc.status || store.calls != tc.calls {
				t.Fatalf("status=%d calls=%d body=%s", w.Code, store.calls, w.Body.String())
			}
			if strings.Contains(w.Body.String(), "secret") {
				t.Fatalf("driver detail leaked: %s", w.Body.String())
			}
			if tc.status == 200 {
				for _, match := range tc.bodyMatch {
					if !strings.Contains(w.Body.String(), match) {
						t.Fatalf("missing %q in %s", match, w.Body.String())
					}
				}
				if store.lastID != parent {
					t.Fatalf("series queried for %s", store.lastID)
				}
				var decoded seriesPayload
				if err := json.Unmarshal(w.Body.Bytes(), &decoded); err != nil {
					t.Fatal(err)
				}
				if len(decoded.Occurrences) != len(payload.Occurrences) {
					t.Fatalf("occurrences lost: %+v", decoded)
				}
				if w.Header().Get("Cache-Control") != "no-store" || w.Header().Get("Content-Type") != "application/json; charset=utf-8" {
					t.Fatalf("unexpected headers: %v", w.Header())
				}
			}
		})
	}
}

// The handler is the only place that decides 404 versus 503, so an unimplemented
// store must not look like a public series with no occurrences.
func TestSeriesWithoutStoreFailsClosed(t *testing.T) {
	w := httptest.NewRecorder()
	(&API{&fakeStore{}}).handler().ServeHTTP(w, httptest.NewRequest("GET", "/api/series/"+demoID, nil))
	if w.Code != 503 {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
}

// Integration coverage for the queries the unit tests cannot reach.
func TestMongoFindSeries(t *testing.T) {
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
	db := client.Database("moso_go_series_test_" + bson.NewObjectID().Hex())
	defer db.Drop(context.Background())
	collection := db.Collection("demonstrations")
	store := mongoStore{collection, client}

	parent, hiddenParent, otherParent := bson.NewObjectID(), bson.NewObjectID(), bson.NewObjectID()
	today := localDay(time.Now())
	upcoming, later, past, cancelled := bson.NewObjectID(), bson.NewObjectID(), bson.NewObjectID(), bson.NewObjectID()
	tooFar, unapproved, foreign := bson.NewObjectID(), bson.NewObjectID(), bson.NewObjectID()
	for _, doc := range []bson.M{
		{"_id": parent, "approved": true},
		{"_id": hiddenParent, "approved": true, "hide": true},
		{"_id": otherParent, "approved": true},
		// One occurrence stores the parent as a string, as older records do.
		{"_id": upcoming, "approved": true, "parent": parent.Hex(), "slug": "upcoming", "date": today, "start_time": "14:00"},
		{"_id": later, "approved": true, "parent": parent, "date": shiftDay(today, 7), "start_time": "10:00"},
		{"_id": past, "approved": true, "parent": parent, "date": shiftDay(today, -7)},
		{"_id": cancelled, "approved": true, "parent": parent, "date": today, "cancelled": true},
		{"_id": tooFar, "approved": true, "parent": parent, "date": shiftDay(today, seriesWindowDays+10)},
		{"_id": unapproved, "approved": false, "parent": parent, "date": today},
		{"_id": foreign, "approved": true, "parent": otherParent, "date": today},
	} {
		if _, err := collection.InsertOne(ctx, doc); err != nil {
			t.Fatal(err)
		}
	}
	for _, doc := range []bson.M{
		{"_id": parent, "approved": true},
		{"_id": hiddenParent, "approved": true, "hide": true},
		{"_id": otherParent, "approved": true},
	} {
		if _, err := db.Collection("recu_demos").InsertOne(ctx, doc); err != nil {
			t.Fatal(err)
		}
	}

	series, err := store.FindSeries(ctx, parent)
	if err != nil {
		t.Fatal(err)
	}
	var got []string
	for _, occurrence := range series.Occurrences {
		got = append(got, occurrence.ID)
	}
	want := []string{past.Hex(), upcoming.Hex(), cancelled.Hex(), later.Hex()}
	if strings.Join(got, ",") != strings.Join(want, ",") {
		t.Fatalf("occurrences=%v want %v", got, want)
	}
	if series.Occurrences[1].Slug != "upcoming" || !series.Occurrences[2].Cancelled {
		t.Fatalf("fields lost: %+v", series.Occurrences)
	}

	if _, err := store.FindSeries(ctx, hiddenParent); !errors.Is(err, mongo.ErrNoDocuments) {
		t.Fatalf("hidden parent resolved: %v", err)
	}
	if _, err := store.FindSeries(ctx, bson.NewObjectID()); !errors.Is(err, mongo.ErrNoDocuments) {
		t.Fatalf("missing parent resolved: %v", err)
	}
}

