# Auth bridge: who is signed in, for Go and React

Status: implemented behind two off-by-default flags (2026-11-12). Login, MFA,
password changes and the session cookie stay in Flask. Go and React gain a
read-only "who am I" answer and permission checks.

Maintainer approval (2026-11-12): "I approve the beginning of changing the
authentication to react and go, maybe just maybe lets keep login on flask, and
make go and react have some sorta auth engine that then uses the flask […] and
then choose the best and implement". This document is that research and choice.

## 1. Verified facts (from the code)

### Flask session

- **Mechanism.** Flask 3.1.1's default `SecureCookieSessionInterface`: the whole
  session is a client-side cookie named `session`. There is no Flask-Session, no
  server-side session store and no Redis session. (`requirements.txt` has none.)
- **Signing.** `itsdangerous` `URLSafeTimedSerializer`: salt `cookie-session`,
  HMAC-SHA1 key derivation (`hmac`), signed with `SECRET_KEY` from
  `config.yaml` (`config.py`, `SECRET_KEY`). The payload is compressed JSON and is
  **readable** by the holder, only tamper-proof. A Go implementation would need the
  same `SECRET_KEY`, the same serializer and the same Flask-Login rules.
- **Cookie flags.** `SESSION_COOKIE_HTTPONLY=True`, `SameSite=Lax`,
  `SESSION_COOKIE_SECURE` defaults to `False` in `config.py` (production value
  comes from its `config.yaml`; not read for this document).
- **Lifetime.** Anonymous sessions are browser-session cookies. Login sets
  `session.permanent = True` (`users/BPs/auth.py`), so the cookie lives
  `PERMANENT_SESSION_LIFETIME`, default 12 hours. There is no "remember me": every
  `login_user` call uses the default `remember=False`, so Flask-Login's
  `remember_token` cookie is never issued.
- **Who is signed in.** Flask-Login stores `_user_id` (and `_id`, `_fresh`).
  `load_user` in `app.py` reloads the user from MongoDB **on every request** and
  returns nobody when: the account is suspended, `session["auth_epoch"]` differs
  from the user's `auth_epoch` (this is how "log out everywhere" works), a god
  session is no longer valid, `mfa_credential_version` no longer matches the
  SHA-256 of the current `password_hash` (a password reset invalidates sessions),
  or the account is inactive. **A copied cookie is therefore not enough to read
  the same answer in another system; the answer depends on a live database read.**
  This is the strongest argument against validating the cookie outside Flask.
- **MFA step.** Password check → if MFA is on, a pending challenge is stored
  server-side in `mfa_login_challenges` (5 minute TTL, 5 attempts), referenced by
  a random handle in the session. Only after the TOTP/passkey step does
  `login_user` run. Go never sees the pending state.
- **Other session contents.** Flashes (`_flashes`), locale, per-form CSRF nonces
  (`translation_join_csrf_token`, contact tokens, governance, edit-link and others),
  the step-up `sudo` record, `auth_epoch`, `next_page`, WebAuthn challenges.
- **CSRF.** No global `CSRFProtect`. Each sensitive form carries its own
  session-bound nonce compared with `hmac.compare_digest`, plus `SameSite=Lax`.
- **Password hashes.** `werkzeug.security.generate_password_hash` /
  `check_password_hash` (Werkzeug 3.1.5, `users/models.py`), not bcrypt. New hashes
  use Werkzeug's default (scrypt); `check_password_hash` also accepts older
  `pbkdf2:` hashes. The mix of formats in the production database was **not**
  measured; any Go password check would have to reproduce Werkzeug's formats
  exactly. God accounts add a `god_security.secret_hash` and ordered extra steps.

### `/api/session`

`GET /api/session` (`basic_routes.py`, `public_session_summary`) is already the
read-only introspection endpoint. It returns the header state (authenticated,
role, display name, picture, `global_admin`, `has_admin_access`, unread count,
locale, fundraising/analytics flags, `submission.can_edit_demo`) plus `actor_id`
for signed-in users, with `Cache-Control: no-store` and `Vary: Cookie`. Scopes:

| Scope | Returns |
| --- | --- |
| `organization_id=<id>` (one) | signed-in: following, invited, `has_messages`, four organization permissions. With `AUTH_BRIDGE_SCOPES`, anonymous visitors get `{id, has_messages}` only |
| `translation_join=1` | signed-in only: join state, nonce, flashes (consumes them) |
| `contact_form=1` | anyone: one-time token, flashes (consumes them), limits; may set the cookie |

