package main

import (
	"context"
	_ "embed"
	"encoding/json"
	"log"
	"net/http"
	"sort"
	"strings"
	"unicode"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
	"golang.org/x/text/unicode/norm"
)

//go:generate python3 ../scripts/generate_city_catalog.py
//go:embed city_catalog.json
var cityCatalogJSON []byte

type catalogCity struct {
	Key            string `json:"key"`
	Name           string `json:"name"`
	Phrase         string `json:"phrase"`
	DefaultEnabled bool   `json:"default_enabled"`
}

var cityCatalog = readCityCatalog()

func readCityCatalog() map[string]catalogCity {
	var rows []catalogCity
	if err := json.Unmarshal(cityCatalogJSON, &rows); err != nil {
		panic("invalid generated city catalog")
	}
	result := make(map[string]catalogCity, len(rows))
	for _, row := range rows {
		result[row.Key] = row
	}
	return result
}

func normalizeCityKey(value string) string {
	value = norm.NFKD.String(strings.ToLower(strings.TrimSpace(value)))
	var ascii strings.Builder
	for _, char := range value {
		if char < 128 && !unicode.Is(unicode.Mn, char) {
			ascii.WriteRune(char)
		}
	}
	return strings.Join(strings.Fields(strings.ReplaceAll(ascii.String(), "_", "-")), "-")
}

type citySummary struct {
	Key           string `json:"key"`
	Name          string `json:"name"`
	Phrase        string `json:"phrase"`
	DemoCount     int64  `json:"demo_count"`
	TodayCount    int64  `json:"today_count"`
	UpcomingCount int64  `json:"upcoming_count"`
}

type citiesPayload struct {
	Day    string        `json:"day"`
	Cities []citySummary `json:"cities"`
}

type citiesStore interface {
	FindCities(context.Context, string) (citiesPayload, error)
}

func (s mongoStore) FindCities(ctx context.Context, day string) (citiesPayload, error) {
	enabled, err := s.enabledCities(ctx)
	if err != nil {
		return citiesPayload{}, err
	}
	all, err := s.cityEventCounts(ctx, day, false)
	if err != nil {
		return citiesPayload{}, err
	}
	upcoming, err := s.cityEventCounts(ctx, day, true)
	if err != nil {
		return citiesPayload{}, err
	}
	rows := []citySummary{}
	for key, city := range cityCatalog {
		count := all[key]
		if !enabled[key] && count.DemoCount == 0 {
			continue
		}
		rows = append(rows, citySummary{Key: key, Name: city.Name, Phrase: city.Phrase,
			DemoCount: count.DemoCount, TodayCount: count.TodayCount, UpcomingCount: upcoming[key].DemoCount})
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].Name < rows[j].Name })
	return citiesPayload{Day: day, Cities: rows}, nil
}

func (s mongoStore) enabledCities(ctx context.Context) (map[string]bool, error) {
	result := map[string]bool{}
	for key, city := range cityCatalog {
		result[key] = city.DefaultEnabled
	}
	cursor, err := s.collection.Database().Collection("city_settings").Find(ctx, bson.M{},
		options.Find().SetProjection(bson.M{"city_key": 1, "enabled": 1}))
	if err != nil {
		return nil, err
	}
	defer cursor.Close(ctx)
	for cursor.Next(ctx) {
		var setting struct {
			Key     string `bson:"city_key"`
			Enabled bool   `bson:"enabled"`
		}
		if err := cursor.Decode(&setting); err != nil {
			return nil, err
		}
		if _, known := cityCatalog[setting.Key]; known {
			result[setting.Key] = setting.Enabled
		}
	}
	return result, cursor.Err()
}

func (s mongoStore) cityEventCounts(ctx context.Context, day string, upcoming bool) (map[string]citySummary, error) {
	filter := publicDatedFilter()
	filter["city"] = bson.M{"$type": "string", "$ne": ""}
	if upcoming {
		filter["date"] = bson.M{"$gte": day}
		filter["cancelled"] = bson.M{"$ne": true}
	}
	group := bson.M{"_id": bson.M{"city_key": "$city_key", "city": "$city"}, "count": bson.M{"$sum": 1},
		"today": bson.M{"$sum": bson.M{"$cond": bson.A{bson.M{"$eq": bson.A{"$date", day}}, 1, 0}}}}
	cursor, err := s.collection.Aggregate(ctx, mongo.Pipeline{{{Key: "$match", Value: filter}}, {{Key: "$group", Value: group}}})
	if err != nil {
		return nil, err
	}
	defer cursor.Close(ctx)
	result := map[string]citySummary{}
	for cursor.Next(ctx) {
		var row struct {
			Identity bson.M `bson:"_id"`
			Count    int64  `bson:"count"`
			Today    int64  `bson:"today"`
		}
		if err := cursor.Decode(&row); err != nil {
			return nil, err
		}
		identity, _ := row.Identity["city_key"].(string)
		if identity == "" {
			identity, _ = row.Identity["city"].(string)
		}
		key := normalizeCityKey(identity)
		if _, known := cityCatalog[key]; !known {
			continue
		}
		count := result[key]
		count.DemoCount += row.Count
		count.TodayCount += row.Today
		result[key] = count
	}
	return result, cursor.Err()
}

func (a *API) getCities(w http.ResponseWriter, r *http.Request) {
	if len(r.URL.RawQuery) > 512 {
		writeError(w, 400, "invalid query parameters")
		return
	}
	if _, err := parseQuery(r.URL.RawQuery); err != nil {
		writeError(w, 400, "invalid query parameters")
		return
	}
	source, ok := a.store.(interface {
		FindCitiesJSON(context.Context) ([]byte, error)
	})
	if !ok {
		writeError(w, 503, "service unavailable")
		return
	}
	data, err := source.FindCitiesJSON(r.Context())
	if err != nil {
		log.Print("City directory read failed")
		writeError(w, 503, "service unavailable")
		return
	}
	w.Header().Set("Cache-Control", "public, max-age=60, s-maxage=300")
	writeJSONBytes(w, 200, data)
}
