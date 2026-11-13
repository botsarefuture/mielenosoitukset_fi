package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"regexp"
	"strings"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
)

const cancellationLinkPrefix = "/api/cancellation-links/"

// Flask issues secrets.token_urlsafe(32), 43 characters. Anything outside this
// alphabet or far longer cannot be a token and is treated as unknown.
var cancellationTokenPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,128}$`)

// cancellationLinkState is what the public cancellation page needs and nothing
// more: never the organizer email, organization or token hash.
type cancellationLinkState struct {
	State               string                `json:"state"`
	Demo                *cancellationLinkDemo `json:"demo,omitempty"`
	CancellationPending bool                  `json:"cancellation_pending,omitempty"`
	CanCancelDirectly   bool                  `json:"can_cancel_directly,omitempty"`
}

type cancellationLinkDemo struct {
	Title     string `json:"title"`
	Date      string `json:"date"`
	City      string `json:"city"`
	Cancelled bool   `json:"cancelled"`
}

// cancellationLinkRecord is the stored token plus its demonstration, as read.
type cancellationLinkRecord struct {
	Found     bool
	Expires   time.Time
	Used      bool
	Official  bool
	Demo      bson.M
	DemoFound bool
}

// cancellationLinkStatus mirrors the GET branch of Flask's cancel_demo_with_token.
// Later checks override earlier ones exactly as there: unknown, expired, used,
// then a missing demonstration. The read changes nothing; the POST that cancels
// or requests cancellation, and marks the token used, stays in Flask.
func cancellationLinkStatus(record cancellationLinkRecord, now time.Time) cancellationLinkState {
	if !record.Found {
		return cancellationLinkState{State: "invalid"}
	}
	state := "ready"
	if !record.Expires.IsZero() && record.Expires.Before(now) {
		state = "expired"
	}
	if record.Used {
		state = "used"
	}
	if !record.DemoFound {
		state = "missing-demonstration"
	}
	if state != "ready" {
		return cancellationLinkState{State: state}
	}
	cancelled, _ := record.Demo["cancelled"].(bool)
	pending, _ := record.Demo["cancellation_requested"].(bool)
	title, _ := record.Demo["title"].(string)
	city, _ := record.Demo["city"].(string)
	return cancellationLinkState{
		State:               "ready",
		Demo:                &cancellationLinkDemo{Title: title, Date: cancellationDate(record.Demo["date"]), City: city, Cancelled: cancelled},
		CancellationPending: pending,
		CanCancelDirectly:   record.Official,
	}
}

// cancellationDate formats like Flask: dd.mm.yyyy for a date or an ISO string,
// and the stored text unchanged when it is not a valid ISO date.
func cancellationDate(value any) string {
	switch date := value.(type) {
	case bson.DateTime:
		return date.Time().UTC().Format("02.01.2006")
	case time.Time:
		return date.UTC().Format("02.01.2006")
	case string:
		for _, layout := range []string{"2006-01-02", "2006-01-02T15:04:05", "2006-01-02T15:04:05Z07:00"} {
			if parsed, err := time.Parse(layout, strings.TrimSpace(date)); err == nil {
				return parsed.Format("02.01.2006")
			}
		}
		return date
	}
	return ""
}

// cancellationLinkHandler serves GET /api/cancellation-links/<token> so the React
// host can render the organizer cancellation page without Flask.
//
// The token is a bearer secret: responses are no-store and are not cached in
// Go or the host, and an unknown, expired and used token all return 200 with a
// state, so the status code alone does not reveal which tokens exist. A failed
// read is 503, never a state.
func cancellationLinkHandler(next http.Handler, read func(context.Context, string) (cancellationLinkRecord, error)) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasPrefix(r.URL.Path, cancellationLinkPrefix) {
			next.ServeHTTP(w, r)
			return
		}
		w.Header().Set("Cache-Control", "no-store")
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			w.Header().Set("Allow", "GET, HEAD")
			writeError(w, http.StatusMethodNotAllowed, "method not allowed")
			return
		}
		token := strings.TrimPrefix(r.URL.Path, cancellationLinkPrefix)
		if !cancellationTokenPattern.MatchString(token) {
			writeJSON(w, http.StatusOK, cancellationLinkState{State: "invalid"})
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()
		sum := sha256.Sum256([]byte(token))
		record, err := read(ctx, hex.EncodeToString(sum[:]))
		if err != nil {
			writeError(w, http.StatusServiceUnavailable, "cancellation link unavailable")
			return
		}
		writeJSON(w, http.StatusOK, cancellationLinkStatus(record, time.Now().UTC()))
	})
}

func readCancellationLink(db *mongo.Database) func(context.Context, string) (cancellationLinkRecord, error) {
	return func(ctx context.Context, hash string) (cancellationLinkRecord, error) {
		var token bson.M
		err := db.Collection("demo_cancellation_tokens").FindOne(ctx, bson.M{"token_hash": hash}).Decode(&token)
		if err == mongo.ErrNoDocuments {
			return cancellationLinkRecord{}, nil
		}
		if err != nil {
			return cancellationLinkRecord{}, err
		}
		record := cancellationLinkRecord{Found: true, Used: token["used_at"] != nil}
		switch expires := token["expires_at"].(type) {
		case bson.DateTime:
			record.Expires = expires.Time()
		case time.Time:
			record.Expires = expires
		}
		record.Official, _ = token["official_contact"].(bool)
		if id, ok := token["demo_id"]; ok {
			err = db.Collection("demonstrations").FindOne(ctx, bson.M{"_id": id}).Decode(&record.Demo)
			if err != nil && err != mongo.ErrNoDocuments {
				return cancellationLinkRecord{}, err
			}
			record.DemoFound = err == nil
		}
		return record, nil
	}
}
