package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
)

type fakeWriteStore struct {
	fakeDeveloperStore
	ineligible bool
	apps, toks int64
	appDocs    []bson.M
	tokenDocs  []bson.M
	audits     []bson.M
	revokeOK   bool
	rotated    []string
}

func (f *fakeWriteStore) CanReceiveTokens(context.Context, bson.ObjectID) (bool, error) {
	return !f.ineligible, nil
}
func (f *fakeWriteStore) CountApps(context.Context, bson.ObjectID) (int64, error) { return f.apps, nil }
func (f *fakeWriteStore) CountTokens(context.Context, bson.ObjectID, bson.ObjectID) (int64, error) {
	return f.toks, nil
}
func (f *fakeWriteStore) CreateApp(_ context.Context, doc bson.M) (bson.ObjectID, error) {
	f.appDocs = append(f.appDocs, doc)
	return bson.NewObjectID(), nil
}
func (f *fakeWriteStore) RotateApp(_ context.Context, owner, id bson.ObjectID, cid, hash string) (bool, error) {
	f.rotated = append(f.rotated, cid+":"+hash)
	return owner == f.owner, nil
}
func (f *fakeWriteStore) InsertToken(_ context.Context, doc bson.M) error {
	f.tokenDocs = append(f.tokenDocs, doc)
	return nil
}
func (f *fakeWriteStore) RevokeToken(context.Context, bson.ObjectID, bson.ObjectID) (bool, error) {
	return f.revokeOK, nil
}
func (f *fakeWriteStore) Audit(_ context.Context, doc bson.M) error {
	f.audits = append(f.audits, doc)
	return nil
}

type writeRig struct {
	h      http.Handler
	store  *fakeWriteStore
	writes *developerWrites
}

func newWriteRig(t *testing.T, enabled bool) writeRig {
	t.Helper()
	owner, _ := bson.ObjectIDFromHex(testActor)
	store := &fakeWriteStore{fakeDeveloperStore: fakeDeveloperStore{enabled: enabled, owner: owner,
		apps: []developerApp{{ID: testOrg, Name: "Oma", AllowedScopes: []string{"read", "write"}}}}, revokeOK: true}
	config, _ := fakeFlask(t, flaskAnswer)
	resolver, _ := newSessionResolver(config)
	writes := newDeveloperWrites(store, "https://example.test")
	h := developerHandlerWith(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(299) }), store, resolver, writes)
	return writeRig{h, store, writes}
}

func (g writeRig) post(method, path, body string, headers ...string) *httptest.ResponseRecorder {
	r := httptest.NewRequest(method, path, strings.NewReader(body))
	r.Header.Set("Cookie", "session=member")
	r.Header.Set("Sec-Fetch-Site", "same-origin")
	r.Header.Set("Origin", "https://example.test")
	r.Header.Set("Content-Type", "application/json")
	r.Header.Set(developerCSRFHeader, g.writes.csrfToken(testActor))
	for i := 0; i+1 < len(headers); i += 2 {
		if headers[i+1] == "-" {
			r.Header.Del(headers[i])
		} else {
			r.Header.Set(headers[i], headers[i+1])
		}
	}
	w := httptest.NewRecorder()
	g.h.ServeHTTP(w, r)
	return w
}

func TestWritesOffByDefault(t *testing.T) {
	store := &fakeWriteStore{}
	config, _ := fakeFlask(t, flaskAnswer)
	resolver, _ := newSessionResolver(config)
	h := developerHandler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(299) }), store, resolver)
	for _, c := range [][2]string{{"POST", "/api/developer/apps"}, {"POST", "/api/developer/tokens"}, {"DELETE", "/api/developer/tokens/" + testOrg}, {"POST", "/api/developer/apps/" + testOrg + "/rotate"}} {
		r := httptest.NewRequest(c[0], c[1], strings.NewReader("{}"))
		r.Header.Set("Cookie", "session=member")
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		if w.Code == 200 || len(store.appDocs) > 0 {
			t.Fatalf("%v must not write while the flag is off: %d", c, w.Code)
		}
	}
	if r := httptest.NewRequest("POST", "/api/developer/apps/"+testOrg+"/rotate", nil); true {
		r.Header.Set("Cookie", "session=member")
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		if w.Code != 404 {
			t.Fatalf("write paths must be 404 while off, got %d", w.Code)
		}
	}
	if w := get(h, developerOverviewPath, "session=member"); strings.Contains(w.Body.String(), "csrf") {
		t.Fatal("no csrf token while writes are off")
	}
}

func TestReadsAdvertiseWritesAndCSRF(t *testing.T) {
	g := newWriteRig(t, true)
	w := get(g.h, developerOverviewPath, "session=member")
	if !strings.Contains(w.Body.String(), `"writes":true`) || !strings.Contains(w.Body.String(), `"csrf":"`) {
		t.Fatal(w.Body.String())
	}
}

