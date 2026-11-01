# Standalone React public app (metadata-only server rendering)

Owner direction (1 November 2026): the public UI becomes React-only, migrated
pages stop using Jinja bodies, and the server cost of that stays low. This slice
starts the standalone host with the front page. The existing Flask pages remain
in place and unchanged for every route that has not moved yet.

## Rendering split

| Work | Where |
| --- | --- |
| `<title>`, description, robots, canonical/OG/Twitter tags, favicons, fonts, stylesheet links, theme bootstrap script | Server (`frontend/src/app/render.tsx`) |
| App root, bootstrap JSON (config, session summary, current path) | Server |
| Header, page components, event cards, footer, in-app navigation | Browser (`frontend/src/app/client.tsx`) |
| Event data | Browser requests the public Go `/api/home?lang=...` contract |

The server renders no React tree and queries no event collection. A page
response is a small amount of string composition plus one bounded read of the
Flask session summary. This keeps server CPU per page low while the browser
renders once. The home metadata is static, so it needs no event lookup. Routes
whose metadata depends on an event (detail pages) must add that single projected
read to the head path before they can move here.

## Files

- `frontend/src/app/` — configuration (existing public URL paths), copy catalog
  (fi/en/sv), routes, session contract, header props, footer, app shell, server
  render and browser entry.
- `frontend/vite.app.config.ts` and `frontend/vite.app.ssr.config.ts` — separate
  client and server bundles. Output goes to `frontend/dist/` (not committed).
- `frontend/server.mjs` — HTTP server: metadata pages, `/app-assets/*`, `/health`.
- `deploy/apache/react-ssr-routing.conf` — web server routing rules.
- `mielenosoitukset_fi/basic_routes.py` — `GET /api/session`.

## Session summary contract

`GET /api/session` returns the same header state the templates receive:

```json
{
  "authenticated": true, "locale": "fi",
  "locales": [{"code": "fi", "name": "Suomi"}],
  "role": "user", "name": "Display name", "picture": "https://...",
  "global_admin": false, "has_admin_access": false, "unread": 2, "fundraising": false
}
```

`locales` is the configured `BABEL_PUBLIC_LOCALES` list with its display names.
It is not hardcoded in the app: while only Finnish translations are complete, the
configuration exposes only Finnish and the header shows no language switcher,
exactly as the templates do today. Enabling another public locale adds it to the
header without a frontend change.

It returns no cookie value, token, email, permission list or private record, is
`Cache-Control: no-store` with `Vary: Cookie`, and grants no authority. Flask
still decides every permission and every write. A missing or slow endpoint
degrades to the anonymous header; it never blocks the page.

The summary also exposes public `site_analytics_enabled` and `matomo_enabled`
booleans. A missing summary defaults both to disabled; the host does not guess
whether tracking was enabled in production configuration.

## Analytics across the host boundary

Flask records successful legacy HTML responses in its request hook. A migrated
React page does not execute that hook, so after the React tree commits the app
sends one optional `POST /api/analytics/pageview` signal. It sends only the
original document referrer; the same-origin `Referer` header determines the
displayed page. The receiver currently allows only `/`, rejects bots,
cross-origin signals, prefetches, disabled tracking and DNT, bounds its JSON
body to 1 KiB, and uses the existing aggregate page/campaign/visitor writes.
The trusted request peer supplies the visitor-hash input; the browser cannot
provide an IP, identifier or page path. No raw location/referrer is stored.
Legacy pages must not emit this signal because their HTML hook already counts
them. Newly migrated routes must be added explicitly to the receiver allowlist.

The host loads the pinned existing Web Vitals observer and aggregate-beacon
script when first-party analytics is enabled. Matomo loads asynchronously after
the app commits when enabled and DNT is absent. Prerendered documents wait for
activation before page/Matomo hooks run. Analytics never blocks rendering and
does not retry page signals, avoiding duplicate increments on ambiguous errors.
The counts retain their existing aggregate meanings, but migrated pages need
working JavaScript and beacon delivery: blocked scripts, DNT and failed signals
can reduce their coverage compared with legacy server-side HTML counts.

## Routing

The web server sends only migrated page GET/HEAD requests to the app host:

| Request | Handler |
| --- | --- |
| `GET|HEAD /` | React app host |
| `POST /submit`, form posts, login/logout and other mutations | Flask (unchanged) |
| `GET /admin*`, `/users*`, `/api*`, `/static*`, feeds, sitemap, robots | Flask (unchanged) |
| `GET` of any page not yet migrated | Flask (unchanged) |

`/app-assets/*` always comes from the app host. Every other route must keep
working when the include is removed.

## Build and run

Use Node 22.12+ (the repository's existing requirement):

```sh
npm ci
npm run app:build          # typecheck, client bundle, server bundle
APP_ORIGIN=https://mielenosoitukset.fi \
FLASK_API_ORIGIN=http://127.0.0.1:8000 \
PUBLIC_API_BASE=https://api.mielenosoitukset.fi/api \
APP_PORT=8090 npm run app:start
```

For local verification only, `STATIC_DIR=mielenosoitukset_fi/static` lets the app
host serve `/static/*`, which production serves directly from the web server.
`/health` answers `{"status":"ok"}`.

## Verification performed

- `npx tsc --noEmit` and `npm run app:build` pass.
- `GET /` returns the expected Finnish title/description, RSS alternate, OG and
  Twitter tags, stylesheet links, an empty app root and bootstrap JSON;
  `Cache-Control: no-store`, `Vary: Cookie`, `X-Content-Type-Options: nosniff`.
- In a real browser the app renders the shared header, the front-page content and
  six live cards from `https://api.mielenosoitukset.fi/api/home?lang=fi`, plus the
  footer. No console errors. At 390px and 1440px in both themes the layout is
  visually identical to the current production page (same header, hero spacing,
typography and card start).
- Local `http://127.0.0.1` captures show broken event images because the CDN is
  cross-site from a loopback origin; the same URLs load from the production
  origin (`https://mielenosoitukset.fi`), where they are same-site. This is a
  capture-environment limitation, not a page change.
- Unknown paths return 404 from the app host, so nothing is silently claimed.
- `/app-assets` path traversal attempts return 404.

## Open items before switching production

1. A Node 22 runtime and systemd unit for the app host (production currently runs
   Python/Gunicorn only). Build output must be shipped with the release.
2. Detail, listing, organization, Pride and submit routes still have Jinja
   shells. Each needs its metadata source and (where required) data contract
   before its GET rule is added.
3. Page data for migrated routes comes from the public Go API. Routes still
   served by Flask keep using the existing authenticated Flask APIs.
4. Visual acceptance for the new host is **BLOCKED**: captures exist for 390px
   and 1440px in both themes plus the production reference, but no independent
   image-capable reviewer has issued a verdict. The implementer's comparison is
   evidence, not approval.
5. The local verification host has no Flask process, so links to routes still
   owned by Flask (for example an event card) return 404 locally. Production
   routes those to Flask; verify them on the staging vhost before switching.
6. The Apache include must be placed before the catch-all `ProxyPass "/"` line.
   Only `/` is proxied in this slice, so `/demonstrations`, `/submit` and event
   pages keep their current responses.

## Rollback

Remove or comment the Apache include and restart Apache, then revert the source
and rebuild the island bundle if needed. No database or session change is
required: `/api/session` is additive and unread once routing is rolled back.
