package main

import (
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

const testActor = "0123456789abcdef01234567"
const testOrg = "abcdefabcdefabcdefabcdef"

// fakeFlask answers /api/session on a unix socket the way Flask does, based on
// the Cookie header. It records every call.
func fakeFlask(t *testing.T, handler http.HandlerFunc) (authBridgeConfig, *int32) {
	t.Helper()
	dir, err := os.MkdirTemp("", "ab")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(dir) })
	socket := filepath.Join(dir, "s.sock")
	listener, err := net.Listen("unix", socket)
	if err != nil {
		t.Skip("unix sockets unavailable: ", err)
	}
	var calls int32
	server := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&calls, 1)
		handler(w, r)
	})}
	go server.Serve(listener)
	t.Cleanup(func() { server.Close() })
	return authBridgeConfig{Enabled: true, Origin: "https://example.test", Socket: socket}, &calls
}

func flaskAnswer(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	switch r.Header.Get("Cookie") {
	case "session=member":
		perms := "{}"
		if strings.Contains(r.URL.RawQuery, "permission=EDIT_DEMO") {
			perms = `{"EDIT_DEMO": true, "OTHER_PERM": true}`
		}
		org := ""
		if r.URL.Query().Get("organization_id") == testOrg {
			org = `,"organization":{"id":"` + testOrg + `","following":true,"invited":false,"has_messages":true,"permissions":{"EDIT_ORGANIZATION":true}}`
		}
		w.Write([]byte(`{"authenticated":true,"actor_id":"` + testActor + `","role":"user","name":"Test","picture":null,"global_admin":false,"has_admin_access":false,"unread":3,"permissions":` + perms + org + `}`))
	case "session=guest":
		w.Write([]byte(`{"authenticated":false,"organization":{"id":"` + testOrg + `","has_messages":true}}`))
	case "session=broken":
		w.Write([]byte(`not json`))
	case "session=error":
		w.WriteHeader(500)
	case "session=nobool":
		w.Write([]byte(`{"role":"admin"}`))
	case "session=badactor":
		w.Write([]byte(`{"authenticated":true,"actor_id":"nope"}`))
	default:
		w.Write([]byte(`{"authenticated":false}`))
	}
}

func bridge(t *testing.T, ttl time.Duration) (http.Handler, *int32) {
	config, calls := fakeFlask(t, flaskAnswer)
	config.CacheTTL = ttl
	resolver, err := newSessionResolver(config)
	if err != nil {
		t.Fatal(err)
	}
	next := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(299) })
	return authBridgeHandlerWith(next, resolver), calls
}

func get(h http.Handler, target, cookie string, headers ...string) *httptest.ResponseRecorder {
	r := httptest.NewRequest("GET", target, nil)
	if cookie != "" {
		r.Header.Set("Cookie", cookie)
	}
	for i := 0; i+1 < len(headers); i += 2 {
		r.Header.Set(headers[i], headers[i+1])
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	return w
}

func TestDisabledBridgeLeavesTheRouteToTheNextHandler(t *testing.T) {
	next := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(404) })
	h := authBridgeHandler(next, authBridgeConfig{}, nil)
	if w := get(h, "/api/auth/me", "session=member"); w.Code != 404 {
		t.Fatalf("flag off must not serve /api/auth/me, got %d", w.Code)
	}
}

func TestConfigRequiresOriginAndSocketWhenEnabled(t *testing.T) {
	t.Setenv("AUTH_BRIDGE_ENABLED", "true")
	t.Setenv("PUBLIC_SUBMIT_ORIGIN", "")
	if _, err := authBridgeConfigFromEnv(); err == nil {
		t.Fatal("expected an error without origin and socket")
	}
	t.Setenv("AUTH_BRIDGE_ORIGIN", "https://example.test")
	t.Setenv("AUTH_BRIDGE_SESSION_SOCKET", "/run/x.sock")
	c, err := authBridgeConfigFromEnv()
	if err != nil || !c.Enabled || c.CacheTTL != 0 {
		t.Fatalf("unexpected %v %v", c, err)
	}
	t.Setenv("AUTH_BRIDGE_CACHE_TTL_SECONDS", "6")
	if _, err := authBridgeConfigFromEnv(); err == nil {
		t.Fatal("cache time above the limit must be rejected")
	}
	t.Setenv("AUTH_BRIDGE_ENABLED", "")
	if c, err := authBridgeConfigFromEnv(); err != nil || c.Enabled {
		t.Fatal("default must be disabled")
	}
}

