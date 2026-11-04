package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"sort"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

// The recurring series endpoint replaces the read work the Flask chooser page
// does: parent visibility and the bounded occurrence list. Selection, ordering
// for display and the index window belong to the caller, so this payload stays
// raw content plus identifiers.

const (
	seriesWindowDays = 90
	seriesLimit      = 16
)

type seriesOccurrence struct {
	ID            string `json:"id"`
	Slug          string `json:"slug,omitempty"`
	RunningNumber int64  `json:"running_number,omitempty"`
	Date          string `json:"date,omitempty"`
	StartTime     string `json:"start_time,omitempty"`
	EndTime       string `json:"end_time,omitempty"`
	Cancelled     bool   `json:"cancelled"`
}

type seriesPayload struct {
	ID          string             `json:"id"`
	Occurrences []seriesOccurrence `json:"occurrences"`
}

// seriesStore is implemented by mongoStore and delegated by the cached store.
type seriesStore interface {
	FindSeries(ctx context.Context, parent bson.ObjectID) (seriesPayload, error)
}

// seriesChildrenFilter matches the children query the Flask chooser uses, with
// the shared public visibility rule so an unapproved child can never appear.
func seriesChildrenFilter(parent bson.ObjectID) bson.M {
	filter := publicVisibility()
	filter["parent"] = bson.M{"$in": bson.A{parent, parent.Hex()}}
	return filter
}

// localDay returns the current Helsinki date, which is the day boundary the
// existing pages use. A host without zoneinfo falls back to UTC.
func localDay(now time.Time) string {
	location, err := time.LoadLocation("Europe/Helsinki")
	if err != nil {
		return now.UTC().Format("2006-01-02")
	}
	return now.In(location).Format("2006-01-02")
}

func shiftDay(day string, days int) string {
	parsed, err := time.Parse("2006-01-02", day)
	if err != nil {
		return day
	}
	return parsed.AddDate(0, 0, days).Format("2006-01-02")
}

func (s mongoStore) FindSeries(ctx context.Context, parent bson.ObjectID) (seriesPayload, error) {
	payload := seriesPayload{ID: parent.Hex(), Occurrences: []seriesOccurrence{}}
	// The series parent lives in its own collection; its moderation fields decide
	// whether the occurrence pages are public at all.
	var parentDoc bson.M
	err := s.collection.Database().Collection("recu_demos").
		FindOne(ctx, bson.M{"_id": parent}, options.FindOne().SetProjection(bson.M{"approved": 1, "hide": 1, "rejected": 1})).
		Decode(&parentDoc)
	if err != nil {
		return payload, err
	}
	approved, _ := parentDoc["approved"].(bool)
	if !approved {
		return payload, mongo.ErrNoDocuments
	}
	for _, field := range []string{"hide", "rejected"} {
		if stored, exists := parentDoc[field]; exists {
			if value, ok := stored.(bool); !ok || value {
				return payload, mongo.ErrNoDocuments
			}
		}
	}

	collection := s.collection
	base := seriesChildrenFilter(parent)
	today := localDay(time.Now())
	windowEnd := shiftDay(today, seriesWindowDays)
	windowStart := shiftDay(today, -seriesWindowDays)
	projection := options.Find().SetProjection(bson.M{
		"_id": 1, "slug": 1, "running_number": 1, "date": 1, "start_time": 1, "end_time": 1, "cancelled": 1,
	}).SetLimit(seriesLimit)

	upcomingFilter := cloneFilter(base)
	upcomingFilter["cancelled"] = bson.M{"$ne": true}
	upcomingFilter["date"] = bson.M{"$gte": today, "$lte": windowEnd}
	upcoming, err := collection.Find(ctx, upcomingFilter, projection.SetSort(bson.D{
		{Key: "date", Value: 1}, {Key: "start_time", Value: 1}, {Key: "_id", Value: 1},
	}))
	if err != nil {
		return payload, err
	}
	defer upcoming.Close(ctx)

	pastFilter := cloneFilter(base)
	pastFilter["cancelled"] = bson.M{"$ne": true}
	pastFilter["date"] = bson.M{"$lt": today}
	past, err := collection.Find(ctx, pastFilter, projection.SetSort(bson.D{
		{Key: "date", Value: -1}, {Key: "start_time", Value: -1}, {Key: "_id", Value: -1},
	}))
	if err != nil {
		return payload, err
	}
	defer past.Close(ctx)

	cancelledFilter := cloneFilter(base)
	cancelledFilter["cancelled"] = true
	cancelledFilter["date"] = bson.M{"$gte": windowStart, "$lte": windowEnd}
	cancelled, err := collection.Find(ctx, cancelledFilter, projection.SetSort(bson.D{
		{Key: "date", Value: 1}, {Key: "start_time", Value: 1}, {Key: "_id", Value: 1},
	}))
	if err != nil {
		return payload, err
	}
	defer cancelled.Close(ctx)

	seen := map[string]bool{}
	occurrences := []seriesOccurrence{}
	for _, cursor := range []*mongo.Cursor{upcoming, past, cancelled} {
		for cursor.Next(ctx) {
			var doc bson.M
			if err := cursor.Decode(&doc); err != nil {
				return payload, err
			}
			entry, ok := seriesEntry(doc)
			if !ok || seen[entry.ID] {
				continue
			}
			seen[entry.ID] = true
			occurrences = append(occurrences, entry)
		}
		if err := cursor.Err(); err != nil {
			return payload, err
		}
	}
	// One display order for every caller.
	sort.Slice(occurrences, func(i, j int) bool { return lessOccurrence(occurrences[i], occurrences[j]) })
	payload.Occurrences = occurrences
	return payload, nil
}

