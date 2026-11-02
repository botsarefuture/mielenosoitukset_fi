package main

import (
	"context"
	"encoding/json"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

func TestCityCatalogAndNormalization(t *testing.T) {
	for key, city := range cityCatalog {
		if normalizeCityKey(city.Name) != key {
			t.Fatal("generated key mismatch", city.Name, key)
		}
	}
	for _, value := range []string{"Jyväskylä", " JYVASKYLA ", "jyvaskyla"} {
		if normalizeCityKey(value) != "jyvaskyla" {
			t.Fatal(value)
		}
	}
	if cityCatalog["helsinki"].Phrase != "Helsingissä" || !cityCatalog["tampere"].DefaultEnabled {
		t.Fatal("existing city data changed")
	}
	if len(cityCatalog) < 300 {
		t.Fatal("municipality catalog incomplete")
	}
}

func TestMongoCitiesAndToday(t *testing.T) {
	uri := os.Getenv("TEST_MONGODB_URI")
	if uri == "" {
		t.Skip("set TEST_MONGODB_URI for isolated cities integration")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	client, err := mongo.Connect(options.Client().ApplyURI(uri))
	if err != nil {
		t.Fatal(err)
	}
	defer client.Disconnect(context.Background())
	db := client.Database("moso_go_cities_test_" + bson.NewObjectID().Hex())
	defer db.Drop(context.Background())
	store := mongoStore{db.Collection("demonstrations"), client}
	day := localDay(time.Now())
	for _, extra := range []bson.M{{}, {"city": "Helsingfors"}, {"cancelled": true}, {"date": shiftDay(day, 1)}, {"date": shiftDay(day, -1)}, {"hide": true}, {"approved": false}, {"date": bson.A{day}}} {
		doc := bson.M{"_id": bson.NewObjectID(), "approved": true, "date": day, "city": "Helsinki", "city_key": "helsinki", "title": "Public event", "start_time": "12:00"}
		for key, value := range extra {
			doc[key] = value
		}
		if _, err := store.collection.InsertOne(ctx, doc); err != nil {
			t.Fatal(err)
		}
	}
	for _, setting := range []bson.M{{"city_key": "tampere", "enabled": false}, {"city_key": "espoo", "enabled": true, "contact_instructions": "PRIVATE"}} {
		if _, err := db.Collection("city_settings").InsertOne(ctx, setting); err != nil {
			t.Fatal(err)
		}
	}
	payload, err := store.FindCities(ctx, day)
	if err != nil {
		t.Fatal(err)
	}
	seen := map[string]citySummary{}
	for _, city := range payload.Cities {
		seen[city.Key] = city
	}
	h := seen["helsinki"]
	if h.DemoCount != 5 || h.TodayCount != 3 || h.UpcomingCount != 3 {
		t.Fatalf("counts: %+v", h)
	}
	if _, exists := seen["tampere"]; exists {
		t.Fatal("disabled empty city included")
	}
	if _, exists := seen["espoo"]; !exists {
		t.Fatal("enabled empty city omitted")
	}
	data, _ := json.Marshal(payload)
	if strings.Contains(string(data), "PRIVATE") {
		t.Fatal("private settings leaked")
	}
	query, err := parseListingQuery("today=true&city=Helsinki&in_past=true&date_start=2000-01-01&date_end=2099-01-01&include_cancelled=false", time.Now())
	if err != nil {
		t.Fatal(err)
	}
	page, err := store.FindListing(ctx, query)
	if err != nil || page.Day != day || page.Total != 3 {
		t.Fatalf("today widened or lost cancellation/city key: %+v %v", page, err)
	}
	for _, event := range page.Results {
		if event["date"] != day {
			t.Fatal("non-today event leaked")
		}
	}
	cached := newCachedDetailStore(store)
	defer cached.Close()
	api := &API{cached}
	for _, raw := range []string{"", "?lang=fi", "?lang=fi&lang=en", "?private=true"} {
		w := httptest.NewRecorder()
		api.handler().ServeHTTP(w, httptest.NewRequest("GET", "/api/cities"+raw, nil))
		want := 200
		if strings.Contains(raw, "&") || strings.Contains(raw, "private") {
			want = 400
		}
		if w.Code != want {
			t.Fatal(raw, w.Code, w.Body)
		}
	}
}
