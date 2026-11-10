# Standalone React public app

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
| Detail head (title, canonical, JSON-LD, robots) | Server requests the same public API once, `/api/demonstrations/<identifier>` |
| Home card batch | Server reads `/api/home` once, caches it for 30 s and inlines it in the bootstrap |
| Information pages | Server renders the React page and shell. The client hydrates the navigation and theme controls. The content, guide anchors, FAQ and translator form work without JavaScript. |

The server accesses no event collection directly. Submission pages additionally
render a small React no-JavaScript fallback form; their interactive wizard is
browser-rendered and loads only on the submit route.
It composes the document and reads the bounded Flask session summary. Public
home data and event metadata come from the Go API through bounded caches;
production uses `PUBLIC_API_LOCAL=http://127.0.0.1:8091/api` for those reads.

### Information pages

The Apache include routes GET/HEAD `/info`, `/ohjeet` and `/ohjeet/`,
`/privacy`, `/terms`, and `/upcoming/translations/` to Node. Both guide
URLs canonicalize to `/ohjeet` and retain fragment navigation.
Page content and Finnish metadata live in the React app and require no content
API calls.

On the signed-in translation project page, Node asks the existing private
`GET /api/session?translation_join=1` scope for the join status, the existing
form CSRF nonce when needed, and flash feedback. Node forwards Flask's
session cookie update only for this scope. The scoped response and resulting
HTML use `no-store` and vary by cookie. The same-origin join POST stays in
Flask, where login, CSRF validation, permission grants and welcome mail
continue to run. Deploy the Flask contract and app build before activating
the reviewed Apache rules. Removing these rules restores the existing Flask
pages.

### Organization fill-in form

The Apache include routes GET/HEAD `/organization/<id>/fill` to Node. Node reads
the organization from the existing Go `/api/organizations/<id>` profile and
renders the form; a missing organization redirects home and an unavailable API
returns 503. The form posts to Flask's existing
`/organization/<id>/save_suggestion`, which stores the suggestion, opens a case
and notifies moderators, then redirects to the organization page. Adding social
media rows needs JavaScript; the rest of the form works without it. Removing the
rule restores the Flask page.

### Demonstration change suggestions

GET/HEAD `/suggest_change/<ObjectId>` is rendered by the standalone React host.
It reads only Go `GET /api/demonstrations/<id>` for event data. The additive
`suggestion` object contains original (not translated) form values, comma-joined
tags and route stops, newline-joined public organizer display names, and
`description_markdown`. Go mirrors Flask's `html_to_markdown` with the already
installed `golang.org/x/net/html` tokenizer; no new dependency is needed.
Missing/nonpublic events redirect home (302); API failures or an older Go
response without `suggestion` return 503 with `Retry-After: 30`. The form is
noindex and its bootstrap uses the same data for hydration.
The returned ID must match the requested ObjectId: an alias resolved by the Go
detail endpoint redirects home rather than editing another record.

The public API's visibility and organizer-consent boundary remains authoritative:
only approved, non-hidden, non-rejected events are readable, even though the old
Flask GET looked up any known ObjectId. Unconsented organizer details never enter
the response. If redaction makes an organizer list incomplete, the safe current
names are shown separately and the editable list starts empty. An untouched form
therefore cannot suggest a lossy replacement for that list. This is a deliberate
privacy exception to exact legacy prefill parity.

The plain HTML form still POSTs the same fields to Flask
`/suggest_change/<id>` for comparison, moderation storage and notifications.
It submits without JavaScript; JavaScript adds editable list rows and Markdown
formatting/preview. Cancel is a red button targeting a separate GET form so no
suggestion fields or reporter contact details enter the navigation URL.

Rollout order: deploy Go first, build/deploy the host, verify the form and API,
then activate the exact GET/HEAD Apache rule. Removing just that rule restores
the untouched Flask GET/template; POST ownership and stored suggestions never
change. Do not remove the Flask implementation in this migration. Visual
acceptance remains BLOCKED until real application captures at 390px/1440px in
both themes and independent reviewer SHIP are available.

