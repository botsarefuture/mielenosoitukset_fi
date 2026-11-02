package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

type listingQuery struct {
	Lang, Day, Search, Title, Tag, Location string
	Cities                                  []string
	Start, End                              string
	Parent, Organization                    bson.ObjectID
	InPast, IncludeCancelled                bool
	MaxDays, Page, PerPage                  int
}

type listingPage struct {
	Page        int      `json:"page"`
	PerPage     int      `json:"per_page"`
	Total       int64    `json:"total"`
	TotalPages  int64    `json:"total_pages"`
	ResultStart int64    `json:"result_start"`
	ResultEnd   int64    `json:"result_end"`
	Results     []bson.M `json:"results"`
}

type listingStore interface {
	FindListing(context.Context, listingQuery) (listingPage, error)
}

func parseListingQuery(raw string, now time.Time) (listingQuery, error) {
	q := listingQuery{Lang: "fi", Day: localDay(now), Page: 1, PerPage: 20}
	values, err := listingValues(raw)
	if err != nil {
		return q, err
	}
	if lang := strings.ToLower(values.Get("lang")); lang != "" {
		if lang != "fi" && lang != "en" && lang != "sv" {
			return q, errors.New("invalid listing parameters")
		}
		q.Lang = lang
	}
	if err := q.parsePagination(values); err != nil {
		return q, err
	}
	if err := q.parseScopes(values); err != nil {
		return q, err
	}
	if err := q.parseDates(values); err != nil {
		return q, err
	}
	q.Search, q.Title = strings.ToLower(values.Get("search")), strings.ToLower(values.Get("title"))
	q.Tag, q.Location = strings.ToLower(values.Get("tag")), strings.ToLower(values.Get("location"))
	q.Cities = listingCities(values.Get("city"))
	if len(q.Cities) > 20 {
		return q, errors.New("invalid listing parameters")
	}
	return q, nil
}

func listingValues(raw string) (url.Values, error) {
	invalid := errors.New("invalid listing parameters")
	if len(raw) > 4096 {
		return nil, invalid
	}
	values, err := url.ParseQuery(raw)
	if err != nil {
		return nil, invalid
	}
	allowed := map[string]bool{}
	for _, key := range []string{"lang", "page", "per_page", "search", "title", "tag", "city", "location", "date_start", "date_end", "in_past", "include_cancelled", "parent_id", "organization_id", "max_days_till", "recurring"} {
		allowed[key] = true
	}
	for key, entries := range values {
		if !allowed[key] || len(entries) != 1 || !utf8.ValidString(entries[0]) {
			return nil, invalid
		}
		value := strings.TrimSpace(entries[0])
		if utf8.RuneCountInString(value) > 200 || strings.IndexFunc(value, unicode.IsControl) >= 0 {
			return nil, invalid
		}
		values.Set(key, value)
	}
	return values, nil
}

func (q *listingQuery) parsePagination(values url.Values) error {
	invalid := errors.New("invalid listing parameters")
	for key, target := range map[string]*int{"page": &q.Page, "per_page": &q.PerPage, "max_days_till": &q.MaxDays} {
		if raw := values.Get(key); raw != "" {
			value, err := strconv.Atoi(raw)
			if err != nil || value < 0 || (value == 0 && key != "max_days_till") || value > 100000 {
				return invalid
			}
			*target = value
		}
	}
	if q.PerPage > 100 || int64(q.Page-1)*int64(q.PerPage) > 100000 {
		return invalid
	}
	return nil
}

func (q *listingQuery) parseScopes(values url.Values) error {
	invalid := errors.New("invalid listing parameters")
	for key, target := range map[string]*bool{"in_past": &q.InPast, "include_cancelled": &q.IncludeCancelled} {
		if value := strings.ToLower(values.Get(key)); value != "" {
			if value != "true" && value != "false" {
				return invalid
			}
			*target = value == "true"
		}
	}
	for key, target := range map[string]*bson.ObjectID{"parent_id": &q.Parent, "organization_id": &q.Organization} {
		if value := values.Get(key); value != "" {
			id, err := bson.ObjectIDFromHex(value)
			if err != nil || id.IsZero() {
				return invalid
			}
			*target = id
		}
	}
	return nil
}

func (q *listingQuery) parseDates(values url.Values) error {
	invalid := errors.New("invalid listing parameters")
	for key, target := range map[string]*string{"date_start": &q.Start, "date_end": &q.End} {
		if value := values.Get(key); value != "" {
			if parsed, err := time.Parse("2006-01-02", value); err != nil || parsed.Format("2006-01-02") != value {
				return invalid
			}
			*target = value
		}
	}
	if q.Start != "" && q.End != "" && q.Start > q.End {
		return invalid
	}
	return nil
}

func listingCities(raw string) []string {
	var cities []string
	seen := map[string]bool{}
	for _, value := range strings.Split(raw, ",") {
		city := strings.ToLower(strings.TrimSpace(value))
		if city != "" && !seen[city] {
			seen[city] = true
			cities = append(cities, city)
		}
	}
	sort.Strings(cities)
	return cities
}

func listingFilter(q listingQuery) bson.M {
	filter := publicDatedFilter()
	if !q.IncludeCancelled && q.Parent.IsZero() && q.Organization.IsZero() {
		filter["cancelled"] = bson.M{"$ne": true}
	}
	if !q.Parent.IsZero() {
		filter["parent"] = bson.M{"$in": bson.A{q.Parent, q.Parent.Hex()}}
	}
	if !q.Organization.IsZero() {
		filter["organizers"] = bson.M{"$elemMatch": bson.M{"organization_id": bson.M{"$in": bson.A{q.Organization, q.Organization.Hex()}}}}
	}
	if dates := listingDates(q); len(dates) > 0 {
		filter["date"] = dates
	}
	filter["$and"] = listingSearch(q, filter["$and"].(bson.A))
	return filter
}

