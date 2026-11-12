package main

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

// City admin applications (phase 2 of docs/city-admin-applications.md).
//
// Go only accepts and stores the application. Flask's background job turns a
// stored application into a `city_admin_application` case for global admins,
// and granting the role stays in the existing Flask accounts dashboard. The
// signed-in user is read through the same Flask session bridge as submissions.

const (
	applicationsPath     = "/api/city-admin-applications"
	applicationsMinePath = "/api/city-admin-applications/mine"
	applicationMaxBody   = 32 << 10
)

var applicationExperience = map[string]bool{"none": true, "some": true, "lot": true}

// Statuses an applicant can see. received and in_review count as open.
var applicationOpenStatuses = bson.A{"received", "in_review"}

type applicationInput struct {
	CityKeys   []string `json:"city_keys"`
	About      string   `json:"about"`
	References string   `json:"references"`
	Consent    bool     `json:"consent"`
	Activism   struct {
		Cities            []string `json:"cities"`
		Organizations     string   `json:"organizations"`
		Experience        string   `json:"experience"`
		ExperienceDetails string   `json:"experience_details"`
	} `json:"activism"`
}

type applicationError struct{ code, message string }

func (e applicationError) Error() string { return e.message }

func boundedText(value string, min, max int, code, message string) (string, error) {
	value = strings.TrimSpace(strings.ReplaceAll(value, "\x00", ""))
	if count := utf8.RuneCountInString(value); count < min || count > max {
		return "", applicationError{code, message}
	}
	return value, nil
}

func applicationCities(values []string, min, max int, allowNational bool) ([]string, error) {
	seen := map[string]bool{}
	keys := []string{}
	for _, value := range values {
		key := normalizeCityKey(value)
		if _, known := cityCatalog[key]; !known {
			return nil, applicationError{"APPLY_CITY", "Tuntematon paikkakunta."}
		}
		if !allowNational && nationallyManagedCities[key] {
			return nil, applicationError{"APPLY_NATIONAL_CITY", "Tätä paikkakuntaa hoitaa valtakunnallinen ylläpitotiimi, joten sille ei haeta kaupunkiadmineja."}
		}
		if !seen[key] {
			seen[key] = true
			keys = append(keys, key)
		}
	}
	if len(keys) < min || len(keys) > max {
		return nil, applicationError{"APPLY_CITY_COUNT", "Valitse 1–5 paikkakuntaa."}
	}
	return keys, nil
}

// validateApplication returns the document fields to store, or an
// applicationError whose message is safe to show to the applicant.
func validateApplication(input applicationInput) (bson.M, error) {
	if !input.Consent {
		return nil, applicationError{"APPLY_CONSENT", "Hyväksy hakemuksen käsittely ennen lähettämistä."}
	}
	cities, err := applicationCities(input.CityKeys, 1, 5, false)
	if err != nil {
		return nil, err
	}
	about, err := boundedText(input.About, 50, 3000, "APPLY_ABOUT", "Kerro itsestäsi ja motivaatiostasi 50–3000 merkillä.")
	if err != nil {
		return nil, err
	}
	activeIn, err := applicationCities(input.Activism.Cities, 0, 10, true)
	if err != nil {
		return nil, err
	}
	organizations, err := boundedText(input.Activism.Organizations, 0, 1000, "APPLY_ORGANIZATIONS", "Ryhmien ja järjestöjen kuvaus on liian pitkä.")
	if err != nil {
		return nil, err
	}
	if !applicationExperience[input.Activism.Experience] {
		return nil, applicationError{"APPLY_EXPERIENCE", "Valitse järjestämiskokemuksesi."}
	}
	details, err := boundedText(input.Activism.ExperienceDetails, 0, 2000, "APPLY_EXPERIENCE_DETAILS", "Kokemuksen kuvaus on liian pitkä.")
	if err != nil {
		return nil, err
	}
	references, err := boundedText(input.References, 0, 1000, "APPLY_REFERENCES", "Suosittelijoiden kuvaus on liian pitkä.")
	if err != nil {
		return nil, err
	}
	return bson.M{
		"city_keys": cities,
		"about":     about,
		"activism": bson.M{
			"cities": activeIn, "organizations": organizations,
			"experience": input.Activism.Experience, "experience_details": details,
		},
		"references": references,
	}, nil
}

