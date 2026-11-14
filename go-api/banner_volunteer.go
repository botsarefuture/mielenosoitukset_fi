package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

// Pride banner carrier signup (docs/pride-banner-volunteers.md).
//
// A second list on the fundraising reminder system (docs/fundraising-reminder.md):
// the same guards, rate limits, double opt-in, hashed one-time tokens and
// one-click removal, with its own collection, routes and fields. Go stores the
// signup and consumes the links; Flask mints the tokens and sends the mail.

const (
	bannerPath            = "/api/pride-banner/volunteer"
	bannerConfirmPath     = bannerPath + "/confirm"
	bannerUnsubscribePath = bannerPath + "/unsubscribe"
	bannerCollection      = "pride_banner_volunteers"
	bannerMaxBody         = 8 << 10
	// bannerConsentVersion names the consent text on the form; change it together
	// with prideVolunteerCopy.consent in frontend/src/app/pride-volunteer.ts.
	bannerConsentVersion = "2026-11-13"
)

var bannerAcceptedMessage = "Jos osoite on kelvollinen, lähetämme siihen vahvistusviestin. Ilmoittautuminen tulee voimaan vasta, kun olet vahvistanut sen viestin linkistä."

func bannerEnabledFromEnv() bool {
	return strings.EqualFold(strings.TrimSpace(os.Getenv("PRIDE_BANNER_SIGNUP_ENABLED")), "true")
}