### Contact page

The Apache include routes GET/HEAD `/contact` to Node. The form posts to Flask
at the same URL, where every existing check stays: per-IP and global rate
limits, the size cap, the one-time token (2 seconds to 2 hours old, at most 5
outstanding, consumed once so restored cookies cannot replay it), the honeypot,
field validation and email delivery. Flask then redirects back to `/contact`,
and Node shows its feedback.

**Session scope.** For each GET, Node calls
`GET /api/session?contact_form=1`, with the visitor's cookie or with none. The
response adds `contact_form`: `enabled`, a new `csrf_token` from the existing
`_new_contact_form_token()`, pending `messages`, and the field `limits` from
config. It is `no-store` and varies by cookie. Because the token lives in the
visitor's session, this is a private read even without a cookie: it never uses
the shared anonymous summary, and Node forwards Flask's `Set-Cookie`. The page
is `private, no-store`. `HEAD` skips the scope and mints nothing. If the read
fails, the page shows the support email instead of a form. Approved by the
maintainer on 9 November 2026 as a session change.

Removing the Apache rule restores the Flask page; the scope is additive.

### Campaign page

The Apache include routes GET/HEAD `/kampanja/` to Node. Flask keeps the
`/kampanja` slash redirect, the volunteer signup
`POST /kampanja/api/volunteers`, email confirmation `/kampanja/confirm/<token>`
and the existing template as the rollback path. The page is the same
`CampaignPage` component the Flask island used, now rendered on the server and
hydrated; its Finnish copy and endpoints live in `frontend/src/app/campaign-route.ts`.

The page has the same publication gate as Flask's `campaign_preview_required`:

| Publication | Visitor | Response |
| --- | --- | --- |
| Not published | Anonymous | `302` to `/users/auth/login?next=%2Fkampanja%2F` |
| Not published | Signed in | `200` preview with `X-Robots-Tag` and robots meta `noindex, nofollow` |
| Published | Anyone | `200`, indexable |

Every response is `private, no-store`, so a later return to private cannot be
served from a cache.

**Publication API.** `GET /api/campaign/publication` on the Go API returns
`{"published": true|false}` with `Cache-Control: no-store`.
- *Purpose:* lets the host apply the gate without a Flask route.
- *Request:* no parameters. `GET` and `HEAD` only; other methods get `405`.
- *Authentication and authorization:* none; it reveals only whether the page is
  public, which the page itself shows to anyone once published.
- *Database:* one read of `campaign_settings` `{_id: "public_pages"}`, at most
  once a second per process, outside the response caches and Redis.
- *Semantics:* only a stored boolean `true` counts, matching Flask. A missing
  document, any other value, a failed read and the public lockdown (`503`)
  all mean private, and the host treats any non-`200` or malformed reply the
  same way.
- *Replaces:* the `campaign_pages_public()` read for page GETs only. The Flask
  signup API keeps its own gate.

Deploy the Go API and the host before activating the Apache rule. Removing the
rule restores the Flask page.

### Fundraising page

`/keräys` (sent as `/ker%C3%A4ys`) is routed to Node behind the same
publication gate as the campaign page. The page content is the Flask template
as a React component (`frontend/src/app/FundraisingScreen.tsx`).

Its data still comes from `mielenosoitukset_fi/utils/data/fundraising.json`,
which the host build bundles. Editing that file therefore needs a host
deploy, which every push to `main` already runs. `frontend/src/app/fundraising.ts`
ports `fundraising_details()`, which decides when the organizer, collection
number and payment details may appear. Both versions are tested against the
shared cases in `tests/fixtures/fundraising_parity.json`
(`tests/test_fundraising_parity.py` and `scripts/verify_public_host.mjs`), so
a change to either rule fails until both agree. Regenerate the fixture from
Python when the rules change on purpose. The TypeScript port accepts dates only
as `YYYY-MM-DD`, the format this file documents; any other form keeps
donations closed. The server passes its Helsinki date to the browser so both
render the same state.

