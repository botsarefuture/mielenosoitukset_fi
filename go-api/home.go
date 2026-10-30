package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"sort"
	"strings"
	"time"
	_ "time/tzdata"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

type homeStore interface {
	FindHome(context.Context, string) (bson.M, error)
}

func (s *cachedDetailStore) FindHome(ctx context.Context, lang string) (bson.M, error) {
	if source, ok := s.source.(homeStore); ok {
		return source.FindHome(ctx, lang)
	}
	return nil, errors.New("home store unavailable")
}

func (a *API) getHome(w http.ResponseWriter, r *http.Request) {
	lang, err := parseQuery(r.URL.RawQuery)
	if err != nil {
		writeError(w, 400, "invalid query parameters")
		return
	}
	if lang == "" {
		lang = "fi"
	}
	source, ok := a.store.(homeStore)
	if !ok {
		writeError(w, 503, "service unavailable")
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
	defer cancel()
	result, err := source.FindHome(ctx, lang)
	if err != nil {
		log.Print("Home database read failed")
		writeError(w, 503, "service unavailable")
		return
	}
	writeJSON(w, 200, result)
}

func homeProjection() bson.M {
	fields := bson.M{}
	for _, field := range []string{"_id", "title", "date", "start_time", "end_time", "city", "address", "tags", "default_language", "gallery_images", "images", "img", "cover_picture", "cover_image", "preview_image"} {
		fields[field] = 1
	}
	for _, lang := range []string{"fi", "en", "sv"} {
		for _, field := range []string{"title", "tags"} {
			fields["translations."+lang+"."+field] = 1
		}
	}
	return fields
}

// The home response never caches public content: every read checks moderation.
func (s mongoStore) FindHome(ctx context.Context, lang string) (bson.M, error) {
	location, err := time.LoadLocation("Europe/Helsinki")
	if err != nil {
		return nil, err
	}
	today := time.Now().In(location).Format("2006-01-02")
	filter := publicFilter(bson.NilObjectID)
	delete(filter, "_id")
	filter["date"] = bson.M{"$gte": today}
	filter["cancelled"] = bson.M{"$ne": true}
	// Scalar ISO dates only; malformed arrays must not match a public date range.
	expressions := object(filter["$expr"])["$and"].(bson.A)
	object(filter["$expr"])["$and"] = append(expressions,
		bson.M{"$eq": bson.A{bson.M{"$type": "$date"}, "string"}},
		bson.M{"$eq": bson.A{bson.M{"$type": "$_id"}, "objectId"}},
	)

	recs, err := s.collection.Database().Collection("recommended_demos").Find(ctx, bson.M{}, options.Find().SetProjection(bson.M{"demo_id": 1, "recommend_till": 1}).SetSort(bson.D{{Key: "recommend_till", Value: 1}, {Key: "_id", Value: 1}}).SetLimit(50))
	if err != nil {
		return nil, err
	}
	defer recs.Close(ctx)
	ids := bson.A{}
	ranks := map[bson.ObjectID]string{}
	for recs.Next(ctx) {
		var rec bson.M
		if err = recs.Decode(&rec); err != nil {
			return nil, err
		}
		idString, ok := identifier(rec["demo_id"]).(string)
		if !ok {
			continue
		}
		id, _ := bson.ObjectIDFromHex(idString)
		if _, exists := ranks[id]; !exists {
			ids = append(ids, id)
			rank, _ := rec["recommend_till"].(string)
			ranks[id] = rank
		}
	}
	if err = recs.Err(); err != nil {
		return nil, err
	}
	read := func(query bson.M, limit int64) ([]bson.M, error) {
		cursor, err := s.collection.Find(ctx, query, options.Find().SetProjection(homeProjection()).SetSort(bson.D{{Key: "date", Value: 1}, {Key: "_id", Value: 1}}).SetLimit(limit))
		if err != nil {
			return nil, err
		}
		defer cursor.Close(ctx)
		docs := []bson.M{}
		err = cursor.All(ctx, &docs)
		return docs, err
	}
	docs := []bson.M{}
	if len(ids) > 0 {
		filter["_id"] = bson.M{"$in": ids}
		docs, err = read(filter, 50)
		if err != nil {
			return nil, err
		}
	}
	recommended := len(docs) > 0
	if recommended {
		rank := func(doc bson.M) string {
			value := ranks[doc["_id"].(bson.ObjectID)]
			if value == "" {
				value, _ = doc["date"].(string)
			}
			return value
		}
		sort.SliceStable(docs, func(i, j int) bool { return rank(docs[i]) < rank(docs[j]) })
	} else {
		delete(filter, "_id")
		docs, err = read(filter, 6)
		if err != nil {
			return nil, err
		}
	}
	events := []bson.M{}
	for _, doc := range docs {
		payload := publicPayload(doc, lang)
		event := bson.M{}
		for _, field := range []string{"_id", "title", "date", "city", "address", "tags"} {
			event[field] = payload[field]
		}
		dateText, _ := payload["date"].(string)
		if parsed, err := time.Parse("2006-01-02", dateText); err == nil {
			event["date_display"] = parsed.Format("02.01.2006")
		} else {
			continue
		}
		for _, field := range []string{"start_time", "end_time"} {
			value, _ := payload[field].(string)
			parts := strings.Split(value, ":")
			if len(parts) >= 2 {
				value = strings.Join(parts[:2], ":")
			}
			event[field+"_display"] = value
		}
		event["cancelled"] = false
		event["cover_image"] = ""
		for _, field := range []string{"gallery_images", "images", "img", "cover_picture", "cover_image", "preview_image"} {
			if images := galleryImages(doc[field]); len(images) > 0 {
				event["cover_image"] = images[0]
				break
			}
		}
		event["detail_url"] = "/demonstration/" + doc["_id"].(bson.ObjectID).Hex()
		events = append(events, event)
	}
	return bson.M{"events": events, "recommended": recommended}, nil
}