// startPrideBannerSignup decides at startup whether the routes are on. Like the
// reminder, they need public submissions and the unique e-mail index.
func startPrideBannerSignup(db *mongo.Database, config submissionConfig) *reminderState {
	state := &reminderState{}
	if !bannerEnabledFromEnv() {
		return state
	}
	if config.Origin == "" {
		log.Print("Pride banner signup disabled: public submissions are not configured")
		return state
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if err := checkListEmailIndex(ctx, db, bannerCollection, "pride banner signup"); err != nil {
		log.Print("Pride banner signup disabled: ", err)
		return state
	}
	state.available.Store(true)
	return state
}

func prideBannerHandler(next http.Handler, db *mongo.Database, config submissionConfig, state *reminderState) http.Handler {
	return reminderListHandler(next, db, config, state, reminderList{
		signupPath: bannerPath, confirmPath: bannerConfirmPath, unsubscribePath: bannerUnsubscribePath,
		collection: bannerCollection, rateScope: "banner",
		unavailable: "Ilmoittautuminen ei ole käytettävissä.",
		signup:      serveBannerSignup,
	})
}

type bannerSignupInput struct {
	Name    string `json:"name"`
	Email   string `json:"email"`
	City    string `json:"city"`
	Pride   string `json:"pride"`
	Unsure  bool   `json:"unsure"`
	Note    string `json:"note"`
	Consent bool   `json:"consent"`
	Locale  string `json:"locale"`
	Website string `json:"website"`
}

// cleanBannerText trims the value, drops control characters (a line break is
// kept in the note only) and reports false when it is not valid UTF-8 or longer
// than max characters. Nothing is rewritten beyond that: the page escapes text on
// output and the mails never include it.
func cleanBannerText(value string, max int, multiline bool) (string, bool) {
	if !utf8.ValidString(value) {
		return "", false
	}
	value = strings.Map(func(r rune) rune {
		if r == '\n' && multiline {
			return r
		}
		if r == '\r' && multiline {
			return -1
		}
		// Format characters (right-to-left overrides, zero-width marks) can disguise text.
		if unicode.IsControl(r) || unicode.Is(unicode.Cf, r) || r == ' ' || r == ' ' {
			if multiline && r == '\t' {
				return ' '
			}
			return -1
		}
		return r
	}, value)
	value = strings.TrimSpace(value)
	return value, utf8.RuneCountInString(value) <= max
}

func serveBannerSignup(ctx context.Context, w http.ResponseWriter, r *http.Request, db *mongo.Database, config submissionConfig) {
	var input bannerSignupInput
	if err := readListJSON(w, r, &input, bannerMaxBody); err != nil {
		reminderFailure(w, http.StatusBadRequest, "REMINDER_FORMAT", "Tarkista tiedot ja yritä uudelleen.")
		return
	}
	// A filled honeypot gets the normal answer and stores nothing.
	if strings.TrimSpace(input.Website) != "" {
		writeJSON(w, http.StatusAccepted, bson.M{"success": true, "message": bannerAcceptedMessage})
		return
	}
	if !input.Consent {
		reminderFailure(w, http.StatusBadRequest, "BANNER_CONSENT", "Anna lupa tietojen tallentamiseen ennen lähettämistä.")
		return
	}
	name, nameOK := cleanBannerText(input.Name, 60, false)
	if !nameOK || name == "" {
		reminderFailure(w, http.StatusBadRequest, "BANNER_NAME", "Kirjoita etunimi tai nimimerkki.")
		return
	}
	city, cityOK := cleanBannerText(input.City, 80, false)
	pride, prideOK := cleanBannerText(input.Pride, 120, false)
	note, noteOK := cleanBannerText(input.Note, 500, true)
	if !cityOK || !prideOK || !noteOK {
		reminderFailure(w, http.StatusBadRequest, "BANNER_FORMAT", "Jokin kentistä on liian pitkä. Lyhennä tekstiä ja yritä uudelleen.")
		return
	}
	email := normalizeReminderEmail(input.Email)
	if email == "" {
		reminderFailure(w, http.StatusBadRequest, "REMINDER_EMAIL", "Tarkista sähköpostiosoite.")
		return
	}
	if input.Unsure {
		pride = ""
	}
	locale := "fi"
	if config.Locales[input.Locale] {
		locale = input.Locale
	}
	// Past the per-address limit the answer stays the same: nothing is stored
	// and the caller learns nothing about the address.
	perAddress, err := windowedRate(ctx, db, listEmailKey("banner-email", email, config.Secret), 2, 4)
	if err != nil {
		reminderFailure(w, http.StatusServiceUnavailable, "REMINDER_UNAVAILABLE", "Yritä uudelleen hetken kuluttua.")
		return
	}
	if perAddress {
		if err := storeBannerSignup(ctx, db, bannerRow{Email: email, Name: name, City: city, Pride: pride, Unsure: input.Unsure, Note: note, Locale: locale}); err != nil {
			log.Print("Pride banner signup could not be stored")
			reminderFailure(w, http.StatusServiceUnavailable, "REMINDER_SAVE_FAILED", "Ilmoittautumista ei voitu tallentaa. Yritä uudelleen.")
			return
		}
	}
	// The same answer for a new, a pending and an already confirmed address.
	writeJSON(w, http.StatusAccepted, bson.M{"success": true, "message": bannerAcceptedMessage})
}

type bannerRow struct {
	Email, Name, City, Pride, Note, Locale string
	Unsure                                 bool
}

// storeBannerSignup is idempotent like storeReminderSignup: a new address gets
// a pending row; a repeat of a pending one may get its confirmation re-sent (at
// most three times, 15 minutes apart) and keeps the first answers; a confirmed
// one is left alone. Flask sends the mail.
func storeBannerSignup(ctx context.Context, db *mongo.Database, row bannerRow) error {
	rows := db.Collection(bannerCollection)
	now := time.Now().UTC()
	result, err := rows.UpdateOne(ctx, bson.M{"email": row.Email}, bson.M{"$setOnInsert": bson.M{
		"email": row.Email, "name": row.Name, "city": row.City, "pride": row.Pride, "unsure": row.Unsure, "note": row.Note,
		"status": "pending", "locale": row.Locale,
		"consent_at": now, "consent_version": bannerConsentVersion,
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
		"email": row.Email, "status": "pending",
		"confirmation_sent_at": bson.M{"$lt": now.Add(-reminderResendAfter)},
		"confirmation_count":   bson.M{"$lt": reminderMaxSends},
	}, bson.M{"$set": bson.M{"confirmation_requested_at": now, "confirmation_sent_at": nil}})
	return err
}