func TestWriteGuards(t *testing.T) {
	g := newWriteRig(t, true)
	body := `{"name":"x"}`
	cases := []struct {
		name string
		want int
		h    []string
	}{
		{"cross site", 403, []string{"Sec-Fetch-Site", "cross-site"}},
		{"missing fetch metadata", 403, []string{"Sec-Fetch-Site", "-"}},
		{"foreign origin", 403, []string{"Origin", "https://evil.test"}},
		{"no csrf", 403, []string{developerCSRFHeader, "-"}},
		{"bad csrf", 403, []string{developerCSRFHeader, "1.2.3"}},
		{"form post", 415, []string{"Content-Type", "application/x-www-form-urlencoded"}},
	}
	for _, c := range cases {
		if w := g.post("POST", "/api/developer/apps", body, c.h...); w.Code != c.want {
			t.Errorf("%s: got %d", c.name, w.Code)
		}
	}
	if len(g.store.appDocs) != 0 {
		t.Fatal("rejected requests must not write")
	}
	// Anonymous and failed sessions.
	for _, cookie := range []string{"", "session=guest", "session=error"} {
		r := httptest.NewRequest("POST", "/api/developer/apps", strings.NewReader(body))
		if cookie != "" {
			r.Header.Set("Cookie", cookie)
		}
		w := httptest.NewRecorder()
		g.h.ServeHTTP(w, r)
		if w.Code != 401 && w.Code != 503 {
			t.Errorf("%q: got %d", cookie, w.Code)
		}
	}
	if len(g.store.appDocs) != 0 {
		t.Fatal("unauthenticated request wrote")
	}
}

func TestCSRFIsBoundToAccountAndExpires(t *testing.T) {
	g := newWriteRig(t, true)
	token := g.writes.csrfToken(testActor)
	if !g.writes.csrfValid(testActor, token) || g.writes.csrfValid("fedcba9876543210fedcba98", token) {
		t.Fatal("token must bind to the account")
	}
	g.writes.now = func() time.Time { return time.Now().Add(13 * time.Hour) }
	if g.writes.csrfValid(testActor, token) {
		t.Fatal("expired token accepted")
	}
	other := newDeveloperWrites(g.store, "x")
	if other.csrfValid(testActor, token) {
		t.Fatal("a token from another key accepted")
	}
}

func TestCreateAppShowsSecretOnceAndStoresHash(t *testing.T) {
	g := newWriteRig(t, true)
	w := g.post("POST", "/api/developer/apps", `{"name":" Sovellus ","description":"d"}`)
	if w.Code != 200 {
		t.Fatal(w.Code, w.Body.String())
	}
	body := w.Body.String()
	doc := g.store.appDocs[0]
	// Flask stores client_secret as given; the shape must not change.
	if stored := doc["client_secret"].(string); len(stored) != 32 || extractSecret(body) != stored {
		t.Fatal("client_secret must be stored as Flask stores it", stored)
	}
	if !strings.Contains(body, `"client_secret":"`) || strings.Contains(body, `"owner_id"`) {
		t.Fatal(body)
	}
	if doc["name"] != "Sovellus" || doc["owner_id"].(bson.ObjectID).Hex() != testActor {
		t.Fatal("document shape", doc)
	}
	if sc := doc["allowed_scopes"].(bson.A); len(sc) != 1 || sc[0] != "read" {
		t.Fatal("new apps start with read only")
	}
	if len(g.store.audits) != 1 || g.store.audits[0]["action"] != "developer app created" {
		t.Fatal("audit entry missing")
	}
	for _, bad := range []string{`{"name":""}`, `{"name":"  "}`, `{`, `{"name":"` + strings.Repeat("x", 101) + `"}`} {
		if w := g.post("POST", "/api/developer/apps", bad); w.Code != 400 {
			t.Errorf("%q: %d", bad, w.Code)
		}
	}
	g.store.apps = developerMaxApps
	if w := g.post("POST", "/api/developer/apps", `{"name":"x"}`); w.Code != 409 {
		t.Fatal("app cap", w.Code)
	}
}

func TestLockedAccountCannotWrite(t *testing.T) {
	g := newWriteRig(t, false)
	for _, p := range []string{"/api/developer/apps", "/api/developer/tokens", "/api/developer/apps/" + testOrg + "/token"} {
		if w := g.post("POST", p, `{"name":"x","scopes":["read"]}`); w.Code != 403 {
			t.Errorf("%s: %d", p, w.Code)
		}
	}
	if len(g.store.appDocs)+len(g.store.tokenDocs) != 0 {
		t.Fatal("wrote while locked")
	}
}

