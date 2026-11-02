package main

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

type submissionConfig struct {
	Origin, Secret string
	SessionSocket  string
	Locales        map[string]bool
}

func submissionConfigFromEnv() (submissionConfig, error) {
	c := submissionConfig{Origin: os.Getenv("PUBLIC_SUBMIT_ORIGIN"), Secret: os.Getenv("PUBLIC_SUBMIT_SECRET"), Locales: map[string]bool{}}
	c.SessionSocket = os.Getenv("PUBLIC_SUBMIT_SESSION_SOCKET")
	if c.Origin == "" && c.Secret == "" {
		return c, nil
	}
	parsed, err := url.Parse(c.Origin)
	localHTTP := err == nil && parsed.Scheme == "http" && net.ParseIP(parsed.Hostname()) != nil && net.ParseIP(parsed.Hostname()).IsLoopback()
	if err != nil || (parsed.Scheme != "https" && !localHTTP) || parsed.Host == "" || parsed.Path != "" || parsed.RawQuery != "" || parsed.Fragment != "" || parsed.User != nil || len(c.Secret) < 32 {
		return c, errors.New("invalid public submission configuration")
	}
	for _, locale := range strings.Split(env("PUBLIC_SUBMIT_LOCALES", "fi"), ",") {
		if locale != "fi" && locale != "en" && locale != "sv" {
			return c, errors.New("invalid submission locale")
		}
		c.Locales[locale] = true
	}
	return c, nil
}

func submissionClientAddress(r *http.Request) string {
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		host = r.RemoteAddr
	}
	if ip := net.ParseIP(host); ip != nil && ip.IsLoopback() {
		forwardedFor := strings.Split(r.Header.Get("X-Forwarded-For"), ",")
		if forwarded := net.ParseIP(strings.TrimSpace(forwardedFor[len(forwardedFor)-1])); forwarded != nil {
			host = forwarded.String()
		}
	}
	return submissionVisitorAddress(r, host)
}

func submissionClient(r *http.Request, secret string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte("submission-rate\x00" + submissionClientAddress(r)))
	return hex.EncodeToString(mac.Sum(nil))
}

func submissionRate(ctx context.Context, db *mongo.Database, key string) (bool, error) {
	now := time.Now().UTC()
	for _, window := range []struct {
		name           string
		seconds, limit int64
	}{{"minute", 60, 5}, {"hour", 3600, 30}} {
		bucket := now.Unix() / window.seconds
		filter := bson.M{"token": "go-rate:" + window.name + ":" + strconv.FormatInt(bucket, 10) + ":" + key}
		var record struct {
			Count int64 `bson:"count"`
		}
		err := db.Collection("demo_submission_tokens").FindOneAndUpdate(ctx, filter, bson.M{"$inc": bson.M{"count": 1}, "$setOnInsert": bson.M{"created_at": now, "status": "go_rate"}}, options.FindOneAndUpdate().SetUpsert(true).SetReturnDocument(options.After)).Decode(&record)
		if err != nil {
			return false, err
		}
		if record.Count > window.limit {
			return false, nil
		}
	}
	return true, nil
}

func submissionFailure(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, bson.M{"success": false, "error_code": code, "message": message})
}

func publicSubmissionHandler(next http.Handler, db *mongo.Database, config submissionConfig) http.Handler {
	inflight := make(chan struct{}, 4)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/submissions" {
			next.ServeHTTP(w, r)
			return
		}
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		if config.Origin == "" {
			submissionFailure(w, 503, "SUBMIT_UNAVAILABLE", "Lomake ei ole juuri nyt käytettävissä.")
			return
		}
		if r.Method != "POST" {
			w.Header().Set("Allow", "POST")
			submissionFailure(w, 405, "SUBMIT_METHOD", "Käytä lomaketta ilmoittamiseen.")
			return
		}
		if r.Header.Get("Origin") != config.Origin || r.Header.Get("Sec-Fetch-Site") == "cross-site" {
			submissionFailure(w, 403, "SUBMIT_ORIGIN", "Lähetä ilmoitus sivuston lomakkeella.")
			return
		}
		if r.URL.RawQuery != "" {
			submissionFailure(w, 400, "SUBMIT_QUERY", "Lähetä tiedot lomakkeella.")
			return
		}
		select {
		case inflight <- struct{}{}:
			defer func() { <-inflight }()
		default:
			w.Header().Set("Retry-After", "5")
			submissionFailure(w, 503, "SUBMIT_BUSY", "Palvelu on ruuhkautunut. Yritä hetken kuluttua uudelleen.")
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 8*time.Second)
		defer cancel()
		var panicMode struct {
			Panic bool `bson:"panic"`
		}
		err := db.Collection("panic").FindOne(ctx, bson.M{"name": "global"}).Decode(&panicMode)
		if (err != nil && !errors.Is(err, mongo.ErrNoDocuments)) || panicMode.Panic {
			submissionFailure(w, 503, "SUBMIT_UNAVAILABLE", "Palvelu ei ole juuri nyt käytettävissä.")
			return
		}
		allowed, err := submissionRate(ctx, db, submissionClient(r, config.Secret))
		if err != nil {
			submissionFailure(w, 503, "SUBMIT_UNAVAILABLE", "Yritä uudelleen hetken kuluttua.")
			return
		}
		if !allowed {
			w.Header().Set("Retry-After", "60")
			submissionFailure(w, 429, "SUBMIT_RATE_LIMITED", "Lähetysyrityksiä on liian monta. Odota hetki ja yritä uudelleen.")
			return
		}
		input, err := readSubmission(w, r, config.Locales)
		if err != nil {
			submissionFailure(w, 400, "SUBMIT_MISSING_FIELDS", err.Error())
			return
		}
		actor, err := submissionActor(ctx, r, config)
		if err != nil {
			submissionFailure(w, 503, "SUBMIT_SESSION", "Istunnon tarkistaminen epäonnistui. Yritä uudelleen.")
			return
		}
		if !actor.IsZero() {
			input.Submitter["actor_id"] = actor
		}
		serveSubmission(ctx, w, r, db, input)
	})
}

