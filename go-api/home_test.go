package main

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

type homeResponseSource struct {
	calls int
	err   error
}

func (s *homeResponseSource) FindHome(context.Context, string) (bson.M, error) {
	s.calls++
	return bson.M{"events": []bson.M{}, "recommended": false}, s.err
}

func TestHomeCacheDoesNotReuseYesterday(t *testing.T) {
	source := &homeResponseSource{}
	cache := newHomeCache(source, context.Background())
	yesterday := &homeValue{data: []byte(`{"yesterday":true}`), hardExpiry: time.Now().Add(time.Hour).UnixNano(), day: shiftDay(localDay(time.Now()), -1)}
	cache.slots[0].cur.Store(yesterday)
	data, err := cache.Get(context.Background(), "fi")
	if err != nil || string(data) == string(yesterday.data) || source.calls != 1 {
		t.Fatal("yesterday reused", string(data), err)
	}
	cache.Get(context.Background(), "fi")
	if source.calls != 1 {
		t.Fatal("current-day cache not reused")
	}
	source.err = errors.New("unavailable")
	cache.slots[0].cur.Store(yesterday)
	if _, err := cache.Get(context.Background(), "fi"); err == nil {
		t.Fatal("yesterday's result reused on failed load")
	}
}

// This response-level contract runs against both the pre-refactor loader and
// the extracted helpers, including different homepage/listing image precedence.
func TestMongoHomeResponseContract(t *testing.T) {
	uri := os.Getenv("TEST_MONGODB_URI")
	if uri == "" {
		t.Skip("set TEST_MONGODB_URI for isolated homepage integration")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	client, err := mongo.Connect(options.Client().ApplyURI(uri))
	if err != nil {
		t.Fatal(err)
	}
	defer client.Disconnect(context.Background())
	db := client.Database("moso_go_home_test_" + bson.NewObjectID().Hex())
	defer db.Drop(context.Background())
	store := mongoStore{db.Collection("demonstrations"), client}
	day := shiftDay(localDay(time.Now()), 10)
	ids := []bson.ObjectID{}
	for i := range 8 {
		id := bson.NewObjectID()
		ids = append(ids, id)
		_, err := store.collection.InsertOne(ctx, bson.M{"_id": id, "approved": true,
			"date": shiftDay(day, i), "title": "Suomeksi", "city": "Helsinki", "address": "Tori", "tags": bson.A{"rauha"},
			"start_time": "17:30:45", "gallery_images": bson.A{"https://example.test/gallery.jpg"}, "cover_picture": "https://example.test/cover.jpg",
			"description": "PRIVATE-NOT-CARD", "translations": bson.M{"en": bson.M{"title": "English", "tags": bson.A{"peace"}}}})
		if err != nil {
			t.Fatal(err)
		}
	}
	for _, extra := range []bson.M{{"hide": true}, {"rejected": true}, {"cancelled": true}, {"approved": false}, {"date": bson.A{day}}, {"date": shiftDay(day, -20)}} {
		doc := bson.M{"_id": bson.NewObjectID(), "approved": true, "date": day}
		for key, value := range extra {
			doc[key] = value
		}
		if _, err := store.collection.InsertOne(ctx, doc); err != nil {
			t.Fatal(err)
		}
	}
	assertHome := func(lang string, selected []int, recommended bool) {
		t.Helper()
		actual, err := store.FindHome(ctx, lang)
		if err != nil {
			t.Fatal(err)
		}
		events := []bson.M{}
		for _, i := range selected {
			title, tag := "Suomeksi", "rauha"
			if lang == "en" {
				title, tag = "English", "peace"
			}
			date := shiftDay(day, i)
			parsed, _ := time.Parse("2006-01-02", date)
			events = append(events, bson.M{"_id": ids[i].Hex(), "title": title, "date": date, "date_display": parsed.Format("02.01.2006"),
				"city": "Helsinki", "address": "Tori", "tags": []string{tag}, "start_time_display": "17:30", "end_time_display": "",
				"cancelled": false, "cover_image": "https://example.test/gallery.jpg", "detail_url": "/demonstration/" + ids[i].Hex()})
		}
		want, _ := json.Marshal(bson.M{"events": events, "recommended": recommended})
		got, _ := json.Marshal(actual)
		if string(got) != string(want) {
			t.Fatalf("response contract changed\ngot %s\nwant %s", got, want)
		}
	}
	assertHome("fi", []int{0, 1, 2, 3, 4, 5}, false)
	for _, rec := range []bson.M{{"demo_id": ids[7].Hex(), "recommend_till": "a"}, {"demo_id": ids[6], "recommend_till": "b"}, {"demo_id": ids[7], "recommend_till": "c"}, {"demo_id": "invalid"}} {
		if _, err := db.Collection("recommended_demos").InsertOne(ctx, rec); err != nil {
			t.Fatal(err)
		}
	}
	assertHome("en", []int{7, 6}, true)
	if _, err := db.Collection("recommended_demos").DeleteMany(ctx, bson.M{}); err != nil {
		t.Fatal(err)
	}
	if _, err := db.Collection("recommended_demos").InsertOne(ctx, bson.M{"demo_id": bson.NewObjectID()}); err != nil {
		t.Fatal(err)
	}
	assertHome("fi", []int{0, 1, 2, 3, 4, 5}, false)
	query, _ := parseListingQuery("", time.Now())
	page, err := store.FindListing(ctx, query)
	if err != nil || len(page.Results) != 8 || page.Results[0]["cover_image"] != "https://example.test/cover.jpg" {
		t.Fatalf("listing image priority or public visibility changed: %+v %v", page, err)
	}
}