The Flask route and template stay as the rollback path; removing the Apache
rule restores them.

## Files

- `frontend/src/app/detail-route.ts` — the detail and series head reads, occurrence
  selection and the series navigation that the host renders.
- `frontend/src/app/` — configuration (existing public URL paths), copy catalog
  (fi/en/sv), routes, session contract, header props, footer, app shell, server
  render and browser entry. `detail.ts` holds detail copy and endpoints,
  `detail-route.ts` loads one event for the head, and
  `components/detail/DetailScreen.tsx` is the browser adapter shared with the
  Flask island.
- `frontend/vite.app.config.ts` and `frontend/vite.app.ssr.config.ts` — separate
  client and server bundles. Output goes to `frontend/dist/` (not committed).
- `frontend/server.mjs` — HTTP server: metadata pages, `/app-assets/*`, `/health`.
- `deploy/apache/react-ssr-routing.conf` — web server routing rules.
- `mielenosoitukset_fi/basic_routes.py` — `GET /api/session`.

## Demonstration detail route

`GET /demonstration/<identifier>` is enabled in the reviewed Apache include.
The maintainer approved activation on 1 November 2026. Deploy the matching Go
API and host before installing the include, and complete visual acceptance.

The host claims exactly one path segment. `/demonstration/<id>/ics`,
`/demonstration/<id>/some` and a trailing slash keep their Flask handlers.
The series route is separately listed below.

An occurrence URL of a public series is 301'd to
`/demonstration/<parent>/children?occurrence=<slug or id>`, like Flask; when the
parent series is not public the occurrence renders on its own, which is also the
Flask behaviour.

## Recurring series route

`GET /demonstration/<parent>/children` is hosted and reads
`/api/series/<parent>`: parent visibility plus the bounded occurrence list
(upcoming, recent past, cancelled). The host selects the occurrence — the
`?occurrence=` slug, id or running number when it is active, otherwise the next
active one, otherwise the latest past one — then reads that occurrence's detail
for the head. Canonical is the series URL without the query, and robots is
`noindex` when no occurrence date falls inside the discovery window.

Upcoming occurrences are listed first, then cancelled and past ones, matching the
chooser. A series with no active occurrence is 404 with `noindex`; a nonpublic or
unknown parent is 404; an unavailable API is 503. The Apache rule for this path
is enabled alongside the detail rule.

The head comes from one bounded (1.5 s) read of the public API. The host caches
successful metadata for 60 seconds, not session-bound HTML. The identifier is
resolved by the API in the same precedence the site already uses (ObjectId,
alias, running number, slug), and the canonical link always uses
`slug`, then `running_number`, then the id. Description text is stripped of markup
and truncated to 200 characters like the shell. `application/ld+json` carries the
same `Event` fields as the template. Dates past the two-year discovery horizon
send `noindex, follow` in the head and in the `X-Robots-Tag` header.

A missing or nonpublic event returns 404. A signed-in visitor is redirected to
the same URL with `?preview=1` so the existing Flask preview workflow still
answers; the flag is excluded from the host routing rule and a flagged request
that reaches the host returns 404 instead of redirecting again. An API failure
returns 503 with `Retry-After`, never a page that looks indexable.

Detail views are counted by the screen's existing `POST /api/analytics/track_view`
call, so the generic pageview beacon is not sent for this route and cannot
misattribute the view to the referrer. A detail page is always loaded as a
document: the client bundle only navigates in place for the front page, which
keeps every detail entry with a server-rendered head and a resolved event id.

## Detail copy and endpoints

`frontend/src/app/detail.ts` holds the detail screen's copy (`DetailMessages`),
the account-route templates it posts to and the canonical path helper. It is the
single source instead of Flask template props, so detail copy moves here rather
than into `react_detail.py`; `tests/test_public_detail_copy_parity.py` fails if
the two diverge while the Flask shell still supplies the island. Finnish is the
source catalog and `en`/`sv` reuse it until a human translator supplies those
strings. The route itself still needs the single projected event read in the
head path before it can move here.

