# `/developer` and demo material download on the React host

Status: approved through the auth bridge (2026-11-12, see [auth-bridge.md](auth-bridge.md)). Step 1 is
implemented as Go read routes instead of a Flask scope: `GET /api/developer/overview` and
`GET /api/developer/apps/<id>` (`go-api/developer.go`), served only when `AUTH_BRIDGE_ENABLED=true`,
returning the signed-in account's own metadata with no secrets. Not routed by Apache yet. React screens
are implemented (`DeveloperScreen.tsx`, read-only; see below) and routing is prepared but not active. Written 12 November 2026. This follows the TODO item "Secondary tools".

## Verified facts

- `/developer` is the Flask blueprint `developer_bp.py`. Every route is behind
  `@login_required`. A user whose `api_tokens_enabled` flag is false gets
  `developer/locked.html` instead of the page. The lock page posts a justification
  to `POST /developer/request_access`, which emails the support address.
- GET pages: `/developer/` (apps and personal tokens), `/developer/apps`,
  `/developer/apps/<id>` (tokens, rate limits, allowed scopes), `/developer/docs`
  (a redirect to `/api-docs`). All of them read `developer_apps` and `api_tokens`
  filtered by the signed-in user's id.
- The writes are `POST /developer/apps`, `/apps/<id>/token`, `/apps/<id>/rotate`,
  `/apps/<id>/request_scopes` and `/request_access`. The templates call them with
  `fetch`; rotate and token creation return secrets once.
- Consumers: only the three templates and the settings page link. No other
  frontend code or API client uses these routes.
- `GET /download_material/<demo_id>` is not a page. It redirects to the event's
  `preview_image` or `img` CDN URL, falls back to a file under
  `static/demo_preview/`, and otherwise flashes an error and redirects home. Its
  only caller is the Flask route itself; nothing links to it.

## Why this is not migrated yet

The React host renders pages with public data or a bounded `/api/session` scope.
`/developer` pages are private and per user, so they need a new signed-in read
(a `/api/session?developer=1` scope, or a Go endpoint that authenticates the Flask
session). Both are session/authentication changes, which need your approval, and
the page shows token and app metadata, so the response must be `no-store` and
varied by cookie.

Demo material download stays in Flask: the local-file fallback and the flash message
are Flask-owned, so a Go copy would not be equivalent. It is a download, not a page,
and nothing needs to change for the React target.

## Proposed design if approved

1. Add a private read scope `GET /api/session?developer=1` returning, for the
   signed-in user only: the access flag, their apps (id, name, description, client
   id, allowed scopes, created time), token metadata (id, name, scopes, expiry,
   never the token or secret) and, for one app, the configured rate limits.
   Anonymous requests get a login redirect to `/users/auth/login?next=...`; a user
   without access gets the lock state.
2. React screens at `/developer`, `/developer/apps` and `/developer/apps/<id>`
   (Finnish catalog copy reusing the template msgids, no icons in headings). The
   POST handlers stay in Flask under the same URLs, with CSRF as today.
3. Apache routes only those GET paths to the React host, prepared but not active,
   following `docs/react-ssr-app.md`. Rollback is removing the rule.
4. Visual acceptance with the moso-visual-qa skill and a separate reviewer SHIP.

## Questions

1. May we add the private `/api/session?developer=1` scope (a session change)?
   Suggested: yes, read-only, `no-store`, no secrets, same pattern as
   `organization_id`.
2. Should the `/developer` writes later move to Go? Suggested: not now; they handle
   secrets and sit under the authentication approval.

## React screens (implemented 12 November 2026)

- Routes claimed by the React host: `/developer` (and `/developer/`) and `/developer/apps/<24 hex>`. `/developer/apps`
  (the create form), `/developer/docs` and every POST stay in Flask. The Apache lines are commented out in
  `deploy/apache/react-ssr-routing.conf`.
- The host renders only a shell (`private, no-store`, `noindex, nofollow`, no canonical URL, no analytics). The browser
  then reads `GET /api/developer/overview` or `/api/developer/apps/<id>` with its own cookie, through `useSession`
  (which also re-reads `/api/auth/me` when the bridge is on).
- States: anonymous (or Go 401) shows a sign-in link to `/users/auth/login?next=<this page>`; `{access:false}` shows the
  lock text and the request form, which posts the unchanged `reason` field to Flask `/developer/request_access`; an
  unknown or foreign app (404) shows "Sovellusta ei löytynyt."; any other failure or a malformed body shows a retry
  message, never an empty panel. Secrets are not in the response, so none can be shown.
- Copy is the Flask templates' Finnish msgids in `frontend/src/app/developer-route.ts`; no icons in headings.
- Left out on purpose: the create, rotate, revoke and scope-request controls and the rate-limit panel (no Go data for
  it yet). Until they exist in React, activating the routing would remove them, so activation is open in TODO.md.

## Write controls (13 November 2026)

Ported: see [developer-react-write-controls.md](developer-react-write-controls.md). The "left out on purpose" list above is superseded; the controls appear only when Go reports `writes: true`.
