package main

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"net/mail"
	"os"
	"strings"
	"sync/atomic"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

// Fundraising reminder signup (docs/fundraising-reminder.md).
//
// Go only stores the signup and consumes the one-time links. Flask mints the
// confirmation and unsubscribe tokens (it needs the raw value for the e-mail
// link, stores only SHA-256 hashes) and sends every message through the e-mail
// queue. The routes exist only when FUNDRAISING_REMINDER_ENABLED=true, public
// submissions are configured and the unique e-mail index is present.

const (
	reminderPath            = "/api/fundraising/reminder"
	reminderConfirmPath     = reminderPath + "/confirm"
	reminderUnsubscribePath = reminderPath + "/unsubscribe"
	reminderCollection      = "fundraising_reminders"
	reminderMaxBody         = 2 << 10
	// reminderConsentVersion names the consent text shown on the form; change
	// it together with the copy in frontend/src/app/fundraising-reminder.ts.
	reminderConsentVersion = "2026-11-13"
	reminderResendAfter    = 15 * time.Minute
	reminderMaxSends       = 3
)

var reminderAcceptedMessage = "Jos osoite on kelvollinen, lähetämme siihen vahvistusviestin. Muistutus lähetetään vasta, kun olet vahvistanut osoitteen viestin linkistä."

type reminderState struct{ available atomic.Bool }

// Enabled reports whether the signup routes answer.
func (s *reminderState) Enabled() bool { return s != nil && s.available.Load() }

func reminderEnabledFromEnv() bool {
	return strings.EqualFold(strings.TrimSpace(os.Getenv("FUNDRAISING_REMINDER_ENABLED")), "true")
}

// checkReminderIndex requires the unique index on the normalised e-mail
// address, so two simultaneous signups can never create two rows.
func checkReminderIndex(ctx context.Context, db *mongo.Database) error {
	cursor, err := db.Collection(reminderCollection).Indexes().List(ctx)
	if err != nil {
		var commandError mongo.CommandError
		if errors.As(err, &commandError) && commandError.Code == 26 {
			return errors.New("fundraising reminder collection and unique index required")
		}
		return err
	}
	defer cursor.Close(ctx)
	for cursor.Next(ctx) {
		var index struct {
			Key    bson.D `bson:"key"`
			Unique bool   `bson:"unique"`
		}
		if err := cursor.Decode(&index); err != nil {
			return err
		}
		if index.Unique && len(index.Key) == 1 && index.Key[0].Key == "email" {
			return nil
		}
	}
	return errors.New("unique fundraising reminder e-mail index required")
}

// startFundraisingReminder decides at startup whether the routes are on.
func startFundraisingReminder(db *mongo.Database, config submissionConfig) *reminderState {
	state := &reminderState{}
	if !reminderEnabledFromEnv() {
		return state
	}
	if config.Origin == "" {
		log.Print("Fundraising reminder disabled: public submissions are not configured")
		return state
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if err := checkReminderIndex(ctx, db); err != nil {
		log.Print("Fundraising reminder disabled: ", err)
		return state
	}
	state.available.Store(true)
	return state
}

type reminderSignupInput struct {
	Email          string `json:"email"`
	Consent        bool   `json:"consent"`
	ResultsConsent bool   `json:"results_consent"`
	Locale         string `json:"locale"`
	Website        string `json:"website"`
}

type reminderTokenInput struct {
	Token string `json:"token"`
}

type reminderError struct{ code, message string }

func (e reminderError) Error() string { return e.message }

func reminderFailure(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, bson.M{"success": false, "error_code": code, "message": message})
}

// normalizeReminderEmail returns the lower-case address, or "" when it is not
// a plain ASCII address of at most 254 characters.
func normalizeReminderEmail(value string) string {
	value = strings.ToLower(strings.TrimSpace(value))
	if value == "" || len(value) > 254 || strings.Count(value, "@") != 1 {
		return ""
	}
	for _, r := range value {
		if r <= 0x20 || r >= 0x7f || strings.ContainsRune("<>\"(),:;\\[]", r) {
			return ""
		}
	}
	address, err := mail.ParseAddress(value)
	if err != nil || address.Address != value || address.Name != "" {
		return ""
	}
	local, domain, _ := strings.Cut(value, "@")
	if local == "" || len(local) > 64 || !strings.Contains(domain, ".") || strings.HasPrefix(domain, ".") || strings.HasSuffix(domain, ".") || strings.Contains(domain, "..") {
		return ""
	}
	return value
}