func TestAppTokenScopesFollowTheApp(t *testing.T) {
	g := newWriteRig(t, true)
	path := "/api/developer/apps/" + testOrg + "/token"
	w := g.post("POST", path, `{"type":"short","scopes":["read","write","submit_demonstrations","read"]}`)
	if w.Code != 200 {
		t.Fatal(w.Code, w.Body.String())
	}
	doc := g.store.tokenDocs[0]
	scopes := doc["scopes"].(bson.A)
	if len(scopes) != 2 || scopes[0] != "read" || scopes[1] != "write" {
		t.Fatalf("scopes outside the app's allowed set must be dropped: %v", scopes)
	}
	raw := w.Body.String()
	hash := doc["token"].(string)
	if len(hash) != 64 || strings.Contains(raw, hash) || doc["category"] != "app" || doc["app_id"].(bson.ObjectID).Hex() != testOrg || doc["rate_limit"] != "100/minute" {
		t.Fatal("document shape", doc)
	}
	if exp := doc["expires_at"].(bson.DateTime).Time().Sub(doc["created_at"].(bson.DateTime).Time()); exp < 47*time.Hour || exp > 49*time.Hour {
		t.Fatal("short tokens last 48h", exp)
	}
	if w := g.post("POST", path, `{"scopes":["submit_demonstrations"]}`); w.Code != 403 {
		t.Fatal("no allowed scope left must be 403", w.Code)
	}
	for _, c := range []string{`{"scopes":["admin"]}`, `{"scopes":["mcp.admin"]}`, `{"scopes":["nope"]}`, `{"type":"forever"}`} {
		if w := g.post("POST", path, c); w.Code < 400 {
			t.Errorf("%s accepted: %d", c, w.Code)
		}
	}
	// Another account's app is a 404 and issues nothing.
	g.store.owner = bson.NewObjectID()
	before := len(g.store.tokenDocs)
	if w := g.post("POST", path, `{"scopes":["read"]}`); w.Code != 404 || len(g.store.tokenDocs) != before {
		t.Fatal("foreign app", w.Code)
	}
}

func TestPersonalTokenRules(t *testing.T) {
	g := newWriteRig(t, true)
	if w := g.post("POST", "/api/developer/tokens", `{"type":"long","scopes":["read"]}`); w.Code != 200 {
		t.Fatal(w.Code, w.Body.String())
	}
	doc := g.store.tokenDocs[0]
	if doc["category"] != "user" || doc["app_id"] != nil || doc["type"] != "long" {
		t.Fatal(doc)
	}
	if w := g.post("POST", "/api/developer/tokens", `{"scopes":["admin"]}`); w.Code != 403 {
		t.Fatal("privileged scope needs Flask step-up", w.Code)
	}
	g.store.ineligible = true
	if w := g.post("POST", "/api/developer/tokens", `{"scopes":["read"]}`); w.Code != 400 {
		t.Fatal("suspended or god accounts get no token", w.Code)
	}
	g.store.ineligible = false
	g.store.toks = developerMaxTokens
	if w := g.post("POST", "/api/developer/tokens", `{"scopes":["read"]}`); w.Code != 409 {
		t.Fatal("token cap", w.Code)
	}
}

func TestRotateAndRevoke(t *testing.T) {
	g := newWriteRig(t, true)
	w := g.post("POST", "/api/developer/apps/"+testOrg+"/rotate", `{}`)
	if w.Code != 200 || len(g.store.rotated) != 1 || !strings.HasSuffix(g.store.rotated[0], ":"+extractSecret(w.Body.String())) {
		t.Fatal(w.Code, w.Body.String())
	}
	if len(g.store.audits) != 1 {
		t.Fatal("rotate must be audited")
	}
	if w := g.post("DELETE", developerTokensPrefix+testOrg, ""); w.Code != 200 {
		t.Fatal(w.Code)
	}
	g.store.revokeOK = false
	if w := g.post("DELETE", developerTokensPrefix+testOrg, ""); w.Code != 404 {
		t.Fatal("not the owner's token", w.Code)
	}
	if w := g.post("DELETE", developerTokensPrefix+"bad", ""); w.Code != 404 {
		t.Fatal(w.Code)
	}
}

func extractSecret(body string) string {
	_, rest, _ := strings.Cut(body, `"client_secret":"`)
	secret, _, _ := strings.Cut(rest, `"`)
	return secret
}

func TestWritesAreRateLimited(t *testing.T) {
	g := newWriteRig(t, true)
	var last int
	for i := 0; i < developerWritesPerMin+1; i++ {
		last = g.post("DELETE", developerTokensPrefix+testOrg, "").Code
	}
	if last != 429 {
		t.Fatal("expected 429, got", last)
	}
	g.writes.now = func() time.Time { return time.Now().Add(2 * time.Minute) }
	if w := g.post("DELETE", developerTokensPrefix+testOrg, ""); w.Code != 200 {
		t.Fatal("window must reset", w.Code)
	}
}

func TestOnlyExactAppActionPathsAreWriteRoutes(t *testing.T) {
	g := newWriteRig(t, true)
	for _, p := range []string{"/api/developer/apps/" + testOrg + "/x/rotate", "/api/developer/apps/" + testOrg + "/a/token",
		"/api/developer/apps/bad/rotate", "/api/developer/apps/" + testOrg + "/rotate/"} {
		if w := g.post("POST", p, `{"scopes":["read"]}`); w.Code == 200 {
			t.Errorf("%s must not be served", p)
		}
	}
	if len(g.store.tokenDocs)+len(g.store.rotated) != 0 {
		t.Fatal("a malformed path wrote")
	}
}
