package main

// Write routes for the React /developer pages (docs/developer-react-write-controls.md).
//
// Off unless DEVELOPER_WRITES_ENABLED=true (and the auth bridge is on). Flask
// stays the authority for login; these routes only act for the account the
// bridge resolves, on documents Flask already uses (developer_apps, api_tokens,
// api_usage), with no schema change. Token secrets are shown once and stored as
// SHA-256 hashes, exactly like create_token. client_secret is stored in the same
// plaintext form Flask uses, because hashing it would be a schema change that
// needs maintainer approval (docs/developer-react-write-controls.md). Run a single
// Go instance: the CSRF key and the rate limit live in process memory.
//
// Not here on purpose: scope requests and the access request. Flask sends an
// email for both and Go has no mail sender, so React keeps posting those to the
// unchanged Flask endpoints. Privileged scopes (admin, mcp.admin) need a step-up
// that only Flask can verify, so Go refuses them.

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

const (
	developerTokensPath   = "/api/developer/tokens"
	developerTokensPrefix = "/api/developer/tokens/"
	developerCSRFHeader   = "X-CSRF-Token"
	developerCSRFLife     = 12 * time.Hour
	developerWriteBody    = 4 << 10
	developerWritesPerMin = 20
	developerMaxApps      = 50
	developerMaxTokens    = 150
)

var (
	developerSupportedScopes  = map[string]bool{"read": true, "write": true, "admin": true, "mcp.admin": true, "submit_demonstrations": true}
	developerPrivilegedScopes = map[string]bool{"admin": true, "mcp.admin": true}
	developerTokenTypes       = map[string]time.Duration{"short": 48 * time.Hour, "long": 90 * 24 * time.Hour, "session": 168 * time.Hour}
	errDeveloperNotEligible   = errors.New("account cannot receive tokens")
)

// developerWriteStore holds every write. Each call is scoped to the owner.
type developerWriteStore interface {
	AccessEnabled(ctx context.Context, user bson.ObjectID) (bool, error)
	App(ctx context.Context, owner, id bson.ObjectID) (*developerApp, error)
	// CanReceiveTokens mirrors create_token: not suspended, inactive, banned or god.
	CanReceiveTokens(ctx context.Context, user bson.ObjectID) (bool, error)
	CountApps(ctx context.Context, owner bson.ObjectID) (int64, error)
	CountTokens(ctx context.Context, owner, appID bson.ObjectID) (int64, error)
	CreateApp(ctx context.Context, doc bson.M) (bson.ObjectID, error)
	RotateApp(ctx context.Context, owner, id bson.ObjectID, clientID, clientSecret string) (bool, error)
	InsertToken(ctx context.Context, doc bson.M) error
	RevokeToken(ctx context.Context, owner, id bson.ObjectID) (bool, error)
	Audit(ctx context.Context, doc bson.M) error
}

type developerWrites struct {
	store   developerWriteStore
	origin  string
	key     []byte
	now     func() time.Time
	mu      sync.Mutex
	windows map[string]*developerWindow
}

type developerWindow struct {
	start time.Time
	count int
}

func newDeveloperWrites(store developerWriteStore, origin string) *developerWrites {
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		return nil
	}
	return &developerWrites{store: store, origin: strings.TrimRight(origin, "/"), key: key, now: time.Now, windows: map[string]*developerWindow{}}
}

// csrfToken is bound to the account and expires. It travels in the response
// body of the same-origin GET and must come back in a header, so a page on
// another site can neither read nor guess it.
func (d *developerWrites) csrfToken(actor string) string {
	nonce := make([]byte, 12)
	rand.Read(nonce)
	expiry := strconv.FormatInt(d.now().Add(developerCSRFLife).Unix(), 10)
	body := expiry + "." + hex.EncodeToString(nonce)
	return body + "." + d.mac(actor, body)
}

func (d *developerWrites) mac(actor, body string) string {
	m := hmac.New(sha256.New, d.key)
	m.Write([]byte(actor + "|" + body))
	return hex.EncodeToString(m.Sum(nil))
}

