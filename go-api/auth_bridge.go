package main

// Read-only "who am I" bridge between Go and Flask's session (docs/auth-bridge.md).
//
// Flask stays the only authority: it signs the session cookie, runs login, MFA
// and password checks, and decides permissions. Go never validates, mints or
// stores a Flask cookie. It forwards the visitor's Cookie header to Flask's
// read-only /api/session over the local Gunicorn socket and trusts the JSON
// answer. Any failure to get an answer fails closed. The bridge is off unless
// AUTH_BRIDGE_ENABLED=true, so a rollback is removing that variable.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"sort"
	"strconv"
	"sync"
	"time"
)

const (
	authBridgeMaxPermissions = 10
	authBridgeMaxCacheTTL    = 5 * time.Second
	authBridgeMaxCacheItems  = 1024
	authBridgeMaxCookieBytes = 8 << 10
)

var (
	authPermissionName = regexp.MustCompile(`^[A-Z][A-Z0-9_]{1,63}$`)
	authObjectID       = regexp.MustCompile(`^[a-f0-9]{24}$`)
	errAuthUnavailable = errors.New("session bridge unavailable")
)

type authBridgeConfig struct {
	Enabled bool
	Origin  string
	Socket  string
	// CacheTTL keeps an answer for a few seconds per cookie. Zero (the default)
	// asks Flask on every request, so a logout or revoked session applies at
	// once. A positive value delays revocation by at most that long.
	CacheTTL time.Duration
}

func authBridgeConfigFromEnv() (authBridgeConfig, error) {
	c := authBridgeConfig{Enabled: os.Getenv("AUTH_BRIDGE_ENABLED") == "true"}
	if !c.Enabled {
		return c, nil
	}
	c.Origin = env("AUTH_BRIDGE_ORIGIN", os.Getenv("PUBLIC_SUBMIT_ORIGIN"))
	c.Socket = env("AUTH_BRIDGE_SESSION_SOCKET", os.Getenv("PUBLIC_SUBMIT_SESSION_SOCKET"))
	parsed, err := url.Parse(c.Origin)
	localHTTP := err == nil && parsed.Scheme == "http" && net.ParseIP(parsed.Hostname()) != nil && net.ParseIP(parsed.Hostname()).IsLoopback()
	if err != nil || (parsed.Scheme != "https" && !localHTTP) || parsed.Host == "" || parsed.Path != "" || c.Socket == "" {
		return c, errors.New("invalid auth bridge configuration")
	}
	if raw := os.Getenv("AUTH_BRIDGE_CACHE_TTL_SECONDS"); raw != "" {
		seconds, err := strconv.Atoi(raw)
		if err != nil || seconds < 0 || time.Duration(seconds)*time.Second > authBridgeMaxCacheTTL {
			return c, errors.New("invalid auth bridge cache time")
		}
		c.CacheTTL = time.Duration(seconds) * time.Second
	}
	return c, nil
}

// authScope names what a caller wants to know beyond "who is this".
type authScope struct {
	OrganizationID string
	Permissions    []string
}

// normalized drops invalid and duplicate names and bounds the count. The same
// rules are enforced again by Flask.
func (s authScope) normalized() authScope {
	out := authScope{}
	if authObjectID.MatchString(s.OrganizationID) {
		out.OrganizationID = s.OrganizationID
	}
	seen := map[string]bool{}
	for _, name := range s.Permissions {
		if authPermissionName.MatchString(name) && !seen[name] {
			seen[name] = true
			out.Permissions = append(out.Permissions, name)
		}
	}
	sort.Strings(out.Permissions)
	if len(out.Permissions) > authBridgeMaxPermissions {
		out.Permissions = out.Permissions[:authBridgeMaxPermissions]
	}
	return out
}

func (s authScope) query() string {
	values := url.Values{}
	if s.OrganizationID != "" {
		values.Set("organization_id", s.OrganizationID)
	}
	for _, name := range s.Permissions {
		values.Add("permission", name)
	}
	return values.Encode()
}

// Principal is what Go may know about the caller. It carries no cookie, email
// or token, and ActorID never leaves the process.
type Principal struct {
	Authenticated  bool
	ActorID        string
	Role           string
	Name           string
	Picture        string
	GlobalAdmin    bool
	HasAdminAccess bool
	Unread         int
	Permissions    map[string]bool
	Organization   *PrincipalOrganization
}

