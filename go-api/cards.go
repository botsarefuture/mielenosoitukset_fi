package main

import (
	"sort"
	"strings"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
)

// firstCardImage keeps each endpoint's existing image precedence explicit.
func firstCardImage(doc bson.M, fields ...string) string {
	for _, field := range fields {
		if images := galleryImages(doc[field]); len(images) > 0 {
			return images[0]
		}
	}
	return ""
}

func cardDate(value any) (string, bool) {
	day, _ := value.(string)
	parsed, err := time.Parse("2006-01-02", day)
	return parsed.Format("02.01.2006"), err == nil
}

func homeClock(value any) string {
	clock, _ := value.(string)
	parts := strings.Split(clock, ":")
	if len(parts) >= 2 {
		return strings.Join(parts[:2], ":")
	}
	return clock
}

func homeCards(docs []bson.M, lang string) []bson.M {
	events := []bson.M{}
	for _, doc := range docs {
		payload := publicPayload(doc, lang)
		day, valid := cardDate(payload["date"])
		if !valid {
			continue
		}
		event := bson.M{}
		for _, field := range []string{"_id", "title", "date", "city", "address", "tags"} {
			event[field] = payload[field]
		}
		event["date_display"] = day
		event["start_time_display"] = homeClock(payload["start_time"])
		event["end_time_display"] = homeClock(payload["end_time"])
		event["cancelled"] = false
		event["cover_image"] = firstCardImage(doc, "gallery_images", "images", "img", "cover_picture", "cover_image", "preview_image")
		event["detail_url"] = "/demonstration/" + doc["_id"].(bson.ObjectID).Hex()
		events = append(events, event)
	}
	return events
}

func sortHomeRecommendations(docs []bson.M, ranks map[bson.ObjectID]string) {
	rank := func(doc bson.M) string {
		value := ranks[doc["_id"].(bson.ObjectID)]
		if value == "" {
			value, _ = doc["date"].(string)
		}
		return value
	}
	sort.SliceStable(docs, func(i, j int) bool { return rank(docs[i]) < rank(docs[j]) })
}