// lessOccurrence is the single ordering rule: date, then clock, then id. Within
// one date an occurrence with an announced time sorts first, because it is the
// more actionable row; an occurrence without a clock sorts last instead of
// jumping ahead of one that has a time.
func lessOccurrence(left, right seriesOccurrence) bool {
	if left.Date != right.Date {
		return left.Date < right.Date
	}
	leftTime, rightTime := left.StartTime != "", right.StartTime != ""
	if leftTime != rightTime {
		return leftTime
	}
	if left.StartTime != right.StartTime {
		return left.StartTime < right.StartTime
	}
	return left.ID < right.ID
}

func cloneFilter(source bson.M) bson.M {
	clone := bson.M{}
	for key, value := range source {
		clone[key] = value
	}
	return clone
}

func seriesEntry(doc bson.M) (seriesOccurrence, bool) {
	id, ok := doc["_id"].(bson.ObjectID)
	if !ok {
		return seriesOccurrence{}, false
	}
	entry := seriesOccurrence{ID: id.Hex(), Cancelled: doc["cancelled"] == true}
	if slug, ok := doc["slug"].(string); ok {
		entry.Slug = slug
	}
	switch value := doc["running_number"].(type) {
	case int32:
		entry.RunningNumber = int64(value)
	case int64:
		entry.RunningNumber = value
	case float64:
		entry.RunningNumber = int64(value)
	}
	switch value := doc["date"].(type) {
	case string:
		entry.Date = value
	case bson.DateTime:
		entry.Date = value.Time().UTC().Format("2006-01-02")
	case time.Time:
		entry.Date = value.UTC().Format("2006-01-02")
	}
	for field, target := range map[string]*string{"start_time": &entry.StartTime, "end_time": &entry.EndTime} {
		if value, ok := doc[field].(string); ok {
			*target = value
		}
	}
	return entry, true
}

func (s *cachedDetailStore) FindSeries(ctx context.Context, parent bson.ObjectID) (seriesPayload, error) {
	source, ok := s.source.(seriesStore)
	if !ok {
		return seriesPayload{}, errors.New("series store unavailable")
	}
	return source.FindSeries(ctx, parent)
}

func (a *API) getSeries(w http.ResponseWriter, r *http.Request) {
	if _, err := parseQuery(r.URL.RawQuery); err != nil {
		writeError(w, 400, "invalid query parameters")
		return
	}
	parent, err := bson.ObjectIDFromHex(r.PathValue("parent"))
	if err != nil {
		// A series parent is always an ObjectId; an invalid one cannot exist.
		writeError(w, 404, "series not found")
		return
	}
	source, ok := a.store.(seriesStore)
	if !ok {
		writeError(w, 503, "service unavailable")
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
	defer cancel()
	payload, err := source.FindSeries(ctx, parent)
	switch {
	case err == nil:
		writeJSON(w, 200, payload)
	case errors.Is(err, mongo.ErrNoDocuments):
		writeError(w, 404, "series not found")
	default:
		log.Print("Series database read failed")
		writeError(w, 503, "service unavailable")
	}
}