type PrincipalOrganization struct {
	ID          string
	Following   bool
	Invited     bool
	HasMessages bool
	Permissions map[string]bool
}

// Has reports a permission Flask answered for. A permission that was not asked
// for, or a missing answer, is false: unknown never means allowed.
func (p Principal) Has(permission string) bool {
	return p.Authenticated && p.Permissions[permission]
}

// clone copies the maps so a handler cannot change a cached answer.
func (p Principal) clone() Principal {
	copyMap := func(m map[string]bool) map[string]bool {
		if m == nil {
			return nil
		}
		out := make(map[string]bool, len(m))
		for k, v := range m {
			out[k] = v
		}
		return out
	}
	p.Permissions = copyMap(p.Permissions)
	if p.Organization != nil {
		o := *p.Organization
		o.Permissions = copyMap(o.Permissions)
		p.Organization = &o
	}
	return p
}

var anonymousPrincipal = Principal{Role: "guest"}

type authCacheEntry struct {
	principal Principal
	expires   time.Time
}

type sessionResolver struct {
	client *http.Client
	host   string
	scheme string
	ttl    time.Duration
	mu     sync.Mutex
	cache  map[string]authCacheEntry
	now    func() time.Time
}

func newSessionResolver(config authBridgeConfig) (*sessionResolver, error) {
	origin, err := url.Parse(config.Origin)
	if err != nil {
		return nil, err
	}
	transport := &http.Transport{
		DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
			return (&net.Dialer{}).DialContext(ctx, "unix", config.Socket)
		},
		MaxIdleConns: 8, IdleConnTimeout: 30 * time.Second,
	}
	return &sessionResolver{
		client: &http.Client{Transport: transport, Timeout: time.Second,
			CheckRedirect: func(*http.Request, []*http.Request) error { return errors.New("session redirect") }},
		host: origin.Host, scheme: origin.Scheme, ttl: config.CacheTTL,
		cache: map[string]authCacheEntry{}, now: time.Now,
	}, nil
}

// Resolve returns the caller's principal. A request without cookies is
// anonymous and costs no Flask call. Errors mean "unknown": callers must deny.
func (r *sessionResolver) Resolve(ctx context.Context, request *http.Request, scope authScope) (Principal, error) {
	cookie := request.Header.Get("Cookie")
	scope = scope.normalized()
	if cookie == "" {
		return anonymousFor(scope), nil
	}
	if len(cookie) > authBridgeMaxCookieBytes {
		return Principal{}, errAuthUnavailable
	}
	key := ""
	if r.ttl > 0 {
		sum := sha256.Sum256([]byte(cookie + "\x00" + scope.query()))
		key = hex.EncodeToString(sum[:])
		r.mu.Lock()
		entry, ok := r.cache[key]
		r.mu.Unlock()
		if ok && r.now().Before(entry.expires) {
			return entry.principal.clone(), nil
		}
	}
	principal, err := r.fetch(ctx, request, cookie, scope)
	if err != nil {
		return Principal{}, err
	}
	if key != "" {
		r.mu.Lock()
		if len(r.cache) >= authBridgeMaxCacheItems {
			r.cache = map[string]authCacheEntry{}
		}
		r.cache[key] = authCacheEntry{principal.clone(), r.now().Add(r.ttl)}
		r.mu.Unlock()
	}
	return principal, nil
}

func anonymousFor(scope authScope) Principal {
	p := anonymousPrincipal
	if scope.OrganizationID != "" {
		p.Organization = &PrincipalOrganization{ID: scope.OrganizationID, Permissions: map[string]bool{}}
	}
	return p
}