func reminderTokenHash(token string) (string, bool) {
	if len(token) < 20 || len(token) > 128 {
		return "", false
	}
	for _, r := range token {
		if !(r >= 'a' && r <= 'z' || r >= 'A' && r <= 'Z' || r >= '0' && r <= '9' || r == '-' || r == '_') {
			return "", false
		}
	}
	sum := sha256.Sum256([]byte(token))
	return hex.EncodeToString(sum[:]), true
}

func reminderEmailKey(email, secret string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte("reminder-email\x00" + email))
	return hex.EncodeToString(mac.Sum(nil))
}

func readReminderJSON(w http.ResponseWriter, r *http.Request, into any) error {
	if !strings.HasPrefix(r.Header.Get("Content-Type"), "application/json") {
		return reminderError{"REMINDER_FORMAT", "Lähetä lomake sivuston lomakkeella."}
	}
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, reminderMaxBody))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(into); err != nil {
		return reminderError{"REMINDER_FORMAT", "Tarkista tiedot ja yritä uudelleen."}
	}
	if _, err := decoder.Token(); !errors.Is(err, io.EOF) {
		return reminderError{"REMINDER_FORMAT", "Tarkista tiedot ja yritä uudelleen."}
	}
	return nil
}

func fundraisingReminderHandler(next http.Handler, db *mongo.Database, config submissionConfig, state *reminderState) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path
		if path != reminderPath && path != reminderConfirmPath && path != reminderUnsubscribePath {
			next.ServeHTTP(w, r)
			return
		}
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		if !state.Enabled() {
			reminderFailure(w, http.StatusNotFound, "REMINDER_UNAVAILABLE", "Muistutuksen tilaus ei ole käytettävissä.")
			return
		}
		if r.Method != http.MethodPost {
			w.Header().Set("Allow", "POST")
			reminderFailure(w, http.StatusMethodNotAllowed, "REMINDER_METHOD", "Käytä sivun lomaketta.")
			return
		}
		// The unsubscribe link must work from a mail client, which sends no
		// Origin; the one-time token is its authorisation. Signup and
		// confirmation come from the page and must be same-origin. There is no
		// session to forge, so no CSRF token exists to check.
		if path != reminderUnsubscribePath &&
			(r.Header.Get("Sec-Fetch-Site") == "cross-site" || !submissionOriginAllowed(r.Header.Get("Origin"), config.Origin)) {
			reminderFailure(w, http.StatusForbidden, "REMINDER_ORIGIN", "Lähetä lomake sivuston lomakkeella.")
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 8*time.Second)
		defer cancel()
		var panicMode struct {
			Panic bool `bson:"panic"`
		}
		err := db.Collection("panic").FindOne(ctx, bson.M{"name": bson.M{"$in": bson.A{"global", "security"}}}).Decode(&panicMode)
		if (err != nil && !errors.Is(err, mongo.ErrNoDocuments)) || panicMode.Panic {
			reminderFailure(w, http.StatusServiceUnavailable, "REMINDER_UNAVAILABLE", "Palvelu ei ole juuri nyt käytettävissä.")
			return
		}
		// Signup and confirm clicks have their own IP limits, so a burst of
		// signups cannot stop someone from confirming. Removal has none: a one-click
		// unsubscribe comes from a mailbox provider's shared servers, and a
		// removal must never be refused. It is a cheap indexed delete by a
		// 256-bit token.
		if path != reminderUnsubscribePath {
			scope, minute, hour := "reminder-signup:", int64(5), int64(20)
			if path == reminderConfirmPath {
				scope, minute, hour = "reminder-confirm:", 10, 60
			}
			allowed, err := windowedRate(ctx, db, scope+submissionClient(r, config.Secret), minute, hour)
			if err != nil {
				reminderFailure(w, http.StatusServiceUnavailable, "REMINDER_UNAVAILABLE", "Yritä uudelleen hetken kuluttua.")
				return
			}
			if !allowed {
				w.Header().Set("Retry-After", "60")
				reminderFailure(w, http.StatusTooManyRequests, "REMINDER_RATE_LIMITED", "Yrityksiä on liian monta. Odota hetki ja yritä uudelleen.")
				return
			}
		}
		switch path {
		case reminderPath:
			serveReminderSignup(ctx, w, r, db, config)
		case reminderConfirmPath:
			serveReminderConfirm(ctx, w, r, db)
		default:
			serveReminderUnsubscribe(ctx, w, r, db)
		}
	})
}