It never returns the cookie, email or private records. With `AUTH_BRIDGE_SCOPES` it also answers named permissions as booleans for the caller's own account (at most 10).

### Consumers today

- **React SSR host** (`frontend/src/app/session-server.ts`, `render.tsx`): reads
  `/api/session` over the Gunicorn unix socket with the visitor's cookie and passes
  a `SessionSummary` (`session.ts`) to the pages. There is no client-side
  `useSession`.
- **Go** (`go-api/submission_session.go`): `submissionActor` calls the same
  endpoint over the socket, uncached, one second deadline, and uses only the
  account id. It fails closed. Used by `POST /submit` and the city admin
  application endpoints.
- **Gap that blocks TODO items.** Go has no reusable principal or permission
  check, and `/api/session` cannot answer "may this account do X?" for arbitrary
  permissions, nor tell an anonymous visitor that a flash message is waiting.

## 2. Options

**(a) Go validates the Flask cookie / reads the session store.** There is no
store, so this means copying `SECRET_KEY` into Go and reimplementing
`itsdangerous` plus Flask-Login. The cookie only proves what was true at login:
Go would also need to reimplement `load_user` (suspension, `auth_epoch`, MFA
credential version, god sessions) with direct MongoDB reads, and keep that in
step with Flask forever. Two implementations of one security decision.

**(b) Go (and React SSR) ask a small Flask introspection endpoint, with a short
optional cache.** The endpoint already exists and is in production use. Flask
keeps every decision; Go gets a typed principal.

**(c) Flask mints a short-lived signed token for Go.** Needs a minting endpoint,
a shared secret or key pair, token delivery to the browser (a second credential
next to the cookie, readable by script unless carefully stored), expiry and
revocation design. Revocation (`auth_epoch`, suspension, password reset) only
takes effect when the token expires. This is the JWT/session-sharing path the
repository rules say not to take by default.

**(d) Full auth in Go.** Reimplement login, MFA (TOTP, passkeys, email steps, god
flow), password hashing in all existing formats, reset, forced changes, step-up,
rate limits and audit logging. Largest security surface, no rollback short of
reverting data-affecting changes, nothing delivered incrementally.

## 3. Scores

1 (poor) to 5 (best). "Blocked items" is how much of `/report`, account pages,
token pages / `accept_invite`, the organization flash message and `/developer`
the option unblocks soon.

| | Security | Rollback | Performance | Incremental | Blocked items | Total |
| --- | --- | --- | --- | --- | --- | --- |
| (a) validate cookie in Go | 2 (second copy of `load_user`, shared secret) | 3 | 5 | 3 | 3 | 16 |
| **(b) introspection** | **5** (one authority, instant revocation) | **5** (flag off) | 3 (one local socket hop; optional ≤5 s cache) | **5** | **4** | **22** |
| (c) signed token for Go | 3 (new credential, revocation lag) | 3 | 5 | 3 | 3 | 17 |
| (d) full auth in Go | 2 | 1 | 4 | 1 | 5 (eventually) | 13 |

Performance for (b): Gunicorn answers `/api/session` with one user lookup and a
notification read; the call is local over a unix socket. Anonymous requests have
no cookie, so Go makes no call at all. A cache is available but off by default
because it delays revocation.

## 4. Choice and what it unblocks

**Option (b).** It is the only option that keeps a single authority for
revocation, needs no new credential and is already proven in production by the
submission and city admin endpoints. Login/MFA/password pages can move to React
later as forms that post to the existing Flask handlers; none of that needs
(a), (c) or (d).

| Item | With the bridge |
| --- | --- |
| Organization flash message for anonymous visitors | Done here (below). |
| `/developer`, `/report` | A Go handler wraps itself in `RequireAuthenticated` or `RequirePermission`; `/report` still needs its one-time form token, which stays a Flask scope like `contact_form`. |
| Token pages (`/confirm/<token>` etc.) | Need no session; `accept_invite` uses the signed-in principal. |
| Account pages (login, settings, MFA) | Still post to Flask. React can show state from `useSession`; moving the flows is a separate approval. |

## 5. Implementation

Two independent flags, both off by default. With both off nothing changes.