func readApplication(w http.ResponseWriter, r *http.Request) (applicationInput, error) {
	var input applicationInput
	if !strings.HasPrefix(r.Header.Get("Content-Type"), "application/json") {
		return input, applicationError{"APPLY_FORMAT", "Lähetä hakemus sivuston lomakkeella."}
	}
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, applicationMaxBody))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&input); err != nil {
		return input, applicationError{"APPLY_FORMAT", "Hakemusta ei voitu lukea."}
	}
	if _, err := decoder.Token(); !errors.Is(err, io.EOF) {
		return input, applicationError{"APPLY_FORMAT", "Hakemusta ei voitu lukea."}
	}
	return input, nil
}

func applicationFailure(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, bson.M{"success": false, "error_code": code, "message": message})
}

// applicationAccount checks that the signed-in user may apply: an active,
// confirmed account, the same rule that decides who counts as city admin cover.
func applicationAccount(ctx context.Context, db *mongo.Database, actor bson.ObjectID) (bool, error) {
	var doc bson.M
	err := db.Collection("users").FindOne(ctx, bson.M{"_id": actor},
		options.FindOne().SetProjection(bson.M{"active": 1, "banned": 1, "confirmed": 1, "security_suspension": 1})).Decode(&doc)
	if errors.Is(err, mongo.ErrNoDocuments) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return activeAccount(doc), nil
}

// applicationInsertFailure maps a failed insert to a response. With the optional
// partial unique index on open applications (docs/city-admin-applications.md,
// "Duplicate submissions"), a simultaneous second submission fails with a
// duplicate key error. It gets the same answer as the open-application check
// above, so the form needs no new error code.
func applicationInsertFailure(err error) (int, string, string) {
	if mongo.IsDuplicateKeyError(err) {
		return 409, "APPLY_OPEN_EXISTS", "Sinulla on jo käsittelyssä oleva hakemus. Voit seurata sen tilaa tällä sivulla."
	}
	return 503, "APPLY_SAVE_FAILED", "Hakemusta ei voitu tallentaa. Yritä uudelleen."
}

type applicationSummary struct {
	ID        string    `json:"id"`
	CityKeys  []string  `json:"city_keys"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"created_at"`
}

func cityAdminApplicationHandler(next http.Handler, db *mongo.Database, config submissionConfig) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != applicationsPath && r.URL.Path != applicationsMinePath {
			next.ServeHTTP(w, r)
			return
		}
		w.Header().Set("Cache-Control", "private, no-store")
		w.Header().Set("Vary", "Cookie")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		if config.Origin == "" {
			applicationFailure(w, 503, "APPLY_UNAVAILABLE", "Hakulomake ei ole juuri nyt käytettävissä.")
			return
		}
		mine := r.URL.Path == applicationsMinePath
		if (mine && r.Method != "GET") || (!mine && r.Method != "POST") {
			w.Header().Set("Allow", map[bool]string{true: "GET", false: "POST"}[mine])
			applicationFailure(w, 405, "APPLY_METHOD", "Käytä hakulomaketta.")
			return
		}
		if r.Header.Get("Sec-Fetch-Site") == "cross-site" || (!mine && !submissionOriginAllowed(r.Header.Get("Origin"), config.Origin)) {
			applicationFailure(w, 403, "APPLY_ORIGIN", "Lähetä hakemus sivuston lomakkeella.")
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 8*time.Second)
		defer cancel()
		actor, err := submissionActor(ctx, r, config)
		if err != nil {
			applicationFailure(w, 503, "APPLY_SESSION", "Istunnon tarkistaminen epäonnistui. Yritä uudelleen.")
			return
		}
		if actor.IsZero() {
			applicationFailure(w, 401, "APPLY_SIGN_IN", "Kirjaudu sisään hakeaksesi kaupunkiadminiksi.")
			return
		}
		if mine {
			serveMyApplications(ctx, w, db, actor)
			return
		}
		serveApplication(ctx, w, r, db, config, actor)
	})
}