func serveReminderSignup(ctx context.Context, w http.ResponseWriter, r *http.Request, db *mongo.Database, config submissionConfig) {
	var input reminderSignupInput
	if err := readReminderJSON(w, r, &input); err != nil {
		var invalid reminderError
		errors.As(err, &invalid)
		reminderFailure(w, http.StatusBadRequest, invalid.code, invalid.message)
		return
	}
	// A filled honeypot gets the normal answer and stores nothing.
	if strings.TrimSpace(input.Website) != "" {
		writeJSON(w, http.StatusAccepted, bson.M{"success": true, "message": reminderAcceptedMessage})
		return
	}
	if !input.Consent {
		reminderFailure(w, http.StatusBadRequest, "REMINDER_CONSENT", "Hyväksy sähköpostiosoitteen käsittely ennen lähettämistä.")
		return
	}
	email := normalizeReminderEmail(input.Email)
	if email == "" {
		reminderFailure(w, http.StatusBadRequest, "REMINDER_EMAIL", "Tarkista sähköpostiosoite.")
		return
	}
	locale := "fi"
	if config.Locales[input.Locale] {
		locale = input.Locale
	}
	// Past the per-address limit the answer stays the same: nothing is stored
	// and the caller learns nothing about the address.
	perAddress, err := windowedRate(ctx, db, reminderEmailKey(email, config.Secret), 2, 4)
	if err != nil {
		reminderFailure(w, http.StatusServiceUnavailable, "REMINDER_UNAVAILABLE", "Yritä uudelleen hetken kuluttua.")
		return
	}
	if perAddress {
		if err := storeReminderSignup(ctx, db, email, locale, input.ResultsConsent); err != nil {
			log.Print("Fundraising reminder signup could not be stored")
			reminderFailure(w, http.StatusServiceUnavailable, "REMINDER_SAVE_FAILED", "Tilausta ei voitu tallentaa. Yritä uudelleen.")
			return
		}
	}
	writeJSON(w, http.StatusAccepted, bson.M{"success": true, "message": reminderAcceptedMessage})
}

// storeReminderSignup is idempotent: a new address gets a pending row; an
// existing pending one may get its confirmation re-sent (at most three times,
// 15 minutes apart); a confirmed one is left alone. Flask sends the mail.
func storeReminderSignup(ctx context.Context, db *mongo.Database, email, locale string, resultsConsent bool) error {
	rows := db.Collection(reminderCollection)
	now := time.Now().UTC()
	result, err := rows.UpdateOne(ctx, bson.M{"email": email}, bson.M{"$setOnInsert": bson.M{
		"email": email, "status": "pending", "locale": locale,
		"results_consent": resultsConsent, "consent_at": now, "consent_version": reminderConsentVersion,
		"created_at": now, "confirmation_requested_at": now, "confirmation_sent_at": nil, "confirmation_count": 0,
	}}, options.UpdateOne().SetUpsert(true))
	if mongo.IsDuplicateKeyError(err) {
		err = nil
		result = &mongo.UpdateResult{UpsertedCount: 0}
	}
	if err != nil {
		return err
	}
	if result.UpsertedCount > 0 {
		return nil
	}
	_, err = rows.UpdateOne(ctx, bson.M{
		"email": email, "status": "pending",
		"confirmation_sent_at": bson.M{"$lt": now.Add(-reminderResendAfter)},
		"confirmation_count":   bson.M{"$lt": reminderMaxSends},
	}, bson.M{"$set": bson.M{"confirmation_requested_at": now, "confirmation_sent_at": nil}})
	return err
}