func (r *sessionResolver) fetch(ctx context.Context, request *http.Request, cookie string, scope authScope) (Principal, error) {
	target := "http://" + r.host + "/api/session"
	if query := scope.query(); query != "" {
		target += "?" + query
	}
	call, err := http.NewRequestWithContext(ctx, http.MethodGet, target, nil)
	if err != nil {
		return Principal{}, errAuthUnavailable
	}
	// Gunicorn speaks plain HTTP over its local socket, even for HTTPS visitors.
	call.Header.Set("Cookie", cookie)
	call.Header.Set("Accept", "application/json")
	call.Header.Set("X-Forwarded-Proto", r.scheme)
	// Flask-Login's basic session protection fingerprints the user agent.
	if agent := request.Header.Get("User-Agent"); agent != "" && len(agent) <= 512 {
		call.Header.Set("User-Agent", agent)
	}
	if address := submissionClientAddress(request); net.ParseIP(address) != nil {
		call.Header.Set("X-Forwarded-For", address)
	}
	response, err := r.client.Do(call)
	if err != nil {
		return Principal{}, errAuthUnavailable
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return Principal{}, errAuthUnavailable
	}
	var raw struct {
		Authenticated  *bool           `json:"authenticated"`
		ActorID        string          `json:"actor_id"`
		Role           string          `json:"role"`
		Name           *string         `json:"name"`
		Picture        *string         `json:"picture"`
		GlobalAdmin    bool            `json:"global_admin"`
		HasAdminAccess bool            `json:"has_admin_access"`
		Unread         int             `json:"unread"`
		Permissions    map[string]bool `json:"permissions"`
		Organization   *struct {
			ID          string          `json:"id"`
			Following   bool            `json:"following"`
			Invited     bool            `json:"invited"`
			HasMessages bool            `json:"has_messages"`
			Permissions map[string]bool `json:"permissions"`
		} `json:"organization"`
	}
	if err := json.NewDecoder(io.LimitReader(response.Body, 64<<10)).Decode(&raw); err != nil || raw.Authenticated == nil {
		return Principal{}, errAuthUnavailable
	}
	p := anonymousFor(scope)
	if raw.Organization != nil && raw.Organization.ID == scope.OrganizationID {
		p.Organization = &PrincipalOrganization{ID: raw.Organization.ID, HasMessages: raw.Organization.HasMessages,
			Permissions: map[string]bool{}}
	}
	if !*raw.Authenticated {
		return p, nil
	}
	if !authObjectID.MatchString(raw.ActorID) {
		return Principal{}, errAuthUnavailable
	}
	p.Authenticated, p.ActorID = true, raw.ActorID
	p.Role = authBoundedText(raw.Role, 40, "user")
	if raw.Name != nil {
		p.Name = authBoundedText(*raw.Name, 200, "")
	}
	if raw.Picture != nil {
		p.Picture = authBoundedText(*raw.Picture, 2048, "")
	}
	p.GlobalAdmin, p.HasAdminAccess = raw.GlobalAdmin, raw.HasAdminAccess
	if raw.Unread > 0 {
		p.Unread = min(raw.Unread, 999)
	}
	p.Permissions = map[string]bool{}
	for _, name := range scope.Permissions {
		p.Permissions[name] = raw.Permissions[name]
	}
	if p.Organization != nil && raw.Organization != nil && raw.Organization.ID == p.Organization.ID {
		p.Organization.Following, p.Organization.Invited = raw.Organization.Following, raw.Organization.Invited
		for name, allowed := range raw.Organization.Permissions {
			if authPermissionName.MatchString(name) {
				p.Organization.Permissions[name] = allowed
			}
		}
	}
	return p, nil
}

func authBoundedText(value string, limit int, fallback string) string {
	if value == "" {
		return fallback
	}
	if len(value) > limit {
		value = value[:limit]
		for len(value) > 0 && value[len(value)-1]&0xC0 == 0x80 {
			value = value[:len(value)-1]
		}
	}
	return value
}

type principalKey struct{}

// PrincipalFromContext returns the principal a Require* wrapper resolved.
func PrincipalFromContext(ctx context.Context) (Principal, bool) {
	p, ok := ctx.Value(principalKey{}).(Principal)
	return p, ok
}

func authDenied(w http.ResponseWriter, status int, message string) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Vary", "Cookie")
	writeError(w, status, message)
}

// resolveFor resolves the principal or answers 503. It never runs the wrapped
// handler on an error: an unreadable session is not an anonymous one.
func (r *sessionResolver) resolveFor(w http.ResponseWriter, request *http.Request, scope authScope) (*http.Request, bool) {
	ctx, cancel := context.WithTimeout(request.Context(), 1500*time.Millisecond)
	defer cancel()
	p, err := r.Resolve(ctx, request, scope)
	if err != nil {
		log.Print("Auth bridge could not read the session")
		authDenied(w, http.StatusServiceUnavailable, "session unavailable")
		return nil, false
	}
	return request.WithContext(context.WithValue(request.Context(), principalKey{}, p)), true
}