## Standalone demonstration listings

The host owns `/demonstrations`, `/city/<city>` and `/tag/<tag>` GET/HEAD.
React owns the filters, localized calendar, city selection, URL history,
retry controls and a maximum five-page card window. The old listing island
remains available to organization pages until their whole page moves; the
standalone pages load none of its global pagination/filter scripts.

`GET /api/demonstrations` on Go supplies public card data. The host reads it
over loopback, coalesces identical requests and embeds the initial page in the
document. Successful public pages are cached for 30 seconds with at most 64
entries and 16 in-flight query variants; stale `no-store` API fallbacks are not
cached again. Query normalization is shared with the browser and excludes
campaign parameters while retaining those parameters in the address bar.
Go's separate 30-second cache is bounded by both memory and entry count;
combined host/API/browser freshness windows can add, rather than guaranteeing
30-second end-to-end freshness. See [the API contract](go-listing-api.md).

Only listing documents preload their split listing/calendar bundle. Home does
not download it. Page, search, campaign and Web Vitals tracking use the existing
allowlisted analytics endpoints; Go cache hits never substitute for browser
display/search signals. DNT and analytics settings retain their existing rules.

`/pride-nakyvaksi`, `/pride` and `/pride/` render the Pride page on the host with
the same `tag=pride` listing bootstrap and the existing Pride map, which reads
every Pride page from the Go listing endpoint at `per_page=100`. The canonical URL
is `/pride-nakyvaksi`; filtered addresses are `noindex`. Leaflet still loads from
`/static/leaflet/`. Without JavaScript the document lists the first page of events.
The Flask template stays as the rollback path.
RSS links keep their city/tag scopes. Signed-in attendance remains with Flask.

Deployment order is Go API, host release, then the reviewed listing GET routing
rule. Removing that rule returns the pages to the existing Flask shells without
changing their URLs or data. All writes stay with their existing handlers.

## City discovery and today

The host also owns exact GET/HEAD `/cities`, `/mielenosoitukset-tanaan` and
`/city/<city>/tanaan`. The directory uses Go `/api/cities`; today reuses
`/api/demonstrations?today=true` with its city scope fixed by the route. Date
parameters cannot turn a today page into a different date range. Both caches
include the Helsinki day, and open pages reload after the day changes.

Directory summaries are coalesced and cached for 60 seconds in the host and
origin loader. The shared API tier permits five minutes, capped at midnight;
these layers can add freshness delay. Only public counts and the generated
city catalog reach the document. See [the contract](go-cities-api.md).

Navigation between pages uses normal links and browser document loads, including
Back/Forward. React owns in-page search and filter history. The initial document
contains canonical/title/description and collection structured data, with
no-JavaScript discovery links or event summaries. API failures produce a
non-indexable 503 with a React retry control rather than a false empty result.
Filtered directory URLs are non-indexable and canonicalize to `/cities`.
The directory groups compact city links by initial in Finnish alphabetical
order. Search narrows those groups as you type and preserves the existing `q`
and `today` query filters. The unfiltered grouped directory, including event
counts and today links, also renders in the no-JavaScript fallback. Counts appear
inline only for cities with upcoming events, with the full Finnish phrase for
screen readers. Native letter jump links target the existing group headings;
they are hidden while search text is active and work without JavaScript.

Deploy Go first, then the host, then the exact Apache GET/HEAD allowlist.
Removing only the discovery/today routing rule restores the existing Flask
pages. API and write ownership does not change. The homepage does not preload
the split directory or today bundles.

## Submission form

Exact GET/HEAD `/submit` renders the portable React wizard with a fresh
idempotency token per document and `Cache-Control: no-store`. Source copy and
URL configuration live in TypeScript; the host does not fetch the Flask form
or its island props. Shared public session configuration remains briefly cached
for anonymous visits, while signed-in summaries stay private. The form and its
editor/calendar bundle are split from home. Native page navigation and server
canonical/title/description remain consistent with the other migrated pages.

