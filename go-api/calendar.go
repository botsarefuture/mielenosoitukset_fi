package main

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
)

// Month zero selects the whole year; City is an optional canonical catalog key.
type calendarMonth struct {
	Year, Month int
	City        string
}

func parseCalendarMonth(year, month string) (calendarMonth, error) {
	y, e1 := strconv.Atoi(year)
	m, e2 := strconv.Atoi(month)
	if e1 != nil || e2 != nil || y < 2000 || y > 2100 || m < 1 || m > 12 {
		return calendarMonth{}, errors.New("invalid calendar month")
	}
	return calendarMonth{Year: y, Month: m}, nil
}

func parseCalendarRequest(year, month, raw string) (calendarMonth, error) {
	if len(raw) > 512 {
		return calendarMonth{}, errors.New("invalid calendar parameters")
	}
	annual := month == ""
	if annual {
		month = "1"
	}
	period, err := parseCalendarMonth(year, month)
	if err != nil {
		return period, err
	}
	if annual {
		period.Month = 0
	}
	values, err := url.ParseQuery(raw)
	if err != nil {
		return period, err
	}
	for key, items := range values {
		if (key != "city" && key != "lang") || len(items) != 1 {
			return period, errors.New("invalid calendar parameters")
		}
	}
	if city := values.Get("city"); city != "" {
		canonical, ok := cityCatalog[normalizeCityKey(city)]
		if !ok {
			return period, errors.New("unknown calendar city")
		}
		period.City = canonical.Key
	}
	values.Del("city")
	_, err = parseQuery(values.Encode())
	return period, err
}

func (m calendarMonth) key() string { return fmt.Sprintf("%04d-%02d:%s", m.Year, m.Month, m.City) }
func (m calendarMonth) start() time.Time {
	return time.Date(m.Year, time.Month(max(m.Month, 1)), 1, 0, 0, 0, 0, time.UTC)
}

type calendarDay struct {
	Date  string `json:"date"`
	Count int64  `json:"count"`
}
type calendarPayload struct {
	Year  int           `json:"year"`
	Month int           `json:"month"`
	City  string        `json:"city,omitempty"`
	Total int64         `json:"total"`
	Days  []calendarDay `json:"days"`
}
type calendarStore interface {
	FindCalendar(context.Context, calendarMonth) (calendarPayload, error)
}

// Count only the requested period in MongoDB. Never materialize event documents
// or private fields here; selected-day cards use the existing paginated API.
func (s mongoStore) FindCalendar(ctx context.Context, month calendarMonth) (calendarPayload, error) {
	start := month.start()
	end := start.AddDate(0, 1, 0)
	if month.Month == 0 {
		end = start.AddDate(1, 0, 0)
	}
	filter := publicDatedFilter()
	filter["date"] = bson.M{"$gte": start.Format("2006-01-02"), "$lt": end.Format("2006-01-02")}
	filter["cancelled"] = bson.M{"$ne": true}
	if month.City != "" {
		filter["$and"] = listingSearch(listingQuery{Cities: []string{cityCatalog[month.City].Name}}, filter["$and"].(bson.A))
	}
	cursor, err := s.collection.Aggregate(ctx, mongo.Pipeline{
		{{Key: "$match", Value: filter}},
		{{Key: "$group", Value: bson.M{"_id": "$date", "count": bson.M{"$sum": 1}}}},
		{{Key: "$sort", Value: bson.M{"_id": 1}}},
	})
	if err != nil {
		return calendarPayload{}, err
	}
	defer cursor.Close(ctx)
	payload := calendarPayload{Year: month.Year, Month: month.Month, City: month.City, Days: []calendarDay{}}
	for cursor.Next(ctx) {
		var row struct {
			Date  string `bson:"_id"`
			Count int64  `bson:"count"`
		}
		if err := cursor.Decode(&row); err != nil {
			return calendarPayload{}, err
		}
		day, err := time.Parse("2006-01-02", row.Date)
		if err != nil || day.Year() != month.Year || (month.Month != 0 && int(day.Month()) != month.Month) {
			continue
		}
		payload.Days = append(payload.Days, calendarDay{row.Date, row.Count})
		payload.Total += row.Count
	}
	return payload, cursor.Err()
}

func (a *API) getCalendar(w http.ResponseWriter, r *http.Request) {
	month, err := parseCalendarRequest(r.PathValue("year"), r.PathValue("month"), r.URL.RawQuery)
	if err != nil {
		writeError(w, 400, "invalid calendar month")
		return
	}
	source, ok := a.store.(interface {
		FindCalendarJSON(context.Context, calendarMonth) ([]byte, error)
	})
	if !ok {
		writeError(w, 503, "service unavailable")
		return
	}
	data, err := source.FindCalendarJSON(r.Context(), month)
	if err != nil {
		writeError(w, 503, "service unavailable")
		return
	}
	w.Header().Set("Cache-Control", "public, max-age=60, s-maxage=300")
	writeJSONBytes(w, 200, data)
}