// RequireAuthenticated runs next only for a signed-in account.
func (r *sessionResolver) RequireAuthenticated(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, request *http.Request) {
		withPrincipal, ok := r.resolveFor(w, request, authScope{})
		if !ok {
			return
		}
		if p, _ := PrincipalFromContext(withPrincipal.Context()); !p.Authenticated {
			authDenied(w, http.StatusUnauthorized, "authentication required")
			return
		}
		next.ServeHTTP(w, withPrincipal)
	})
}

// RequirePermission runs next only when Flask says the signed-in account has
// the permission. With organizationID the check is for that organization; a
// non-empty id that is not 24 lowercase hex characters is refused (400), never
// widened. Without an id, Flask answers "in any organization or globally".
func (r *sessionResolver) RequirePermission(permission string, organizationID func(*http.Request) string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, request *http.Request) {
		scope := authScope{Permissions: []string{permission}}
		if organizationID != nil {
			scope.OrganizationID = organizationID(request)
			if scope.OrganizationID != "" && !authObjectID.MatchString(scope.OrganizationID) {
				authDenied(w, http.StatusBadRequest, "invalid organization")
				return
			}
		}
		withPrincipal, ok := r.resolveFor(w, request, scope)
		if !ok {
			return
		}
		p, _ := PrincipalFromContext(withPrincipal.Context())
		if !p.Authenticated {
			authDenied(w, http.StatusUnauthorized, "authentication required")
			return
		}
		if !p.Has(permission) {
			authDenied(w, http.StatusForbidden, "forbidden")
			return
		}
		next.ServeHTTP(w, withPrincipal)
	})
}

// authMePayload is the browser-facing answer: the header fields plus the
// scopes asked for. It uses /api/session's field names so the React
// normalizer reads both. The actor ID and cookies are not included.
func authMePayload(p Principal) map[string]any {
	out := map[string]any{
		"authenticated": p.Authenticated, "role": p.Role, "name": nil, "picture": nil,
		"global_admin": p.GlobalAdmin, "has_admin_access": p.HasAdminAccess, "unread": p.Unread,
	}
	if p.Name != "" {
		out["name"] = p.Name
	}
	if p.Picture != "" {
		out["picture"] = p.Picture
	}
	if len(p.Permissions) > 0 {
		out["permissions"] = p.Permissions
	}
	if o := p.Organization; o != nil {
		out["organization"] = map[string]any{"id": o.ID, "following": o.Following, "invited": o.Invited,
			"has_messages": o.HasMessages, "permissions": o.Permissions}
	}
	return out
}

// authBridgeHandler serves GET /api/auth/me and passes everything else to next.
// It adds no CORS header: only same-origin script can read the answer.
func authBridgeHandler(next http.Handler, config authBridgeConfig) http.Handler {
	if !config.Enabled {
		return next
	}
	resolver, err := newSessionResolver(config)
	if err != nil {
		log.Print("Auth bridge disabled: invalid configuration")
		return next
	}
	return authBridgeHandlerWith(next, resolver)
}

func authBridgeHandlerWith(next http.Handler, resolver *sessionResolver) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/auth/me" {
			next.ServeHTTP(w, r)
			return
		}
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("Vary", "Cookie")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			writeError(w, http.StatusMethodNotAllowed, "method not allowed")
			return
		}
		if site := r.Header.Get("Sec-Fetch-Site"); site != "" && site != "same-origin" && site != "none" {
			writeError(w, http.StatusForbidden, "forbidden")
			return
		}
		query := r.URL.Query()
		scope := authScope{Permissions: query["permission"]}
		if orgs := query["organization_id"]; len(orgs) > 1 || (len(orgs) == 1 && !authObjectID.MatchString(orgs[0])) {
			writeError(w, http.StatusBadRequest, "invalid organization scope")
			return
		} else if len(orgs) == 1 {
			scope.OrganizationID = orgs[0]
		}
		for _, name := range scope.Permissions {
			if !authPermissionName.MatchString(name) {
				writeError(w, http.StatusBadRequest, "invalid permission name")
				return
			}
		}
		withPrincipal, ok := resolver.resolveFor(w, r, scope)
		if !ok {
			return
		}
		p, _ := PrincipalFromContext(withPrincipal.Context())
		writeJSON(w, http.StatusOK, authMePayload(p))
	})
}