func (d *developerWrites) csrfValid(actor, token string) bool {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return false
	}
	expiry, err := strconv.ParseInt(parts[0], 10, 64)
	if err != nil || d.now().Unix() > expiry {
		return false
	}
	want := d.mac(actor, parts[0]+"."+parts[1])
	return subtle.ConstantTimeCompare([]byte(want), []byte(parts[2])) == 1
}

func (d *developerWrites) allow(actor string) bool {
	d.mu.Lock()
	defer d.mu.Unlock()
	now := d.now()
	for k, w := range d.windows { // bounded by active accounts per minute
		if now.Sub(w.start) > time.Minute {
			delete(d.windows, k)
		}
	}
	w := d.windows[actor]
	if w == nil {
		w = &developerWindow{start: now}
		d.windows[actor] = w
	}
	w.count++
	return w.count <= developerWritesPerMin
}

// route reports whether the request is one of the write routes.
func developerWriteRoute(r *http.Request) bool {
	p := r.URL.Path
	switch {
	case p == developerAppPrefix[:len(developerAppPrefix)-1] || p == developerTokensPath:
		return r.Method == http.MethodPost
	case strings.HasPrefix(p, developerTokensPrefix):
		return r.Method == http.MethodDelete
	case strings.HasPrefix(p, developerAppPrefix):
		// Exactly "<24 hex>/token" or "<24 hex>/rotate", nothing longer.
		id, action, found := strings.Cut(strings.TrimPrefix(p, developerAppPrefix), "/")
		return r.Method == http.MethodPost && found && authObjectID.MatchString(id) && (action == "token" || action == "rotate")
	}
	return false
}

func developerSecret(n int) (string, error) {
	raw := make([]byte, n)
	if _, err := rand.Read(raw); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(raw), nil
}

func developerHash(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}

func (d *developerWrites) serve(w http.ResponseWriter, r *http.Request, owner bson.ObjectID) {
	actor := owner.Hex()
	// Same-origin only, on top of the CSRF token: browsers always send Sec-Fetch-Site.
	if r.Header.Get("Sec-Fetch-Site") != "same-origin" {
		writeError(w, http.StatusForbidden, "forbidden")
		return
	}
	if origin := r.Header.Get("Origin"); origin != "" && origin != d.origin {
		writeError(w, http.StatusForbidden, "forbidden")
		return
	}
	if r.Method == http.MethodPost && !strings.HasPrefix(r.Header.Get("Content-Type"), "application/json") {
		writeError(w, http.StatusUnsupportedMediaType, "json required")
		return
	}
	if !d.csrfValid(actor, r.Header.Get(developerCSRFHeader)) {
		writeError(w, http.StatusForbidden, "invalid csrf token")
		return
	}
	if !d.allow(actor) {
		w.Header().Set("Retry-After", "60")
		writeError(w, http.StatusTooManyRequests, "too many requests")
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()
	err := d.dispatch(ctx, w, r, owner)
	if err != nil {
		log.Printf("Developer write failed (%s)", dbErrorKind(err))
		writeError(w, http.StatusServiceUnavailable, "service unavailable")
	}
}

func decodeDeveloperBody(w http.ResponseWriter, r *http.Request, into any) bool {
	data, err := io.ReadAll(http.MaxBytesReader(w, r.Body, developerWriteBody))
	if err == nil {
		dec := json.NewDecoder(strings.NewReader(string(data)))
		err = dec.Decode(into)
	}
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid request")
		return false
	}
	return true
}