func serveSubmission(ctx context.Context, w http.ResponseWriter, r *http.Request, db *mongo.Database, input submissionInput) {
	// Check the token before fingerprint lookup so stale-token protection cannot
	// be bypassed by content that happens to match a different saved submission.
	var binding struct {
		Fingerprint string `bson:"fingerprint"`
	}
	err := db.Collection("demo_submission_tokens").FindOne(ctx, bson.M{"token": input.Token}).Decode(&binding)
	if err == nil && binding.Fingerprint != "" && binding.Fingerprint != input.Fingerprint {
		submissionFailure(w, 409, "SUBMIT_STALE_TOKEN", "Istuntosi on vanhentunut. Päivitä lomake ennen uuden ilmoituksen lähettämistä.")
		return
	}
	if err != nil && !errors.Is(err, mongo.ErrNoDocuments) {
		submissionFailure(w, 503, "SUBMIT_SAVE_FAILED", "Yritä uudelleen hetken kuluttua.")
		return
	}
	id, err := legacySubmissionDuplicate(ctx, db, input)
	if err == nil && id.IsZero() {
		id, err = resumeSubmission(ctx, db, input)
	}
	if err == nil && id.IsZero() && !input.Force {
		var matches []bson.M
		matches, err = submissionConflicts(ctx, db, input)
		if err == nil && len(matches) > 0 {
			if r.Header.Get("X-Requested-With") != "XMLHttpRequest" {
				http.Redirect(w, r, "/submit?conflict=1", http.StatusSeeOther)
				return
			}
			writeJSON(w, 409, bson.M{"success": false, "conflict": true, "message": "Löytyi samankaltaisia ilmoituksia tälle päivälle.", "demos": matches})
			return
		}
	}
	if err == nil && id.IsZero() {
		var reservation submissionReservation
		reservation, err = reserveSubmission(ctx, db, input)
		if err == nil {
			err = finishSubmission(ctx, db, reservation)
			id = reservation.DemoID
		}
	}
	if errors.Is(err, errStaleSubmission) {
		submissionFailure(w, 409, "SUBMIT_STALE_TOKEN", "Päivitä lomake ennen uuden ilmoituksen lähettämistä.")
		return
	}
	if err != nil {
		log.Print("Go submission could not be acknowledged")
		submissionFailure(w, 503, "SUBMIT_SAVE_FAILED", "Tallennusta ei voitu vahvistaa. Yritä uudelleen samalla lomakkeella.")
		return
	}
	if r.Header.Get("X-Requested-With") != "XMLHttpRequest" {
		http.Redirect(w, r, "/submit?sent=1", http.StatusSeeOther)
		return
	}
	writeJSON(w, 200, bson.M{"success": true, "demo_id": id.Hex()})
}

func runSubmissionRecovery(ctx context.Context, db *mongo.Database) {
	ticker := time.NewTicker(time.Minute)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			load, cancel := context.WithTimeout(ctx, 10*time.Second)
			recoverGoSubmissions(load, db)
			// Indexed token prefix plus a bounded batch avoids an unbounded delete.
			cursor, err := db.Collection("demo_submission_tokens").Find(load, bson.M{"token": bson.M{"$regex": "^go-rate:"}, "created_at": bson.M{"$lt": time.Now().Add(-48 * time.Hour)}}, options.Find().SetProjection(bson.M{"_id": 1}).SetLimit(200))
			if err == nil {
				ids := bson.A{}
				for cursor.Next(load) {
					var row struct {
						ID bson.ObjectID `bson:"_id"`
					}
					if cursor.Decode(&row) == nil {
						ids = append(ids, row.ID)
					}
				}
				cursor.Close(load)
				if len(ids) > 0 {
					_, _ = db.Collection("demo_submission_tokens").DeleteMany(load, bson.M{"_id": bson.M{"$in": ids}})
				}
			}
			cancel()
		}
	}
}