func serveReminderConfirm(ctx context.Context, w http.ResponseWriter, r *http.Request, db *mongo.Database) {
	var input reminderTokenInput
	if err := readReminderJSON(w, r, &input); err != nil {
		var invalid reminderError
		errors.As(err, &invalid)
		reminderFailure(w, http.StatusBadRequest, invalid.code, invalid.message)
		return
	}
	hash, ok := reminderTokenHash(input.Token)
	invalidLink := func() {
		reminderFailure(w, http.StatusGone, "REMINDER_LINK_INVALID", "Linkki on vanhentunut tai jo käytetty. Jos olet jo vahvistanut osoitteen, sinun ei tarvitse tehdä mitään. Muuten voit tilata uuden vahvistusviestin lomakkeella.")
	}
	if !ok {
		invalidLink()
		return
	}
	now := time.Now().UTC()
	// One atomic step both checks and consumes the token.
	err := db.Collection(reminderCollection).FindOneAndUpdate(ctx,
		bson.M{"confirm_hash": hash, "confirm_expires_at": bson.M{"$gt": now}, "status": "pending"},
		bson.M{"$set": bson.M{"status": "confirmed", "confirmed_at": now}, "$unset": bson.M{"confirm_hash": "", "confirm_expires_at": ""}},
		options.FindOneAndUpdate().SetProjection(bson.M{"_id": 1})).Err()
	if errors.Is(err, mongo.ErrNoDocuments) {
		invalidLink()
		return
	}
	if err != nil {
		reminderFailure(w, http.StatusServiceUnavailable, "REMINDER_UNAVAILABLE", "Yritä uudelleen hetken kuluttua.")
		return
	}
	writeJSON(w, http.StatusOK, bson.M{"success": true, "status": "confirmed"})
}

func serveReminderUnsubscribe(ctx context.Context, w http.ResponseWriter, r *http.Request, db *mongo.Database) {
	token := ""
	if strings.HasPrefix(r.Header.Get("Content-Type"), "application/json") {
		var input reminderTokenInput
		if err := readReminderJSON(w, r, &input); err != nil {
			reminderFailure(w, http.StatusBadRequest, "REMINDER_FORMAT", "Tarkista tiedot ja yritä uudelleen.")
			return
		}
		token = input.Token
	} else {
		// RFC 8058 one-click: the mail client posts List-Unsubscribe=One-Click
		// to the URL in the header, which carries the token in its query.
		r.Body = http.MaxBytesReader(w, r.Body, reminderMaxBody)
		if err := r.ParseForm(); err != nil {
			reminderFailure(w, http.StatusBadRequest, "REMINDER_FORMAT", "Pyyntöä ei voitu lukea.")
			return
		}
		token = r.URL.Query().Get("t")
		if token == "" {
			token = r.PostForm.Get("token")
		}
	}
	hash, ok := reminderTokenHash(token)
	if !ok {
		reminderFailure(w, http.StatusGone, "REMINDER_LINK_INVALID", "Linkki ei kelpaa.")
		return
	}
	// Deleting twice is harmless and answers the same, so the response never
	// tells whether an address was registered.
	if _, err := db.Collection(reminderCollection).DeleteOne(ctx, bson.M{"unsubscribe_hashes": hash}); err != nil {
		reminderFailure(w, http.StatusServiceUnavailable, "REMINDER_UNAVAILABLE", "Yritä uudelleen hetken kuluttua.")
		return
	}
	writeJSON(w, http.StatusOK, bson.M{"success": true})
}

// withReminderFlag tells the page whether to show the signup form. The value
// comes from the running API, never from the details file.
func withReminderFlag(body []byte, enabled bool) []byte {
	var object map[string]any
	if json.Unmarshal(body, &object) != nil {
		return body
	}
	if _, present := object["reminder_signup"]; !present && !enabled {
		return body
	}
	delete(object, "reminder_signup")
	if enabled {
		object["reminder_signup"] = true
	}
	out, err := json.Marshal(object)
	if err != nil {
		return body
	}
	return append(out, '\n')
}