func (d *developerWrites) dispatch(ctx context.Context, w http.ResponseWriter, r *http.Request, owner bson.ObjectID) error {
	path := r.URL.Path
	if r.Method == http.MethodDelete { // revoke does not need developer access: owners can always remove tokens
		raw := strings.TrimPrefix(path, developerTokensPrefix)
		id, err := bson.ObjectIDFromHex(raw)
		if err != nil || !authObjectID.MatchString(raw) {
			writeError(w, http.StatusNotFound, "not found")
			return nil
		}
		deleted, err := d.store.RevokeToken(ctx, owner, id)
		if err != nil {
			return err
		}
		if !deleted {
			writeError(w, http.StatusNotFound, "not found")
			return nil
		}
		d.audit(ctx, r, owner, "developer token revoked", bson.M{"token_id": id})
		writeJSON(w, http.StatusOK, map[string]string{"status": "success"})
		return nil
	}
	enabled, err := d.store.AccessEnabled(ctx, owner)
	if err != nil {
		return err
	}
	if !enabled {
		writeError(w, http.StatusForbidden, "developer access not enabled")
		return nil
	}
	switch {
	case path == strings.TrimSuffix(developerAppPrefix, "/"):
		return d.createApp(ctx, w, r, owner)
	case path == developerTokensPath:
		return d.createToken(ctx, w, r, owner, bson.NilObjectID, nil)
	}
	rest := strings.TrimPrefix(path, developerAppPrefix)
	rawID, action, _ := strings.Cut(rest, "/")
	appID, err := bson.ObjectIDFromHex(rawID)
	if err != nil || !authObjectID.MatchString(rawID) {
		writeError(w, http.StatusNotFound, "not found")
		return nil
	}
	app, err := d.store.App(ctx, owner, appID)
	if err != nil {
		return err
	}
	if app == nil {
		writeError(w, http.StatusNotFound, "not found")
		return nil
	}
	if action == "rotate" {
		return d.rotate(ctx, w, r, owner, appID)
	}
	return d.createToken(ctx, w, r, owner, appID, app.AllowedScopes)
}

func (d *developerWrites) audit(ctx context.Context, r *http.Request, owner bson.ObjectID, action string, extra bson.M) {
	doc := bson.M{"user_id": owner, "action": action, "ip_address": submissionClientAddress(r),
		"timestamp": bson.NewDateTimeFromTime(d.now().UTC()), "source": "go-api"}
	for k, v := range extra {
		doc[k] = v
	}
	// A failed audit write must not hide the result of an action that already happened.
	if err := d.store.Audit(ctx, doc); err != nil {
		log.Printf("Developer audit write failed (%s)", dbErrorKind(err))
	}
}

func (d *developerWrites) createApp(ctx context.Context, w http.ResponseWriter, r *http.Request, owner bson.ObjectID) error {
	var body struct {
		Name        string `json:"name"`
		Description string `json:"description"`
	}
	if !decodeDeveloperBody(w, r, &body) {
		return nil
	}
	name, description := strings.TrimSpace(body.Name), strings.TrimSpace(body.Description)
	if name == "" {
		writeError(w, http.StatusBadRequest, "Nimi vaaditaan")
		return nil
	}
	if len([]rune(name)) > 100 || len([]rune(description)) > 1000 {
		writeError(w, http.StatusBadRequest, "Teksti on liian pitkä")
		return nil
	}
	if n, err := d.store.CountApps(ctx, owner); err != nil {
		return err
	} else if n >= developerMaxApps {
		writeError(w, http.StatusConflict, "Sovellusten enimmäismäärä on täynnä")
		return nil
	}
	clientID, err1 := developerSecret(12)
	clientSecret, err2 := developerSecret(24)
	if err1 != nil || err2 != nil {
		return errors.New("random source unavailable")
	}
	created := d.now().UTC()
	id, err := d.store.CreateApp(ctx, bson.M{"name": name, "description": description, "owner_id": owner,
		"client_id": clientID, "client_secret": clientSecret,
		"created_at": bson.NewDateTimeFromTime(created), "allowed_scopes": bson.A{"read"}})
	if err != nil {
		return err
	}
	d.audit(ctx, r, owner, "developer app created", bson.M{"app_id": id})
	writeJSON(w, http.StatusOK, map[string]any{"status": "success", "app": map[string]any{
		"id": id.Hex(), "name": name, "description": description, "client_id": clientID,
		"client_secret": clientSecret, "created_at": created.Format(time.RFC3339)}})
	return nil
}

