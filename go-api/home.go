package main

import (
	"context"
	"errors"
	"log"
	"net/http"
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

// FindHome checks moderation when loading from MongoDB. Response caches may
// reuse the resulting public payload without another database read.
func (s mongoStore) FindHome(ctx context.Context, lang string) (bson.M, error) {
	location, err := time.LoadLocation("Europe/Helsinki")
	if err != nil {
		return nil, err
	}
	filter := publicDatedFilter()
	today := time.Now().In(location).Format("2006-01-02")
	filter["date"] = bson.M{"$gte": today, "$lte": shiftDay(today, upcomingHorizonDays)}
	filter["cancelled"] = bson.M{"$ne": true}
	ids, ranks, err := s.homeRecommendations(ctx)
	if err != nil {
		return nil, err
	}
	docs := []bson.M{}
	if len(ids) > 0 {
		filter["_id"] = bson.M{"$in": ids}
		docs, err = s.readHomeEvents(ctx, filter, 50)
		if err != nil {
			return nil, err
		}
	}
	recommended := len(docs) > 0
	if recommended {
		sortHomeRecommendations(docs, ranks)
	} else {
		delete(filter, "_id")
		docs, err = s.readHomeEvents(ctx, filter, 6)
		if err != nil {
			return nil, err
		}
	}
	return bson.M{"events": homeCards(docs, lang), "recommended": recommended}, nil
}

func (s mongoStore) homeRecommendations(ctx context.Context) (bson.A, map[bson.ObjectID]string, error) {
	query := options.Find().SetProjection(bson.M{"demo_id": 1, "recommend_till": 1}).
		SetSort(bson.D{{Key: "recommend_till", Value: 1}, {Key: "_id", Value: 1}}).SetLimit(50)
	cursor, err := s.collection.Database().Collection("recommended_demos").Find(ctx, bson.M{}, query)
	if err != nil {
		return nil, nil, err
	}
	defer cursor.Close(ctx)
	ids := bson.A{}
	ranks := map[bson.ObjectID]string{}
	for cursor.Next(ctx) {
		var rec bson.M
		if err := cursor.Decode(&rec); err != nil {
			return nil, nil, err
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
	return ids, ranks, cursor.Err()
}

func (s mongoStore) readHomeEvents(ctx context.Context, filter bson.M, limit int64) ([]bson.M, error) {
	query := options.Find().SetProjection(homeProjection()).
		SetSort(bson.D{{Key: "date", Value: 1}, {Key: "_id", Value: 1}}).SetLimit(limit)
	cursor, err := s.collection.Find(ctx, filter, query)
	if err != nil {
		return nil, err
	}
	defer cursor.Close(ctx)
	docs := []bson.M{}
	err = cursor.All(ctx, &docs)
	return docs, err
}