func serveMyApplications(ctx context.Context, w http.ResponseWriter, db *mongo.Database, actor bson.ObjectID) {
	cursor, err := db.Collection("city_admin_applications").Find(ctx, bson.M{"user_id": actor},
		options.Find().SetProjection(bson.M{"city_keys": 1, "status": 1, "created_at": 1}).
			SetSort(bson.D{{Key: "created_at", Value: -1}}).SetLimit(10))
	if err != nil {
		applicationFailure(w, 503, "APPLY_UNAVAILABLE", "Hakemuksia ei voitu hakea.")
		return
	}
	var rows []struct {
		ID        bson.ObjectID `bson:"_id"`
		CityKeys  []string      `bson:"city_keys"`
		Status    string        `bson:"status"`
		CreatedAt time.Time     `bson:"created_at"`
	}
	if err := cursor.All(ctx, &rows); err != nil {
		applicationFailure(w, 503, "APPLY_UNAVAILABLE", "Hakemuksia ei voitu hakea.")
		return
	}
	items := []applicationSummary{}
	for _, row := range rows {
		items = append(items, applicationSummary{ID: row.ID.Hex(), CityKeys: row.CityKeys, Status: row.Status, CreatedAt: row.CreatedAt})
	}
	writeJSON(w, 200, bson.M{"success": true, "applications": items})
}

func serveApplication(ctx context.Context, w http.ResponseWriter, r *http.Request, db *mongo.Database, config submissionConfig, actor bson.ObjectID) {
	var panicMode struct {
		Panic bool `bson:"panic"`
	}
	err := db.Collection("panic").FindOne(ctx, bson.M{"name": bson.M{"$in": bson.A{"global", "security"}}}).Decode(&panicMode)
	if (err != nil && !errors.Is(err, mongo.ErrNoDocuments)) || panicMode.Panic {
		applicationFailure(w, 503, "APPLY_UNAVAILABLE", "Palvelu ei ole juuri nyt käytettävissä.")
		return
	}
	allowed, err := submissionRate(ctx, db, "apply:"+submissionClient(r, config.Secret))
	if err != nil {
		applicationFailure(w, 503, "APPLY_UNAVAILABLE", "Yritä uudelleen hetken kuluttua.")
		return
	}
	if !allowed {
		w.Header().Set("Retry-After", "60")
		applicationFailure(w, 429, "APPLY_RATE_LIMITED", "Lähetysyrityksiä on liian monta. Odota hetki ja yritä uudelleen.")
		return
	}
	input, err := readApplication(w, r)
	var fields bson.M
	if err == nil {
		fields, err = validateApplication(input)
	}
	var invalid applicationError
	if errors.As(err, &invalid) {
		applicationFailure(w, 400, invalid.code, invalid.message)
		return
	}
	eligible, err := applicationAccount(ctx, db, actor)
	if err != nil {
		applicationFailure(w, 503, "APPLY_UNAVAILABLE", "Yritä uudelleen hetken kuluttua.")
		return
	}
	if !eligible {
		applicationFailure(w, 403, "APPLY_ACCOUNT", "Vahvista sähköpostiosoitteesi ennen hakemista.")
		return
	}
	applications := db.Collection("city_admin_applications")
	open, err := applications.CountDocuments(ctx, bson.M{"user_id": actor, "status": bson.M{"$in": applicationOpenStatuses}}, options.Count().SetLimit(1))
	if err != nil {
		applicationFailure(w, 503, "APPLY_UNAVAILABLE", "Yritä uudelleen hetken kuluttua.")
		return
	}
	if open > 0 {
		applicationFailure(w, 409, "APPLY_OPEN_EXISTS", "Sinulla on jo käsittelyssä oleva hakemus. Voit seurata sen tilaa tällä sivulla.")
		return
	}
	now := time.Now().UTC()
	id := bson.NewObjectID()
	fields["_id"] = id
	fields["user_id"] = actor
	fields["status"] = "received"
	fields["consent_at"] = now
	fields["created_at"] = now
	fields["updated_at"] = now
	// Flask's delivery job creates the admin case and clears this flag.
	fields["case_pending"] = true
	if _, err := applications.InsertOne(ctx, fields); err != nil {
		status, code, message := applicationInsertFailure(err)
		if status == 503 {
			log.Print("City admin application could not be stored")
		}
		applicationFailure(w, status, code, message)
		return
	}
	writeJSON(w, 201, bson.M{"success": true, "id": id.Hex(), "status": "received"})
}