func (d *developerWrites) rotate(ctx context.Context, w http.ResponseWriter, r *http.Request, owner, appID bson.ObjectID) error {
	clientID, err1 := developerSecret(12)
	clientSecret, err2 := developerSecret(24)
	if err1 != nil || err2 != nil {
		return errors.New("random source unavailable")
	}
	ok, err := d.store.RotateApp(ctx, owner, appID, clientID, clientSecret)
	if err != nil {
		return err
	}
	if !ok {
		writeError(w, http.StatusNotFound, "not found")
		return nil
	}
	d.audit(ctx, r, owner, "developer app secret rotated", bson.M{"app_id": appID})
	writeJSON(w, http.StatusOK, map[string]string{"status": "success", "client_id": clientID, "client_secret": clientSecret})
	return nil
}

// createToken serves both app tokens (appID set, allowed holds the app's scopes)
// and personal tokens (appID zero).
func (d *developerWrites) createToken(ctx context.Context, w http.ResponseWriter, r *http.Request, owner, appID bson.ObjectID, allowed []string) error {
	var body struct {
		Type   string   `json:"type"`
		Scopes []string `json:"scopes"`
	}
	if !decodeDeveloperBody(w, r, &body) {
		return nil
	}
	if body.Type == "" {
		body.Type = "short"
	}
	life, ok := developerTokenTypes[body.Type]
	if !ok {
		writeError(w, http.StatusBadRequest, "Tokenia ei voitu luoda annetuilla tiedoilla.")
		return nil
	}
	if body.Scopes == nil {
		body.Scopes = []string{"read"}
	}
	scopes := []string{}
	seen := map[string]bool{}
	for _, s := range body.Scopes {
		if !developerSupportedScopes[s] {
			writeError(w, http.StatusBadRequest, "Tuntemattomat token-oikeudet")
			return nil
		}
		if developerPrivilegedScopes[s] {
			// Flask requires a global admin plus a recent step-up; only Flask can check that.
			writeError(w, http.StatusForbidden, "Etuoikeutetut avaimet luodaan vanhalla kehittäjäsivulla.")
			return nil
		}
		if !seen[s] {
			seen[s] = true
			scopes = append(scopes, s)
		}
	}
	if !appID.IsZero() {
		permitted := map[string]bool{}
		for _, s := range allowed {
			permitted[s] = true
		}
		kept := scopes[:0]
		for _, s := range scopes {
			if permitted[s] {
				kept = append(kept, s)
			}
		}
		scopes = kept
		if len(scopes) == 0 {
			writeError(w, http.StatusForbidden, "Valitut scopet eivät ole sallittuja tälle sovellukselle.")
			return nil
		}
	}
	if eligible, err := d.store.CanReceiveTokens(ctx, owner); err != nil {
		return err
	} else if !eligible {
		writeError(w, http.StatusBadRequest, "Tokenia ei voitu luoda annetuilla tiedoilla.")
		return nil
	}
	if n, err := d.store.CountTokens(ctx, owner, appID); err != nil {
		return err
	} else if n >= developerMaxTokens {
		writeError(w, http.StatusConflict, "Tokenien enimmäismäärä on täynnä")
		return nil
	}
	token, err := developerSecret(32)
	if err != nil {
		return errors.New("random source unavailable")
	}
	now := d.now().UTC()
	expires := now.Add(life)
	category, appValue := "user", any(nil)
	if !appID.IsZero() {
		category, appValue = "app", appID
	}
	scopeList := make(bson.A, len(scopes))
	for i, s := range scopes {
		scopeList[i] = s
	}
	if err := d.store.InsertToken(ctx, bson.M{"user_id": owner, "app_id": appValue, "session_id": nil,
		"token": developerHash(token), "type": body.Type, "category": category, "scopes": scopeList,
		"rate_limit": "100/minute", "system": false,
		"expires_at": bson.NewDateTimeFromTime(expires), "created_at": bson.NewDateTimeFromTime(now)}); err != nil {
		return err
	}
	extra := bson.M{"category": category, "scopes": scopeList, "type": body.Type}
	if !appID.IsZero() {
		extra["app_id"] = appID
	}
	d.audit(ctx, r, owner, "developer token created", extra)
	out := map[string]any{"status": "success", "token": token, "expires_at": expires.Format(time.RFC3339), "scopes": scopes, "type": body.Type}
	if !appID.IsZero() {
		out["app_id"] = appID.Hex()
	}
	writeJSON(w, http.StatusOK, out)
	return nil
}