func TestAnonymousWithoutCookieCostsNoFlaskCall(t *testing.T) {
	h, calls := bridge(t, 0)
	w := get(h, "/api/auth/me?organization_id="+testOrg, "")
	if w.Code != 200 || *calls != 0 {
		t.Fatalf("code %d calls %d", w.Code, *calls)
	}
	body := w.Body.String()
	if !strings.Contains(body, `"authenticated":false`) || !strings.Contains(body, `"has_messages":false`) {
		t.Fatal(body)
	}
}

func TestSignedInAnswerIsMinimalAndUncacheable(t *testing.T) {
	h, _ := bridge(t, 0)
	w := get(h, "/api/auth/me?organization_id="+testOrg+"&permission=EDIT_DEMO", "session=member")
	body := w.Body.String()
	if w.Code != 200 || !strings.Contains(body, `"authenticated":true`) || !strings.Contains(body, `"EDIT_DEMO":true`) {
		t.Fatal(w.Code, body)
	}
	for _, leak := range []string{testActor, "actor_id", "session=member", "OTHER_PERM"} {
		if strings.Contains(body, leak) {
			t.Fatalf("answer leaks %q: %s", leak, body)
		}
	}
	if w.Header().Get("Cache-Control") != "no-store" || !strings.Contains(w.Header().Get("Vary"), "Cookie") {
		t.Fatal("headers", w.Header())
	}
	if w.Header().Get("Access-Control-Allow-Origin") != "" || w.Header().Get("Set-Cookie") != "" {
		t.Fatal("must add neither CORS nor cookies")
	}
}

func TestAnonymousCookieGetsOnlyTheFlashFlag(t *testing.T) {
	h, _ := bridge(t, 0)
	body := get(h, "/api/auth/me?organization_id="+testOrg, "session=guest").Body.String()
	if !strings.Contains(body, `"has_messages":true`) || strings.Contains(body, `"role":"admin"`) || !strings.Contains(body, `"authenticated":false`) {
		t.Fatal(body)
	}
}

func TestFailuresCloseInsteadOfTurningAnonymous(t *testing.T) {
	h, _ := bridge(t, 0)
	for _, cookie := range []string{"session=broken", "session=error", "session=nobool", "session=badactor"} {
		w := get(h, "/api/auth/me", cookie)
		if w.Code != 503 {
			t.Fatalf("%s: got %d %s", cookie, w.Code, w.Body.String())
		}
	}
}

func TestUnreachableFlaskFailsClosed(t *testing.T) {
	resolver, _ := newSessionResolver(authBridgeConfig{Enabled: true, Origin: "https://example.test", Socket: "/nonexistent/x.sock"})
	h := authBridgeHandlerWith(http.NotFoundHandler(), resolver)
	if w := get(h, "/api/auth/me", "session=member"); w.Code != 503 {
		t.Fatal(w.Code)
	}
	// Without cookies there is nothing to ask: anonymous still works.
	if w := get(h, "/api/auth/me", ""); w.Code != 200 {
		t.Fatal(w.Code)
	}
}

func TestRequestValidation(t *testing.T) {
	h, _ := bridge(t, 0)
	cases := map[string]int{
		"/api/auth/me?organization_id=bad":                                        400,
		"/api/auth/me?organization_id=" + testOrg + "&organization_id=" + testOrg: 400,
		"/api/auth/me?permission=lowercase":                                       400,
		"/api/auth/me?permission=A%0d%0aB":                                        400,
	}
	for target, want := range cases {
		if w := get(h, target, "session=member"); w.Code != want {
			t.Errorf("%s: got %d want %d", target, w.Code, want)
		}
	}
	post := httptest.NewRequest("POST", "/api/auth/me", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, post)
	if w.Code != 405 {
		t.Fatal(w.Code)
	}
	if w := get(h, "/api/auth/me", "session=member", "Sec-Fetch-Site", "cross-site"); w.Code != 403 {
		t.Fatalf("cross-site read must be refused, got %d", w.Code)
	}
	if w := get(h, "/api/auth/me", "session=member", "Sec-Fetch-Site", "same-origin"); w.Code != 200 {
		t.Fatal(w.Code)
	}
	if w := get(h, "/other", ""); w.Code != 299 {
		t.Fatal("other paths pass through")
	}
}

