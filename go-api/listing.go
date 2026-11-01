package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"net/url"
	"regexp"
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
	invalid := errors.New("invalid listing parameters")
	if len(raw) > 4096 {
		return q, invalid
	}
	values, err := url.ParseQuery(raw)
	if err != nil {
		return q, invalid
	}
	allowed := map[string]bool{}
	for _, key := range []string{"lang", "page", "per_page", "search", "title", "tag", "city", "location", "date_start", "date_end", "in_past", "include_cancelled", "parent_id", "organization_id", "max_days_till", "recurring"} {
		allowed[key] = true
	}
	for key, entries := range values {
		if !allowed[key] || len(entries) != 1 || !utf8.ValidString(entries[0]) {
			return q, invalid
		}
		value := strings.TrimSpace(entries[0])
		if utf8.RuneCountInString(value) > 200 || strings.IndexFunc(value, unicode.IsControl) >= 0 {
			return q, invalid
		}
		values.Set(key, value)
	}
	if lang := strings.ToLower(values.Get("lang")); lang != "" {
		if lang != "fi" && lang != "en" && lang != "sv" {
			return q, invalid
		}
		q.Lang = lang
	}
	for key, target := range map[string]*int{"page": &q.Page, "per_page": &q.PerPage, "max_days_till": &q.MaxDays} {
		if raw := values.Get(key); raw != "" {
			value, err := strconv.Atoi(raw)
			if err != nil || value < 0 || (value == 0 && key != "max_days_till") || value > 100000 {
				return q, invalid
			}
			*target = value
		}
	}
	if q.PerPage > 100 || int64(q.Page-1)*int64(q.PerPage) > 100000 {
		return q, invalid
	}
	for key, target := range map[string]*bool{"in_past": &q.InPast, "include_cancelled": &q.IncludeCancelled} {
		if value := strings.ToLower(values.Get(key)); value != "" {
			if value != "true" && value != "false" {
				return q, invalid
			}
			*target = value == "true"
		}
	}
	for key, target := range map[string]*bson.ObjectID{"parent_id": &q.Parent, "organization_id": &q.Organization} {
		if value := values.Get(key); value != "" {
			id, err := bson.ObjectIDFromHex(value)
			if err != nil || id.IsZero() {
				return q, invalid
			}
			*target = id
		}
	}
	for key, target := range map[string]*string{"date_start": &q.Start, "date_end": &q.End} {
		if value := values.Get(key); value != "" {
			if parsed, err := time.Parse("2006-01-02", value); err != nil || parsed.Format("2006-01-02") != value {
				return q, invalid
			}
			*target = value
		}
	}
	if q.Start != "" && q.End != "" && q.Start > q.End {
		return q, invalid
	}
	q.Search, q.Title = strings.ToLower(values.Get("search")), strings.ToLower(values.Get("title"))
	q.Tag, q.Location = strings.ToLower(values.Get("tag")), strings.ToLower(values.Get("location"))
	seen := map[string]bool{}
	for _, value := range strings.Split(values.Get("city"), ",") {
		city := strings.ToLower(strings.TrimSpace(value))
		if city != "" && !seen[city] {
			seen[city] = true
			q.Cities = append(q.Cities, city)
		}
	}
	if len(q.Cities) > 20 {
		return q, invalid
	}
	sort.Strings(q.Cities)
	return q, nil
}

func listingFilter(q listingQuery) bson.M {
	filter := publicVisibility()
	// A public date range must not match malformed arrays or non-ObjectId rows.
	clauses := object(filter["$expr"])["$and"].(bson.A)
	object(filter["$expr"])["$and"] = append(clauses,
		bson.M{"$eq": bson.A{bson.M{"$type": "$date"}, "string"}},
		bson.M{"$eq": bson.A{bson.M{"$type": "$_id"}, "objectId"}})
	if !q.IncludeCancelled && q.Parent.IsZero() && q.Organization.IsZero() {
		filter["cancelled"] = bson.M{"$ne": true}
	}
	if !q.Parent.IsZero() {
		filter["parent"] = bson.M{"$in": bson.A{q.Parent, q.Parent.Hex()}}
	}
	if !q.Organization.IsZero() {
		filter["organizers"] = bson.M{"$elemMatch": bson.M{"organization_id": bson.M{"$in": bson.A{q.Organization, q.Organization.Hex()}}}}
	}
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
	if len(dates) > 0 {
		filter["date"] = dates
	}
	and := filter["$and"].(bson.A)
	literal := func(value string, exact bool) bson.Regex {
		pattern := regexp.QuoteMeta(value)
		if exact {
			pattern = "^" + pattern + "$"
		}
		return bson.Regex{Pattern: pattern, Options: "i"}
	}
	translated := func(fields []string, value string, exact bool) {
		if value == "" {
			return
		}
		or := bson.A{}
		for _, field := range fields {
			or = append(or, bson.M{field: literal(value, exact)})
			if field == "title" || field == "description" || field == "tags" {
				for _, lang := range []string{"fi", "en", "sv"} {
					or = append(or, bson.M{"translations." + lang + "." + field: literal(value, exact)})
				}
			}
		}
		and = append(and, bson.M{"$or": or})
	}
	translated([]string{"title", "description", "tags", "address"}, q.Search, false)
	translated([]string{"title"}, q.Title, false)
	translated([]string{"tags"}, q.Tag, true)
	if q.Location != "" {
		and = append(and, bson.M{"address": literal(q.Location, false)})
	}
	if len(q.Cities) > 0 {
		cities := bson.A{}
		for _, city := range q.Cities {
			cities = append(cities, literal(city, true))
		}
		and = append(and, bson.M{"city": bson.M{"$in": cities}})
	}
	filter["$and"] = and
	return filter
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
	if day, ok := payload["date"].(string); ok {
		if parsed, err := time.Parse("2006-01-02", day); err == nil {
			card["date_display"] = parsed.Format("02.01.2006")
		}
	}
	card["cover_image"] = ""
	for _, field := range []string{"cover_picture", "cover_image", "preview_image", "img", "gallery_images", "images"} {
		if images := galleryImages(doc[field]); len(images) > 0 {
			card["cover_image"] = images[0]
			break
		}
	}
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