func listingDates(q listingQuery) bson.M {
	dates := bson.M{}
	if !q.InPast {
		dates["$gte"] = q.Day
	}
	if q.MaxDays > 0 {
		dates["$lte"] = shiftDay(q.Day, q.MaxDays)
	}
	if q.Start != "" && q.End != "" {
		dates = bson.M{"$gte": q.Start, "$lte": q.End}
	} else {
		if q.Start != "" {
			start, _ := dates["$gte"].(string)
			if q.Start > start {
				dates["$gte"] = q.Start
			}
		}
		if q.End != "" {
			dates["$lte"] = q.End
		}
	}
	return dates
}

func listingSearch(q listingQuery, and bson.A) bson.A {
	and = appendTranslatedMatch(and, []string{"title", "description", "tags", "address"}, q.Search, false)
	and = appendTranslatedMatch(and, []string{"title"}, q.Title, false)
	and = appendTranslatedMatch(and, []string{"tags"}, q.Tag, true)
	if q.Location != "" {
		and = append(and, bson.M{"address": literalMatch(q.Location, false)})
	}
	if len(q.Cities) > 0 {
		cities := bson.A{}
		for _, city := range q.Cities {
			cities = append(cities, literalMatch(city, true))
		}
		and = append(and, bson.M{"city": bson.M{"$in": cities}})
	}
	return and
}

func listingProjection() bson.M {
	fields := homeProjection()
	for _, field := range []string{"parent", "slug", "running_number", "cancelled", "latitude", "longitude"} {
		fields[field] = 1
	}
	return fields
}

func listingCard(doc bson.M, lang string) bson.M {
	payload := publicPayload(doc, lang)
	card := bson.M{}
	for _, field := range []string{"_id", "title", "date", "start_time", "end_time", "city", "address", "tags", "cancelled", "parent", "slug", "running_number", "latitude", "longitude"} {
		card[field] = payload[field]
	}
	if day, valid := cardDate(payload["date"]); valid {
		card["date_display"] = day
	}
	card["cover_image"] = firstCardImage(doc, "cover_picture", "cover_image", "preview_image", "img", "gallery_images", "images")
	id, _ := payload["_id"].(string)
	identifier := id
	if slug, ok := payload["slug"].(string); ok && validIdentifier(slug) {
		identifier = slug
	} else if running := nonNegativeInt(doc["running_number"]); running != nil {
		identifier = strconv.FormatInt(running.(int64), 10)
	}
	card["detail_url"] = "/demonstration/" + url.PathEscape(identifier)
	// The detail host decides whether this occurrence has a public series.
	// A hidden parent must leave its public occurrence independently reachable.
	return card
}

func (s mongoStore) FindListing(ctx context.Context, q listingQuery) (listingPage, error) {
	result := listingPage{Page: q.Page, PerPage: q.PerPage, TotalPages: 1, Results: []bson.M{}}
	filter := listingFilter(q)
	total, err := s.collection.CountDocuments(ctx, filter)
	if err != nil {
		return result, err
	}
	result.Total = total
	result.TotalPages = max((total+int64(q.PerPage)-1)/int64(q.PerPage), 1)
	if total == 0 || int64(q.Page) > result.TotalPages {
		return result, nil
	}
	cursor, err := s.collection.Find(ctx, filter, options.Find().SetProjection(listingProjection()).
		SetSort(bson.D{{Key: "date", Value: 1}, {Key: "start_time", Value: 1}, {Key: "_id", Value: 1}}).
		SetSkip(int64(q.Page-1)*int64(q.PerPage)).SetLimit(int64(q.PerPage)))
	if err != nil {
		return result, err
	}
	defer cursor.Close(ctx)
	for cursor.Next(ctx) {
		var doc bson.M
		if err := cursor.Decode(&doc); err != nil {
			return result, err
		}
		result.Results = append(result.Results, listingCard(doc, q.Lang))
	}
	if err := cursor.Err(); err != nil {
		return result, err
	}
	if len(result.Results) > 0 {
		result.ResultStart = int64(q.Page-1)*int64(q.PerPage) + 1
		result.ResultEnd = result.ResultStart + int64(len(result.Results)) - 1
	}
	return result, nil
}

func (a *API) getListing(w http.ResponseWriter, r *http.Request) {
	query, err := parseListingQuery(r.URL.RawQuery, time.Now())
	if err != nil {
		writeError(w, 400, "invalid listing parameters")
		return
	}
	if source, ok := a.store.(interface {
		FindListingJSON(context.Context, listingQuery) ([]byte, bool, error)
	}); ok {
		data, stale, err := source.FindListingJSON(r.Context(), query)
		if err == nil {
			if !stale {
				w.Header().Set("Cache-Control", "public, max-age=30, s-maxage=30")
			}
			writeJSONBytes(w, 200, data)
			return
		}
	} else if source, ok := a.store.(listingStore); ok {
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		result, err := source.FindListing(ctx, query)
		if err == nil {
			w.Header().Set("Cache-Control", "public, max-age=30, s-maxage=30")
			writeJSON(w, 200, result)
			return
		}
	}
	log.Print("Listing database read failed")
	writeError(w, 503, "service unavailable")
}