**Flask (`AUTH_BRIDGE_SCOPES`, config.yaml, default false)**
`/api/session` adds, only when the flag is on:

- `auth_bridge: true`, so the React client knows the Go endpoint may be used;
- `permission=NAME` (repeatable, at most 10, `^[A-Z][A-Z0-9_]{1,63}$`): a
  `permissions` object of booleans for the caller's own account, scoped to
  `organization_id` when one is given. Anonymous callers get `false`.
- For an anonymous caller with `organization_id`: `organization: {id,
  has_messages}`. This is what lets the organization page see "Kiitos! Ehdotuksesi
  on tallennettu". No membership, invitation or permission data.

Reading these never consumes a flash message and changes nothing.

**Go (`AUTH_BRIDGE_ENABLED=true`, `go-api/auth_bridge.go`)**

- `sessionResolver.Resolve` calls Flask `/api/session` over the Gunicorn socket
  (`AUTH_BRIDGE_ORIGIN`, `AUTH_BRIDGE_SESSION_SOCKET`; they fall back to
  `PUBLIC_SUBMIT_ORIGIN` and `PUBLIC_SUBMIT_SESSION_SOCKET`). No cookie → anonymous,
  no call. Any error, non-200, malformed body, missing `authenticated` or invalid
  account id → error, never "anonymous".
- `RequireAuthenticated` and `RequirePermission(name, organizationFromRequest, next)`
  middleware put a `Principal` in the context and answer 401, 403 or 503. A
  permission that was not asked for is false.
- `GET /api/auth/me[?organization_id=…&permission=…]` is the browser-facing
  answer, in `/api/session` field names, without `actor_id`. No CORS header,
  `no-store`, `Vary: Cookie`, refuses any `Sec-Fetch-Site` other than `same-origin` or `none`.
- Optional per-cookie cache `AUTH_BRIDGE_CACHE_TTL_SECONDS` (0 to 5, default 0).
  Revocation can lag by that long when set.
- Flask cookies are never parsed, copied, stored or set by Go.

**React**

- `useSession(initial, { endpoint, scope })` (`frontend/src/app/useSession.ts`):
  starts from the server-rendered summary, and when `authBridge` is true re-reads
  `/api/auth/me` once after hydration. Only identity, role and organization state
  are replaced. Any failure or malformed body keeps the starting value.
- `normalizeSession` now keeps `organization` for anonymous visitors, reduced to
  the message flag.
- First consumer: `OrganizationScreen` shows pending flash messages to anonymous
  visitors too, and the private member panel is unchanged.

## 6. Activation and rollback

1. Flask: add `AUTH_BRIDGE_SCOPES: true` to `config.yaml`, restart Gunicorn
   (never during a backup dump: core 02:32 UTC, full Sunday 03:34 UTC).
   This alone fixes the anonymous organization message, because the React SSR
   host already requests the organization scope when a cookie is present.
2. Go: add `AUTH_BRIDGE_ENABLED=true` to the Go service environment and restart
   (same dump restriction). Add the Apache rule for `/api/auth/me` that is
   commented in `deploy/apache/react-ssr-routing.conf`.
3. **Rollback, one step each:** remove the setting and restart the service. With
   Flask's flag off, `/api/session` is byte-for-byte what it was; with Go's flag off
   `/api/auth/me` is a 404 and React falls back to its server-rendered state.
   No data, cookie or account is touched, so there is nothing to restore.
4. Before activation take a backup of `config.yaml` and the Go environment file.

## 7. Risks and open points

- `has_messages` is true for any pending flash in the visitor's session, not only
  one meant for the organization page, so the page may show and consume another
  page's message. This is existing behaviour for signed-in members, now shared by
  anonymous visitors. Scoping flashes by page is open.
- `RequirePermission` without an organization id means "in any organization or
  globally" (Flask's rule). Give it an id callback for organization routes; a
  malformed id is refused with 400 rather than widened.

- Each Go request that needs identity costs one Flask call. Keep it to handlers
  that need it; do not add the middleware to public cached routes.
- A Flask outage makes bridge-protected Go routes answer 503. Anonymous reads of
  public routes are unaffected.
- The production password-hash format mix is unmeasured. It matters only if a
  future step moves password checks out of Flask.
- Moving login, registration, MFA or reset into Go is not planned and needs a new
  approval. The bridge does not make it easier or harder.