Exact POST `/submit` is forwarded to Go `/api/submissions`, never Node. The
Facebook importer and organization search retain their existing Flask URLs.
Flask's existing worker owns email sending and trusted link preparation. See
[the submission contract and safety/rollout details](go-submission-api.md).

Deploy the Flask worker first, enable/configure Go intake and verify its socket
access, then deploy the host and activate both exact Apache method rules. Remove
both submit rules to roll back to the existing Flask GET/POST flow; keep the
updated worker running to drain already accepted Go submissions. No database
rollback, mail-queue deletion or public response cache purge is needed for this
uncached write route. The old Flask React/legacy templates remain rollback paths.

## Organization profiles

`GET/HEAD /organization/<ObjectId>` uses the standalone React screen and public
Go `GET /api/organizations/<id>`. Only the allowlisted profile fields are public;
membership records and invitation lists never enter that API or its cache.
The Go cache has a 60-second lifetime and 128-entry/2 MiB bounds. The host
coalesces public profile reads, caches up to 64 profiles for 60 seconds, and
starts the profile read alongside the session request. Cache layers can add
freshness delay. Missing valid identifiers retain the existing home redirect;
API failure returns a non-indexable 503. Malformed/nested paths keep their
existing handlers.

The initial event batch comes from the shared Go listing API and is embedded
with the profile. The organization scope overrides URL parameters, and conflicting
parent, past and maximum-day filters are removed like the legacy page. Search,
dates, city selection, cancelled events and pagination use the shared React
listing. No generic RSS feed is presented as an organization-specific feed.

Signed-in requests ask the existing `/api/session?organization_id=<id>` endpoint
for one organization's follow/invitation state and four management booleans.
These are display hints, never authorization; every write retains its existing
Flask permission check. Private summaries and HTML are uncached. Cookieless
requests keep using the ordinary shared public summary without organization
permissions. No account cookie or database credential is exposed to JavaScript.

The existing native invitation forms retain their POST targets. When feedback
is queued, the private summary reports only that fact; the browser reads the
existing `/get_flash_messages` endpoint with `no-store`, allowing Flask's
cookie update to consume the messages once. Ordinary profile visits make no
extra feedback request. Follow actions likewise retain the existing endpoints.
Fill forms, administration and writes remain with Flask.

Organization code, calendar, shared listing and toolbox styles are split into
route bundles and preloaded only where needed. Home downloads neither the
organization screen nor its styles. Organization page/search/campaign/Web Vitals
signals use the existing analytics handlers and respect DNT/settings.

Signed-in organization pages retain their chat launcher as a React component.
The conversation panel and existing Socket.IO client load only after it is
opened; messaging still uses Flask's existing authenticated friend checks and
socket events. Private messages stay in component memory and never enter the
public API, bootstrap or caches. Closing the panel disconnects its socket.

Deploy Go first, then the host, then the exact organization GET routing rule.
Rollback removes that rule and restores the previous host/API release, leaving
the preserved Flask profile and data intact. See [the public API contract](go-organization-api.md).

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
Socket requests preserve the validated reverse-proxy peer and Cloudflare
client header; Flask retains its own Cloudflare-network validation. Forwarded
headers are accepted only from the host's loopback proxy, keeping the session
rate limiter scoped as it was before migration. No IP is added to cache keys.
Restarting the host clears it. Public locale options, fundraising visibility and
tracking configuration may therefore remain stale for up to five minutes.

The host rejects unmigrated routes before fetching session state. Static asset
reads are asynchronous, regular-file-only and restricted to the resolved asset
directory. Malformed URLs, directory requests and traversal attempts return
errors without terminating the host.

