package main

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
)

type calendarMonth struct{ Year, Month int }

func parseCalendarMonth(year, month string) (calendarMonth, error) {
	y, e1 := strconv.Atoi(year)
	m, e2 := strconv.Atoi(month)
	if e1 != nil || e2 != nil || y < 2000 || y > 2100 || m < 1 || m > 12 {
		return calendarMonth{}, errors.New("invalid calendar month")
	}
	return calendarMonth{y, m}, nil
}

func (m calendarMonth) key() string { return fmt.Sprintf("%04d-%02d", m.Year, m.Month) }
func (m calendarMonth) start() time.Time {
	return time.Date(m.Year, time.Month(m.Month), 1, 0, 0, 0, 0, time.UTC)
}

type calendarDay struct {
	Date  string `json:"date"`
	Count int64  `json:"count"`
}
type calendarPayload struct {
	Year  int           `json:"year"`
	Month int           `json:"month"`
	Total int64         `json:"total"`
	Days  []calendarDay `json:"days"`
}
type calendarStore interface {
	FindCalendar(context.Context, calendarMonth) (calendarPayload, error)
}

// Count only the requested month in MongoDB. Never materialize event documents
// or private fields here; selected-day cards use the existing paginated API.
func (s mongoStore) FindCalendar(ctx context.Context, month calendarMonth) (calendarPayload, error) {
	start := month.start()
	filter := publicDatedFilter()
	filter["date"] = bson.M{"$gte": start.Format("2006-01-02"), "$lt": start.AddDate(0, 1, 0).Format("2006-01-02")}
	filter["cancelled"] = bson.M{"$ne": true}
	cursor, err := s.collection.Aggregate(ctx, mongo.Pipeline{
		{{Key: "$match", Value: filter}},
		{{Key: "$group", Value: bson.M{"_id": "$date", "count": bson.M{"$sum": 1}}}},
		{{Key: "$sort", Value: bson.M{"_id": 1}}},
	})
	if err != nil {
		return calendarPayload{}, err
	}
	defer cursor.Close(ctx)
	payload := calendarPayload{Year: month.Year, Month: month.Month, Days: []calendarDay{}}
	for cursor.Next(ctx) {
		var row struct {
			Date  string `bson:"_id"`
			Count int64  `bson:"count"`
		}
		if err := cursor.Decode(&row); err != nil {
			return calendarPayload{}, err
		}
		day, err := time.Parse("2006-01-02", row.Date)
		if err != nil || day.Year() != month.Year || int(day.Month()) != month.Month {
			continue
		}
		payload.Days = append(payload.Days, calendarDay{row.Date, row.Count})
		payload.Total += row.Count
	}
	return payload, cursor.Err()
}

func (a *API) getCalendar(w http.ResponseWriter, r *http.Request) {
	month, err := parseCalendarMonth(r.PathValue("year"), r.PathValue("month"))
	if err != nil {
		writeError(w, 400, "invalid calendar month")
		return
	}
	if len(r.URL.RawQuery) > 512 {
		writeError(w, 400, "invalid query parameters")
		return
	}
	if _, err := parseQuery(r.URL.RawQuery); err != nil {
		writeError(w, 400, "invalid query parameters")
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
