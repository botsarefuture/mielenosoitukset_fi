package main

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

func TestCampaignPublicationFailsClosedAndPassesOtherPaths(t *testing.T) {
	cases := []struct {
		name  string
		value bool
		err   error
		want  string
	}{
		{"published", true, nil, "{\"published\":true}\n"},
		{"private", false, nil, "{\"published\":false}\n"},
		{"read error", true, errors.New("database unavailable"), "{\"published\":false}\n"},
	}
	for _, c := range cases {
		served := 0
		handler := campaignPublication(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			served++
			w.WriteHeader(204)
		}), func(context.Context) (bool, error) { return c.value, c.err })
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest("GET", campaignPublicationPath, nil))
		if w.Code != 200 || w.Body.String() != c.want || w.Header().Get("Cache-Control") != "no-store" {
			t.Fatal(c.name, w.Code, w.Body.String(), w.Header().Get("Cache-Control"))
		}
		w = httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest("POST", campaignPublicationPath, nil))
		if w.Code != 405 {
			t.Fatal(c.name, "post", w.Code)
		}
		w = httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest("GET", "/api/home", nil))
		if served != 1 || w.Code != 204 {
			t.Fatal(c.name, "passthrough", served, w.Code)
		}
	}
}

func TestCampaignPublicationCoalescesReads(t *testing.T) {
	calls := 0
	handler := campaignPublication(http.NotFoundHandler(), func(context.Context) (bool, error) { calls++; return true, nil })
	for range 5 {
		handler.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", campaignPublicationPath, nil))
	}
	if calls != 1 {
		t.Fatal(calls)
	}
}

func TestReadCampaignPublicationMatchesFlaskStrictness(t *testing.T) {
	uri := os.Getenv("TEST_MONGODB_URI")
	if uri == "" {
		t.Skip("set TEST_MONGODB_URI for isolated MongoDB integration")
	}
	client, err := mongo.Connect(options.Client().ApplyURI(uri))
	if err != nil {
		t.Fatal(err)
	}
	defer client.Disconnect(context.Background())
	db := client.Database("moso_go_api_test_" + bson.NewObjectID().Hex())
	defer db.Drop(context.Background())
	read := readCampaignPublication(db)
	settings := db.Collection("campaign_settings")
	for _, tc := range []struct {
		name  string
		doc   bson.M
		value bool
	}{
		{"missing document", nil, false},
		{"missing field", bson.M{"_id": "public_pages"}, false},
		{"string true", bson.M{"_id": "public_pages", "published": "true"}, false},
		{"one", bson.M{"_id": "public_pages", "published": 1}, false},
		{"false", bson.M{"_id": "public_pages", "published": false}, false},
		{"true", bson.M{"_id": "public_pages", "published": true}, true},
	} {
		if _, err := settings.DeleteMany(context.Background(), bson.M{}); err != nil {
			t.Fatal(err)
		}
		if tc.doc != nil {
			if _, err := settings.InsertOne(context.Background(), tc.doc); err != nil {
				t.Fatal(err)
			}
		}
		got, err := read(context.Background())
		if err != nil || got != tc.value {
			t.Fatal(tc.name, got, err)
		}
	}
}