func (s mongoDeveloperStore) CanReceiveTokens(ctx context.Context, user bson.ObjectID) (bool, error) {
	var doc bson.M
	err := s.db.Collection("users").FindOne(ctx, bson.M{"_id": user}, options.FindOne().SetProjection(
		bson.M{"security_suspension": 1, "active": 1, "banned": 1, "role": 1})).Decode(&doc)
	if errors.Is(err, mongo.ErrNoDocuments) {
		return true, nil // create_token only refuses when the user document exists
	}
	if err != nil {
		return false, err
	}
	if susp, ok := doc["security_suspension"].(bson.M); ok {
		if active, _ := susp["active"].(bool); active {
			return false, nil
		}
	}
	if active, ok := doc["active"].(bool); ok && !active {
		return false, nil
	}
	if banned, _ := doc["banned"].(bool); banned {
		return false, nil
	}
	if role, _ := doc["role"].(string); role == "god" {
		return false, nil
	}
	return true, nil
}

func (s mongoDeveloperStore) CountApps(ctx context.Context, owner bson.ObjectID) (int64, error) {
	return s.db.Collection("developer_apps").CountDocuments(ctx, bson.M{"owner_id": owner})
}

// CountTokens counts the rows the page lists for the target (the app's, or the
// account's personal ones), so the cap never blocks an unrelated list. Count and
// insert are separate operations; the per-account rate limit bounds any overshoot.
func (s mongoDeveloperStore) CountTokens(ctx context.Context, owner, appID bson.ObjectID) (int64, error) {
	filter := bson.M{"user_id": owner, "category": "user"}
	if !appID.IsZero() {
		filter = bson.M{"user_id": owner, "app_id": appID}
	}
	return s.db.Collection("api_tokens").CountDocuments(ctx, filter)
}

func (s mongoDeveloperStore) CreateApp(ctx context.Context, doc bson.M) (bson.ObjectID, error) {
	res, err := s.db.Collection("developer_apps").InsertOne(ctx, doc)
	if err != nil {
		return bson.NilObjectID, err
	}
	id, _ := res.InsertedID.(bson.ObjectID)
	return id, nil
}

func (s mongoDeveloperStore) RotateApp(ctx context.Context, owner, id bson.ObjectID, clientID, clientSecret string) (bool, error) {
	res, err := s.db.Collection("developer_apps").UpdateOne(ctx, bson.M{"_id": id, "owner_id": owner},
		bson.M{"$set": bson.M{"client_id": clientID, "client_secret": clientSecret,
			"rotated_at": bson.NewDateTimeFromTime(time.Now().UTC())}})
	return err == nil && res.MatchedCount == 1, err
}

func (s mongoDeveloperStore) InsertToken(ctx context.Context, doc bson.M) error {
	_, err := s.db.Collection("api_tokens").InsertOne(ctx, doc)
	return err
}

func (s mongoDeveloperStore) RevokeToken(ctx context.Context, owner, id bson.ObjectID) (bool, error) {
	res, err := s.db.Collection("api_tokens").DeleteOne(ctx, bson.M{"_id": id, "user_id": owner})
	return err == nil && res.DeletedCount == 1, err
}

func (s mongoDeveloperStore) Audit(ctx context.Context, doc bson.M) error {
	_, err := s.db.Collection("api_usage").InsertOne(ctx, doc)
	return err
}
