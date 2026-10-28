# Incremental React frontend

Flask/Jinja owns the public page shell; the shared header is a React island. React owns the campaign content and
volunteer confirmation, reusing the existing volunteer form. The footer, fundraising page, admin and authentication stay in Jinja. No SPA router
or JavaScript server runtime is required. Campaign and fundraising typography
follows the supplied brand book (Montserrat headings, Roboto body), with the
existing product tokens and shared navigation.

## Develop and build

Use Node 22.12+ (Node 22 LTS is used in CI) and the existing Python environment:

```sh
npm ci
npm run build
# Run Flask as usual, in a separate terminal:
npm run dev
```

`dev` watches sources and rebuilds the same static files Flask serves. Refresh
the Flask page after a rebuild. There is deliberately no second origin, HMR
server, CORS configuration or authentication proxy. `npm run typecheck` checks
TypeScript without writing files. Run `npm run build` before committing; watch
output is not a substitute for the final checked production build.

Vite writes hashed assets and `manifest.json` to
`mielenosoitukset_fi/static/frontend/`. **Commit that directory with the source
and package-lock.json.** This is an intentional bridge to the existing git-based
Python deployment and Docker image: both already include these static files and
need no Node installation at runtime or on the production server. The existing
test workflow builds from the lockfile, type-checks and rejects stale or extra
generated files. Do not edit the generated JavaScript manually. `node_modules`
is excluded from Git and Docker contexts.

This adds approximately 70 KB gzipped on the campaign page, including React;
other pages do not load it. Revisit artifact delivery through CI if the frontend
grows enough that committing builds becomes burdensome. Assets use relative
internal imports and Flask-generated static URLs, so a static URL prefix is
supported. Future entries can share dependencies through Vite's chunk graph.

## Add another island

1. Write a typed component under `frontend/src/components/` and a page entry
   under `frontend/src/entries/`. Import `vite/modulepreload-polyfill` and use
   `mountIsland` from `lib/mount-island.tsx` in the entry.
2. Add its entry to `frontend/vite.config.ts`. Keep unrelated page entries
   separate so visiting one page does not download every React screen.
3. Mark the owned region with `data-react-island="your-name"` and
   `data-props-id="your-config-id"`. Put props in an `application/json` script
   with that ID, serializing a Jinja dictionary using `tojson` (never `safe`).
4. Import `frontend_entry` from `_macros/frontend.html` and call it only on the
   consuming page with the manifest source key, such as
   `src/entries/volunteer.tsx`. The Flask resolver includes dependent CSS first.
5. Remove legacy event handlers that touch that region. React uses `createRoot`
   to replace its fallback; Jinja markup is not React hydration output.
6. Add meaningful browser checks for the workflow and follow the project's
   in-conversation visual acceptance process in both themes and widths.

Flask/Babel remains the translation source. Pass translated behavior messages
as JSON props instead of introducing a separate frontend translation catalog.
The initial form's labels remain Finnish, matching the existing `lang="fi"`
campaign section; its feedback retains the existing fi/en/sv translations.

## Volunteer form contract

The form posts the same trimmed `name`, `email`, `phone`, `city` and `notes`
JSON fields to the endpoint supplied by `url_for('campaign.add_volunteer')`.
Same-origin session cookies are included. Publication/login checks, validation,
database writes, confirmation tokens and queued email remain in Flask. Mounting
React grants no permission. Server rules must also be applied to the API.

The component owns feedback, invalid-field markers, first-invalid focus and
pending state. A synchronous ref prevents simultaneous submissions; controls
are disabled while a request is pending. Failed requests retain entered values;
successful signups clear the form and ask the user to confirm by email. Server
error text is rendered as plain React text, never HTML. Non-JSON responses and
login redirects are failures, not successful signups.

The existing disabled Jinja form is a deliberate no-JavaScript/load-failure
fallback inside the island, with the same fields and IDs. It has no submit
handler and must remain disabled. A loading/contact notice remains visible if
the module fails to load; `noscript` also explains that nothing was sent. Keep
this small fallback aligned with field changes in the React component. No other
script may enable it. A render failure restores the disabled fallback.

The static recovery exporter can keep campaign/collection information in its
server-rendered HTML while removing interactive forms and scripts. A working
React signup is not promised on a static recovery copy.

