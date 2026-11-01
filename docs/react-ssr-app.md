# Standalone React public app (metadata-only server rendering)

Owner direction (1 November 2026): the public UI becomes React-only, migrated
pages stop using Jinja bodies, and the server cost of that stays low. This slice
starts the standalone host with the front page. The existing Flask pages remain
in place and unchanged for every route that has not moved yet.

The deadline is January 2027. New public work must be portable to the React
host; admin UI is excluded. Hosting a route in Node is an architectural step,
not proof of a speedup. Verify its blocking requests and data access before
claiming a performance improvement.

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
degrades to the anonymous header after a maximum 1.2-second wait. Cookie-bearing
requests always fetch their own summary. Cookieless public configuration is
coalesced and cached inside the host for five minutes; identity, role privileges,
notifications and failed responses are never shared through this cache.
Restarting the host clears it. Public locale options, fundraising visibility and
tracking configuration may therefore remain stale for up to five minutes.

The host rejects unmigrated routes before fetching session state. Static asset
reads are asynchronous, regular-file-only and restricted to the resolved asset
directory. Malformed URLs, directory requests and traversal attempts return
errors without terminating the host.

After `npm run app:build`, run `node scripts/verify_public_host.mjs` for bounded
request-count and host-availability checks. Eight concurrent cookieless page
requests cause one public-configuration lookup; warm requests cause none.
Private requests remain independent. This verifies removed work, not a measured
page-load speedup.

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
`/health` includes `status` and the deployed `build_sha`.

## Production release

Use the reviewed artifact procedure in [`deploy/public-app/README.md`](../deploy/public-app/README.md).
The maintainer approved the production deployment on 1 November 2026. The
root-owned release bundle contains `frontend/server.mjs` and `frontend/dist`;
the service uses a separately checksum-verified official Node 22 runtime, runs
as `www-data` on loopback `127.0.0.1:8090`, and needs no production npm install.
`FLASK_SOCKET_PATH` reaches the existing Gunicorn Unix socket directly rather
than sending header/session reads through the public CDN. No database
credentials or Flask signing secret are copied into the Node service.

`deploy/public-app/deploy.sh` verifies the archive, switches the release pointer
atomically and requires exact-build health before reporting success. It saves
the prior environment, unit and release pointer and restores them on failure.
Apache activation is deliberately separate: back up the active vhost, insert
the existing home-only include before its catch-all proxy rule, run configtest
and gracefully reload. Keep origin restrictions, TLS, existing proxy headers
and all unmigrated paths unchanged. The deployment README includes rollback.

### Production state, 1 November 2026

The front page has been served by this host since 1 November 2026, from merge
commit `0a10d6198d066d133965c1b4d21bbb8c22e3db18` (`#1012`), with the public
identifier API from `#1013` in the same release.

| Item | Value |
| --- | --- |
| Service | `mielenosoitukset-public.service`, active, enabled |
| Runtime | official Node v22.23.4, checksum-verified, `/opt/mielenosoitukset-public/node` |
| Release | `/opt/mielenosoitukset-public/releases/0a10d619…`, `current` symlink |
| Environment | `/etc/mielenosoitukset-public/environment` (public values only) |
| Apache include | `/etc/apache2/mielenosoitukset-react-ssr.conf`, inside the TLS vhost before `ProxyPass "/"` |
| Vhost backup | `/root/apache-backups/mielenosoitukset-le-ssl.conf.20261101T180335Z` |
| Deploy backup | `/var/backups/mielenosoitukset-public/20261101T180248Z` |

Checked on the live origin after activation: `/` returns 200 with
`Cache-Control: no-store` and `Vary: Cookie` from the host, `/app-assets/**`
returns the hashed bundle with `immutable`, `POST /submit` still reaches Flask
(400 JSON for an empty body), an unknown path still returns Flask's 404 HTML,
`/api/session` still returns JSON, and `/demonstrations` and `/users/auth/login`
are unchanged. A real browser rendered the header, hero, six live cards and
footer at 390px and 1440px with no console errors, and `/api/home?lang=fi`
returned 200. The service log contains no errors.

Two cosmetic facts are worth knowing: the response carries `Referrer-Policy`
twice because the host sets it and the server-wide
`conf-enabled/wordpress-hardening.conf` sets it again with the same value, and
the existing Flask socket is mode `0777` (pre-existing, not changed by this
release). Signed-in header state was not exercised against production because
that needs a real account session; the socket transport, cookie isolation and
anonymous/signed-in separation are covered by `scripts/verify_public_host.mjs`.

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

## Open items

1. Detail, listing, organization, Pride and submit routes still have Jinja
   shells. Each needs its metadata source and (where required) data contract
   before its GET rule is added.
2. Page data for migrated routes comes from the public Go API. Routes still
   served by Flask keep using the existing authenticated Flask APIs.
3. Independent visual acceptance is **SHIP** for the reviewed home, shared
   header/footer and admin analytics explanation: 390px/1440px, both themes,
   signed-in navigation and focus states. The packet SHA256 is
   `ab17febae09eaaea6c3aacd6e769ecdfa7b78267f402fc88f9caa213b6342a58`.
   This is scoped visual acceptance, not proof of production delivery.
4. A real local gateway now verifies Flask/Go/Node routing together. Repeat the
   public and signed-in smoke checks after production routing changes, including
   legacy page links, API/session transport, analytics and existing form paths.
5. Repeat the signed-in header check on production with a real account, and
   confirm the duplicate `Referrer-Policy` header is acceptable or change the
   server-wide header configuration.

## Rollback

The Apache include is what routes `/` to the host, so rolling back is:

```sh
sed -i '/mielenosoitukset-react-ssr.conf/d' /etc/apache2/sites-enabled/mielenosoitukset-le-ssl.conf
apache2ctl configtest && systemctl reload apache2
```

That sends the front page straight back to the unchanged Flask route. The
`/api/session` endpoint is additive and unread once routing is rolled back. To
stop the service afterwards, `systemctl disable --now mielenosoitukset-public`;
the release, backup and environment files can stay for inspection. Restoring a
prior Node release uses the backup directory the deploy script printed. No
database or session change is required.