func TestScopeNormalizationBoundsNames(t *testing.T) {
	names := []string{"EDIT_DEMO", "EDIT_DEMO", "bad", "A B"}
	for i := 0; i < 20; i++ {
		names = append(names, "PERM_"+strings.Repeat("X", i+1))
	}
	s := authScope{OrganizationID: "zz", Permissions: names}.normalized()
	if s.OrganizationID != "" || len(s.Permissions) != authBridgeMaxPermissions {
		t.Fatalf("%+v", s)
	}
}

func TestCacheIsOffByDefaultAndExpires(t *testing.T) {
	h, calls := bridge(t, 0)
	get(h, "/api/auth/me", "session=member")
	get(h, "/api/auth/me", "session=member")
	if *calls != 2 {
		t.Fatalf("no cache expected, calls %d", *calls)
	}
	h, calls = bridge(t, 2*time.Second)
	get(h, "/api/auth/me", "session=member")
	get(h, "/api/auth/me", "session=member")
	if *calls != 1 {
		t.Fatalf("cache expected, calls %d", *calls)
	}
	get(h, "/api/auth/me", "session=other-user")
	if *calls != 2 {
		t.Fatal("another cookie must not share an answer")
	}
	get(h, "/api/auth/me?permission=EDIT_DEMO", "session=member")
	if *calls != 3 {
		t.Fatal("another scope must not share an answer")
	}
}

func TestRequireWrappersDenyByDefault(t *testing.T) {
	config, _ := fakeFlask(t, flaskAnswer)
	resolver, _ := newSessionResolver(config)
	ok := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p, found := PrincipalFromContext(r.Context())
		if !found || !p.Authenticated {
			t.Error("principal missing in context")
		}
		w.WriteHeader(204)
	})
	auth := resolver.RequireAuthenticated(ok)
	perm := resolver.RequirePermission("EDIT_DEMO", nil, ok)
	orgPerm := resolver.RequirePermission("EDIT_ORGANIZATION", func(*http.Request) string { return testOrg }, ok)
	for _, tc := range []struct {
		h      http.Handler
		cookie string
		want   int
	}{
		{auth, "", 401}, {auth, "session=guest", 401}, {auth, "session=member", 204}, {auth, "session=error", 503},
		{perm, "", 401}, {perm, "session=member", 204}, {perm, "session=guest", 401}, {perm, "session=broken", 503},
		{orgPerm, "session=member", 403},
	} {
		if w := get(tc.h, "/x", tc.cookie); w.Code != tc.want {
			t.Errorf("%s: got %d want %d", tc.cookie, w.Code, tc.want)
		}
	}
}

func TestRequirePermissionRefusesMalformedOrganizationInsteadOfWidening(t *testing.T) {
	config, _ := fakeFlask(t, flaskAnswer)
	resolver, _ := newSessionResolver(config)
	reached := false
	ok := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { reached = true })
	h := resolver.RequirePermission("EDIT_DEMO", func(*http.Request) string { return strings.ToUpper(testOrg) }, ok)
	if w := get(h, "/x", "session=member"); w.Code != 400 || reached {
		t.Fatalf("got %d reached=%v", w.Code, reached)
	}
}

func TestCachedPrincipalCannotBeChangedByCallers(t *testing.T) {
	config, _ := fakeFlask(t, flaskAnswer)
	config.CacheTTL = time.Second
	resolver, _ := newSessionResolver(config)
	r := httptest.NewRequest("GET", "/", nil)
	r.Header.Set("Cookie", "session=member")
	scope := authScope{Permissions: []string{"EDIT_DEMO"}}
	first, _ := resolver.Resolve(r.Context(), r, scope)
	first.Permissions["EDIT_DEMO"] = false
	second, _ := resolver.Resolve(r.Context(), r, scope)
	if !second.Has("EDIT_DEMO") {
		t.Fatal("cached answer was changed through a returned map")
	}
}