Reference: [Vite's backend integration](https://vite.dev/guide/backend-integration).

## Campaign-page refresh (27 October 2026)

The campaign and token-confirmation page content now belongs to React page
components. `CampaignPage` composes the existing `VolunteerForm` without changing
its source, field names, validation, request body or confirmation workflow.
The newsletter keeps its Mailist endpoint/list ID but uses plain success copy,
HTTP/schema-aware feedback, pending protection and retryable errors.

`npm run build` also invokes `frontend/prerender.mjs`. Vite loads the same page
components at build time and React renders their fallback HTML to tracked Jinja
partials. Only explicit internal URL placeholders become Jinja markup;
no user input becomes template source. Flask renders these partials into the
initial response, so headings, copy, navigation and confirmation states do not
wait for JavaScript. The existing mount helper replaces the fallback once its
page entry is ready; this is not hydration. Disabled fallback forms cannot submit
or claim success. A direct support email remains outside the forms for static
recovery. The existing HTML mirror still requires its own export/serving checks.

No Node runtime, React server process, new API call or browser-side routing is
added to Flask's request path. Asset resolution caches the parsed manifest per
app and refreshes on mtime/size changes, including development/release rebuilds.
This reduces repeated filesystem reads/parsing, not a measured TTFB-parity claim.
Page-specific modules share the React runtime through the normal Vite chunks;
other public pages and the admin still do not load these entries.

`npm run dev` watches client bundles; run `npm run build` to refresh fallback
partials too before committing or testing JavaScript-disabled delivery. Existing
CI verifies both tracked bundles and generated fallback files. Do not hand-edit
the generated Jinja files. Future dynamic page data can continue to come through
Flask's escaped JSON props; the campaign's static copy needs no runtime fetch.

Coverage: campaign page content and confirmation success/expired/invalid states
are React; outer Flask metadata/authentication and the existing global chat stay
in their current implementation. No other route is declared migrated by this
slice. Public-page translation/routing work and the rest of UI-06 remain open.


## Shared header (27 October 2026)

`SiteHeader` composes `NavigationLink`, `LanguageSwitcher`, `UserMenu`,
`NotificationMenu` and `ThemeToggle` under `frontend/src/components/header/`.
`header.html` derives URLs, permissions, notification count and translated labels
from the existing Flask context and serializes props with `tojson`. No new
endpoint, session protocol, router or backend service is introduced. The header
entry is intentionally shared by all consumers of this public header; React's
runtime chunk is reused on pages that also load a page entry.

The Jinja fallback reuses the same link/account data. Without JavaScript or if
modules fail to load, mobile navigation uses a native HTML disclosure and
account destinations remain accessible;
notification history is a normal link and controls needing JavaScript are absent.
React replaces this fallback using the existing mounting helper, not hydration.
The native mobile disclosure starts compact like the mounted header, so the
static link list does not expand and collapse during module loading. Desktop
fallback links stay visible. Assess actual loading/layout behavior in production
before making performance claims.

After mounting, React alone owns menu state, focus, theme controls, notification
fetching/polling and mark-read feedback. Legacy inline header handlers and the
unreferenced `public-notifications.js` are removed. The page-level theme helper
remains for other consumers; the header observes root theme-class changes.
The header wrappers use `display: contents` so they do not constrain sticky
navigation. Profile, settings, logout and administrative checks remain on the
server. No account secrets or authentication tokens are added to props.

This completes the shared header slice, not the public page migration. Next:
listings with shared filters/cards/pagination, then event details and recurring
series with shared event metadata, organizer and occurrence components. Before
moving indexable bodies, verify initial HTML, canonical URLs, metadata, locale
behavior and the existing occurrence query contract. Design any API changes from
those real needs in a separate reviewed proposal.


## Public listing components (27 October 2026)

The stacked branch `codex/react-demonstration-listings` follows
`codex/react-site-header` (PR #990). Main, city and tag listings compose
`DemonstrationListingPage`, `ListingTools`, `SearchFilters` and
`DemonstrationCards`/`DemonstrationCard`. The same components serve all three
routes. Their scoped city/tag values and translated labels come from escaped
Flask JSON; routes, data queries and authorization rules are unchanged.

The reusable `public-layout-wide` shell uses the available viewport width with
small responsive margins. The tools panel follows the supplied brand book:
Montserrat headings, Roboto form text, semantic blue heading/secondary action
and orange search action with dark text. `--product-on-accent` defines the
accessible dark foreground for the existing orange accent. Cards keep their
existing shared presentation and inherited Inter font. The grid can show more
columns on larger screens. Only these listing routes opt into the wide shell.
No decorative eyebrow labels or large marketing hero remain on these pages.
New context headings use colons; do not add em dashes to UI copy.

### DOM ownership and existing widgets

Flask renders initial titles, navigation and a disabled search fallback.
React replaces that fallback, rather than hydrating it. The fallback explains
loading/JavaScript requirements in Finnish, English and Swedish and never
pretends to perform a successful search. Existing listings already fetched
cards through JavaScript; this slice retains that rendering model and the
server's document title/metadata shell. It does not claim server-rendered event
cards or solve discovery SEO. Choose initial-content rendering before migrating
the currently server-rendered event-detail bodies.

The tested `UserPagination` window/history controller, pinned Flatpickr date
widget and city autocomplete remain deliberate adapters. React owns the page
composition; native uncontrolled inputs and empty suggestion/chip targets are
owned by those widgets. The window controller owns pagination controls and
page wrapper nodes inside the results grid. Each wrapper contains a React root
for its cards. No legacy card renderer or legacy card navigation listener is
loaded on these three routes. Other consumers of the legacy renderer are
unchanged and remain separate migration tasks.

The listing results use one continuous CSS grid. Page roots use `display:
contents` so an API page ending halfway through a row does not leave empty cells
before the next page. The window controller measures those roots through their
card boxes and anchors a surviving card during eviction/prepending. Other
consumers with ordinary page boxes retain their existing geometry. Regression
checks include five/eight-column layouts, the 60-card window, keyboard focus,
scroll anchoring and hidden/loading results.
The first retained card keeps its global column via a scoped grid-column value,
recomputed on viewport resize. Any partial row is confined to the start of the
retained window; internal API page boundaries stay continuous, and eviction does
not move surviving cards sideways.

The typed listing adapter checks response metadata, cancels replaced searches,
ignores stale responses and leaves failed requests available for explicit retry.
It keeps a maximum of five mounted pages, respects focus/viewport eviction
rules and disposes React roots when a page leaves the window. Each mounted page
owns one authenticated attendance batch; eviction and replacement abort the
corresponding request. React renders event/friend text as text and accepts only
same-origin event URLs. Invitation URLs retain existing queries before adding
the invitation action. Existing card classes, hover behavior, guest messaging,
badges, images and layout remain in use.

### Existing API contracts used by the components

| Operation | Actual consumer and request | Response and data ownership |
| --- | --- | --- |
| GET `/api/demonstrations` | Listing adapter; existing search/city/location/date/tag, page/per_page, locale and history-restore parameters | Existing localized results, canonical detail URL, counts and page metadata. Existing Mongo filters, visibility rules and resource caps stay in Flask. |
| POST `/api/friends-attending` | Authenticated mounted card page; existing JSON `demo_ids` array with same-origin session cookies | Existing mapping from demo ID to friend name/avatar records. Flask determines friend membership and attendance; the client adds no permission or write authority. |

These are existing APIs, not a proposal for a new backend. No database schema,
new endpoint, subdomain, router, session mechanism or deployment topology is
introduced. Event/series detail bodies, organization pages, homepage card
consumers, footer and final routing/rendering consolidation remain open.


### Repeatable local verification

Use the same command for future listing work, with Python 3.12+ development
requirements and installed frontend dependencies:

```sh
python3.12 scripts/verify_react_listings.py all --output-dir /tmp/moso-listing-qa
```

Use `--node /path/to/node` to select Node 22.12+ explicitly. `check` runs the
build/typecheck and focused regression set; `capture` regenerates visual evidence
without repeating the tests. `--stage before` records the current pre-change
reference. Keep the output outside the repository. Capture metadata records
source and screenshot hashes and rejects source changes during capture or stale
output. Four photo-bearing states require decoded image pixels in both widths
and themes. The script supplies evidence; an independent reviewer still must
issue the final visual verdict. It adds no CI workflow or separate CI suite.

The API can return null or absent start/end times. The card formatter accepts
those values, labels an end time when no start is available, and omits the clock
when both are unavailable. A failed React card batch follows the existing retry
path: it does not advance the window, URL or count, and existing pages survive
an append failure. React root error callbacks must remain connected to that
loader result; a successful HTTP response alone does not prove cards rendered.

Include the real-data nullable-clock and pagination scenario after clock or card
renderer changes:

```sh
python3.12 scripts/verify_react_listings.py capture --scenario missing-times --output-dir /tmp/moso-listing-missing-times
```

This seeds null/absent clocks and photos in the disposable database and exercises
page restoration, previous-page and load-more behavior. Keep separate output
directories for each source snapshot.

Use `--scenario continuous-grid` for page-boundary layout changes. It adds the
1680px five-column case to the usual 390px/1440px themes, plus authenticated,
keyboard-focus, restored-page, empty and loading captures.

### Before/after response latency

Use the same Python 3.12+ development environment and disposable test services
to compare two committed revisions locally:

```sh
python3.12 scripts/compare_listing_latency.py --before <baseline-ref> --after <candidate-ref> --attempts 500 --output-dir /tmp/moso-listing-latency
```

The command exports both revisions without changing the working checkout,
seeds identical synthetic events into separate test databases and starts the
real Flask application for each revision. Warmup requests precede alternating
before/after samples for the main, city and tag HTML pages and their existing
listing API. It records raw timings, response sizes, revisions, fixture/config
metadata and p50/p95/p99 summaries. Use an empty output directory outside the
repository for every comparison.

These are warm loopback HTTP response measurements with one sequential client.
They do not measure browser rendering, asset delivery, LCP, production network
conditions or production capacity. Report the sample count and these limits
alongside any comparison; tail percentiles remain sensitive to host load.

## Submission flow

`/submit` now loads the `submit` entry from the existing Vite build. React owns
`SubmitProgress`, `SubmitChoices`, `SubmitNavigation` and `SubmitBack`. Each
region keeps functional Jinja controls when the module is unavailable. There is
no new route, API, authentication scheme or form payload. The server-localized
props are serialized with `tojson`.

The existing controller remains the owner of active field panels, validation,
Quill, organizer lookup, Facebook import, draft storage and multipart POSTs.
`showPage` emits `submit:stepchange`; progress reads the active panel on mount so
an early draft restoration is not overwritten. React does not replace field
nodes or attach competing submit handlers. The final submit button remains
owned by the existing pending/retry handler. Native field components can migrate
in a later slice together with their integration initialization.

Only a non-redirected JSON response with `success: true` confirms delivery, for
both the first attempt and a confirmed duplicate retry. Other responses retain
the form/draft. Date/time draft restoration uses the existing picker API to
restore both submitted values and required alternate inputs. Navigation validates before advancing and focuses the new panel
heading. Failed validation still focuses its first invalid field.

The form's styles are scoped under `.submit-page` and consume product tokens.
Desktop uses a step rail with the form filling the remaining available width;
mobile keeps progress in normal flow, with no overlay over fields or actions.

Repeat local checks/captures with the project Python 3.12 development environment
and Node 22.12+:

```sh
python3.12 scripts/verify_submit_form.py all --output-dir /tmp/moso-submit-qa
python3.12 scripts/compare_listing_latency.py --scope submit --before BASE --after HEAD --output-dir /tmp/moso-submit-latency
```

The HTTP comparison measures GET `/submit` only, excluding browser work and
writes. Capture output uses disposable data and actual assets; independent
in-conversation visual acceptance is still required. Roll back this slice by
reverting its source, template, stylesheet and committed generated build together.

## Organization event lists

The public `/organization/<org_id>` profile embeds the existing listing entry.
`_partials/demonstration-listing.html` is the shared source for localized props
and disabled fallback controls on main/city/tag and organization collections.
`headingLevel: 2` places the event section beneath the profile's sole h1; empty
results use h3. Profile information, follow actions and server-computed toolbar
permissions continue in their existing templates. The page uses available width.

The consumer reuses GET `/api/demonstrations` with server-fixed `organization_id`,
12 records per page by default and the existing public filter fields. Anonymous
access is intentional. The existing API matches BSON ObjectId organizer links
under the public approval/visibility rules; cancelled events remain visible in
organization scope and future events have no artificial 60-day ceiling. User
query parameters, filter changes, history restoration, pagination and retries
cannot replace the fixed organization. Membership/user records are not loaded
or serialized into public listing props. No backend write or authentication
contract changes. Malformed organization IDs return 404; existing missing-ID
behavior for valid IDs is retained.

One listing controller owns the page. The legacy renderer/loader is removed;
profile follow controls, observer and back-to-top behavior retain their existing
owners. API/response/render failures use the shared retry state without advancing
count/page or discarding a successfully rendered batch. Bounded windows and
focus/scroll restoration use the same implementation as other collections.

```sh
python3.12 scripts/verify_react_listings.py all --scenario organization --output-dir /tmp/moso-organization-qa
python3.12 scripts/compare_listing_latency.py --scope organization --before BASE --after HEAD --output-dir /tmp/moso-organization-latency
```

The latency harness uses identical synthetic organizations/events with BSON
organizer links in isolated databases. It measures warm sequential loopback GET
responses for the profile and its scoped API, excludes browser/assets/production
capacity and records raw samples plus p50/p95/p99. No organization, moderation,
account or session schema changes are introduced. Rollback reverts this page's
source/template/styles and its tracked generated listing bundle together.
