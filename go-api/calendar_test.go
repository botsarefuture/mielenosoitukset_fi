package main

import (
	"context"
	"errors"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

type fakeCalendarStore struct {
	fakeStore
	reads atomic.Int64
	fail  atomic.Bool
}

func (s *fakeCalendarStore) FindCalendar(ctx context.Context, month calendarMonth) (calendarPayload, error) {
	if _, ok := ctx.Deadline(); !ok {
		return calendarPayload{}, errors.New("missing deadline")
	}
	s.reads.Add(1)
	if s.fail.Load() {
		return calendarPayload{}, errors.New("unavailable")
	}
	return calendarPayload{Year: month.Year, Month: month.Month, City: month.City, Total: 2, Days: []calendarDay{{month.start().Format("2006-01-") + "09", 2}}}, nil
}

func TestCalendarCacheAndHTTP(t *testing.T) {
	source := &fakeCalendarStore{}
	store := newCachedDetailStore(source)
	defer store.Close()
	var wg sync.WaitGroup
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if _, err := store.FindCalendarJSON(context.Background(), calendarMonth{Year: 2026, Month: 11}); err != nil {
				t.Error(err)
			}
		}()
	}
	wg.Wait()
	if source.reads.Load() != 1 {
		t.Fatal("same month did not coalesce")
	}
	cache, _ := testResponseCache(t)
	handler := publicResponseCache((&API{store}).handler(), cache)
	request := func(method, path, tag string) *httptest.ResponseRecorder {
		r := httptest.NewRequest(method, path, nil)
		r.Header.Set("If-None-Match", tag)
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, r)
		return w
	}
	first := request("GET", "/api/calendar/2026/11", "")
	if first.Code != 200 || !strings.Contains(first.Body.String(), `"total":2`) || !strings.Contains(first.Header().Get("Cache-Control"), "s-maxage=300") {
		t.Fatal(first.Code, first.Body.String(), first.Header())
	}
	tag := first.Header().Get("ETag")
	if tag == "" || request("GET", "/api/calendar/2026/11?lang=sv", tag).Code != 304 {
		t.Fatal("conditional response changed for numeric counts")
	}
	head := request("HEAD", "/api/calendar/2026/11", "")
	if head.Code != 200 || head.Body.Len() != 0 || head.Header().Get("X-Public-Cache") != "HIT" {
		t.Fatal("HEAD did not reuse shared GET")
	}
	for _, path := range []string{"/api/calendar/2026/0", "/api/calendar/2026/13", "/api/calendar/1999/12", "/api/calendar/2026/11?private=true", "/api/calendar/2026/11?lang=fi&lang=sv"} {
		w := request("GET", path, "")
		if w.Code != 400 || w.Header().Get("Cache-Control") != "no-store" {
			t.Fatal(path, w.Code, w.Header())
		}
	}
	source.fail.Store(true)
	for i := 0; i < 2; i++ {
		if request("GET", "/api/calendar/2026/12", "").Code != 503 {
			t.Fatal("failure cached or hidden")
		}
	}
	if source.reads.Load() != 3 {
		t.Fatal("error was cached")
	}
	source.fail.Store(false)
	for month := 0; month < 70; month++ {
		_, err := store.FindCalendarJSON(context.Background(), calendarMonth{Year: 2020 + month/12, Month: month%12 + 1})
		if err != nil {
			t.Fatal(err)
		}
	}
	if len(store.calendar.items) > 64 {
		t.Fatal("calendar cache unbounded")
	}
}

func TestMongoCalendarMonthVisibilityAndDates(t *testing.T) {
	uri := os.Getenv("TEST_MONGODB_URI")
	if uri == "" {
		t.Skip("set TEST_MONGODB_URI for isolated calendar integration")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	client, err := mongo.Connect(options.Client().ApplyURI(uri))
	if err != nil {
		t.Fatal(err)
	}
	defer client.Disconnect(context.Background())
	db := client.Database("moso_go_calendar_test_" + bson.NewObjectID().Hex())
	defer db.Drop(context.Background())
	store := mongoStore{db.Collection("demonstrations"), client}
	for _, extra := range []bson.M{{}, {"date": "2028-02-29"}, {"date": "2028-01-31"}, {"date": "2028-03-01"}, {"date": "2028-02-30"}, {"date": bson.A{"2028-02-09"}}, {"approved": false}, {"hide": true}, {"hide": "false"}, {"rejected": true}, {"cancelled": true}} {
		doc := bson.M{"_id": bson.NewObjectID(), "approved": true, "date": "2028-02-09", "title": "Public", "email": "PRIVATE"}
		for k, v := range extra {
			doc[k] = v
		}
		if _, err := store.collection.InsertOne(ctx, doc); err != nil {
			t.Fatal(err)
		}
	}
	result, err := store.FindCalendar(ctx, calendarMonth{Year: 2028, Month: 2})
	if err != nil || result.Total != 2 || len(result.Days) != 2 || result.Days[1].Date != "2028-02-29" {
		t.Fatalf("month/visibility boundary: %+v %v", result, err)
	}
	empty, err := store.FindCalendar(ctx, calendarMonth{Year: 2027, Month: 2})
	if err != nil || empty.Total != 0 || empty.Days == nil {
		t.Fatal("empty month contract", empty, err)
	}
	if _, err := store.collection.InsertOne(ctx, bson.M{"approved": true, "date": "2028-12-31", "city": "Helsingfors", "city_key": "helsinki"}); err != nil {
		t.Fatal(err)
	}
	if _, err := store.collection.InsertOne(ctx, bson.M{"approved": true, "date": "2028-12-31", "city": "Tampere"}); err != nil {
		t.Fatal(err)
	}
	annual, err := store.FindCalendar(ctx, calendarMonth{Year: 2028, City: "helsinki"})
	if err != nil || annual.Total != 1 || len(annual.Days) != 1 || annual.Days[0].Date != "2028-12-31" || annual.City != "helsinki" {
		t.Fatal("annual/city boundary", annual, err)
	}
}

func TestCalendarScopedKeys(t *testing.T) {
	policy := func(path string) responsePolicy {
		t.Helper()
		p, ok := publicResponsePolicy(httptest.NewRequest("GET", path, nil), time.Now())
		if !ok {
			t.Fatal(path)
		}
		return p
	}
	a := policy("/api/calendar/2028?city=Helsinki")
	if a.key != policy("/api/calendar/2028?city=helsinki&lang=sv").key {
		t.Fatal("city aliases fragmented cache")
	}
	for _, path := range []string{"/api/calendar/2028", "/api/calendar/2028?city=Tampere", "/api/calendar/2028/1?city=helsinki", "/api/calendar/2027?city=helsinki"} {
		if policy(path).key == a.key {
			t.Fatal("calendar scopes shared a cache key", path)
		}
	}
	for _, raw := range []string{"city=not-a-city", "city=Helsinki&city=Tampere", "city=.*", "private=1", "lang=de"} {
		if _, err := parseCalendarRequest("2028", "", raw); err == nil {
			t.Fatal("invalid scope accepted", raw)
		}
	}
}