After `npm run app:build`, run `node scripts/verify_public_host.mjs` for bounded
request-count and host-availability checks. Eight concurrent cookieless page
requests cause one public-configuration lookup; warm requests cause none.
Private requests remain independent. It also asserts that repeated detail views
reuse the cached head, that the home batch is read once and reused, and that
server reads use the local API address. This verifies removed work, not a
measured page-load speedup.

### Server-side public caching

- Detail head metadata: 60 s TTL, 500 entries, keyed by read base, locale and
  identifier. Only successful public metadata is stored, so a newly published or
  edited event appears within a minute and failures are never cached.
- Home batch: 30 s TTL, 4 entries, keyed by read base and locale. The same batch
  is inlined into the document, so the browser paints cards without a second
  request; a failed or invalid batch falls back to the browser request.
- Nothing session-bound is ever cached here: the session summary keeps its own
  rules and private responses stay uncached.

Measured on 1 November 2026 before this change: `GET /` 207 ms TTFB, `GET /api/session`
195 ms, `GET /api/demonstrations/<id>` 130-190 ms, and `GET /api/home` about 470 ms
with `Cache-Control: no-store` and `cf-cache-status: DYNAMIC`. That last response is
the front page's real bottleneck, since the cards wait for it after hydration. The
host-side cache removes it from repeat page views; making the API itself cacheable
at the edge is a separate change on the API side.

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

## Public lockdown and restarts

Every page except `/health` and `/auth/god` first asks the Go API's
`/api/public-status` whether the site is locked down, at most once a second.
The Go API reads the `panic` collection for that answer in the same way.

- An explicit lockdown answer applies at once and clears the remembered "open"
  answer, so a later failed read cannot reopen the site.
- A failed or timed-out read is not a lockdown. For up to 30 seconds after the
  last explicit "open" answer, both the host and the Go API keep serving; after
  that, or with no answer since the process started, they fail closed with the
  maintenance page. This keeps a Go API or database restart from briefly closing
  the site. Approved by the maintainer on 9 November 2026.
- `deploy/public-app/deploy.sh` waits until the host renders the home page with
  its own assets, not only `/health`, and `deploy/release_routing.sh` retries
  each page probe three times, two seconds apart, before restoring the previous
  routing include.

## Routing

The web server sends only migrated page GET/HEAD requests to the app host:

| Request | Handler |
| --- | --- |
| `GET|HEAD /` | React app host |
| `GET|HEAD /demonstration/<id>` | React app host (except `preview=1`) |
| `GET|HEAD /demonstration/<parent>/children` | React app host (except `preview=1`) |
| `GET /demonstration/<id>/ics`, `/some` | Flask (unchanged) |
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
PUBLIC_API_LOCAL=http://127.0.0.1:8080/api \
APP_PORT=8090 npm run app:start
```

`PUBLIC_API_LOCAL` is the address the host uses for its own server-side reads; the
browser keeps `PUBLIC_API_BASE`. Pointing the server at the API on loopback avoids
a public round trip (measured 130-190 ms) that the host would otherwise pay to
reach an API on the same machine.

For local verification only, `STATIC_DIR=mielenosoitukset_fi/static` lets the app
host serve `/static/*`, which production serves directly from the web server.
`/health` includes `status` and the deployed `build_sha`.

## Production release

A push to `main` builds, publishes and deploys this host automatically; see
[`docs/production-deployment.md`](production-deployment.md). The workflow builds
`frontend/server.mjs` plus `frontend/dist`, publishes them as a
`release-<commit>` asset, and the server installs them only when
`http://127.0.0.1:8090/health` does not already report that commit. Apache
routing runs automatically after that deployment and its health checks succeed
on a push to main. Configuration validation, backup and rollback still run;
manual dispatch can opt out of routing for recovery. The manual procedure in
[`deploy/public-app/README.md`](../deploy/public-app/README.md) remains the
break-glass path.

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
Apache activation remains a dependent job: back up the active include, install
the committed rules before the catch-all proxy, run configtest and gracefully
reload. Keep origin restrictions, TLS, existing proxy headers
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
