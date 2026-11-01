# Public Go API: first read-only slice

Owner direction (29 October 2026): start with freely accessible demonstration
information APIs at api.mielenosoitukset.fi, using Go and the existing MongoDB.
The existing detail page will adopt the API in a later slice. No frontend,
Flask authentication, database schema or write ownership changes in this slice.
The initial server is based on the maintainer's `codex/go-mongodb-demonstrations-api`
working tree, not a parallel implementation.

## Contract before implementation

`GET /api/demonstrations/{identifier}?lang=fi` retrieves one public event. The
identifier accepts the existing public forms in the same precedence as the Flask
detail route: BSON ObjectId, then an alias ObjectId, then a running number, then
a slug. Resolution is capped at 200 characters and rejects anything outside
`[A-Za-z0-9-]` as invalid input. A nonpublic original never resolves through one
of its aliases, so an unpublished duplicate cannot be reached by another ID.
Consumer: the planned React detail page and external clients. No token, cookie,
session or privileged override. All origins may read the API; credentialed CORS
is not enabled. `lang` accepts fi/en/sv; omission uses the document default.
Title, description and tags fall back field by field to original content,
matching `utils/demo_localization.py`. Unknown or duplicate parameters are 400.

The database query uses the existing `_id` index in `demonstrations`. It requires
approved=true and hide/rejected absent or exactly false, mirroring DEMO_FILTER's
visibility rules. Cancelled and past public events remain readable as on the
existing detail page. Hidden, rejected, unapproved and missing events all return
404. There is no administrative bypass. Projection and a separately constructed
response both allowlist fields; never serialize a raw BSON document. Nested
organizer and translation metadata are also allowlisted. Hidden private names,
submitter/contact details, moderation, tokens and unknown fields are never
included. The organizer contact extension below permits only explicitly public
organizer email. No joins or geocoding/writes on a read request.

Response fields: `_id`, `title`, `description`, `tags`, `date`, `start_time`,
`end_time`, `city`, `address`, `route`, `latitude`, `longitude`, `cancelled`,
`slug`, `running_number`, `parent`, `event_type`, `facebook`, `img`, `cover_picture`,
`cover_source`, `preview_image`, `gallery_images`, `organizers`, `default_language`,
`resolved_language`, `available_languages`. `parent` is the series identifier of a
recurring occurrence, or null; it lets a host link back to the series without a
second Flask request. Aliases are accepted for lookup but never returned. Route is a string array, accepting stored arrays and comma-separated/JSON-array legacy strings. Gallery images also support the old `images` field. Optional textual/numeric values
are null when absent or malformed; arrays are empty instead of null. Coordinates
accept legacy numeric strings. `cover_source` belongs to each returned event,
so changing a recurring occurrence does not reuse another occurrence's image
policy. Descriptions are content, not a trusted HTML rendering instruction.

The public organizer DTO now contains nullable `name`, `website`, `logo`,
`organization_id` and `email`, plus boolean `is_private`. This extends the
original no-email API contract to support public contacts on the single React
detail view. Email is included only when the stored `show_email_public` value is
exactly boolean true and email is a string. Missing, false, null, numeric, array
or string consent never defaults to true. A computed MongoDB projection removes
unconsented email before decoding; response construction independently enforces
the consent check for raw inputs too. Private organizers without explicit
`show_name_public: true` remain anonymous placeholders: name, website, logo and
organization ID are null. A separately consented public email is the sole
identifying exception for those placeholders. Organization IDs are returned only
for nonprivate entries. No private organizer token, raw contact record or
unknown nested metadata is returned, and there is no organization collection
join or inference of publication consent.

Recurring-parent *content* selection, organization enrichment and personalized
follow/attendance state are intentionally not part of this initial contract.
This is not a drop-in replacement for the authenticated Flask API.

Invalid identifier/parameters:400; unknown or nonpublic event:404; identifier
lookup or database failure:503, both with a bounded generic error. Responses are JSON, no-store and nosniff. Content uses the bounded15minute server cache described below; visibility is
checked on every request, including conditional/HEAD requests.
GET/HEAD/OPTIONS only; no arbitrary queries, list dumps or write methods.
`GET /health` checks MongoDB connectivity with a short deadline.

## Runtime and verification

Run from `go-api/` with Go1.27.3 and the MongoDB Go driver v2.9.2 (MongoDB4.4+; inspected production version7.0.37):

```
MONGODB_URI=mongodb://127.0.0.1:27017 MONGODB_DATABASE=your_database go run .
go test -race ./...
go vet ./...
```

Both MongoDB settings are required: no guessed production database. API_ADDR
is loopback-only by default (127.0.0.1:8080). The maintainer explicitly authorized reuse of the existing production MongoDB
credentials on29October2026. The API implementation performs reads only, but
the credential itself may allow broader operations; do not claim database-enforced
read-only access. A separately scoped principal can be introduced later. One MongoDB
client/pool per process, bounded pool and request/server deadlines. The API
neither migrates nor creates indexes, users, collections or background jobs.
Never put MongoDB credentials in Git, logs or browser code.

Production DNS/TLS/proxy/service configuration must be verified before public
publication. Existing Apache/Gunicorn serves Flask; the checked-in Caddyfile is
development-only. Rollback: stop the independent Go service and remove its API
vhost; existing website and Flask API remain operational. No page switches to
this API in this slice.

Use the existing `scripts/measure_http_latency.py` for p50/p95/p99 with recorded
sample size, environment and errors. A projected JSON read vs full HTML is a
comparison of different workloads, not proof that Go alone accelerated the page.
Record actual measurements before claiming gains; end-to-end page gains remain
unmeasured until integration. Tests must include hidden/rejected/unapproved,
private nested fields, localization, missing/null legacy values, CORS, methods,
timeout/failure and real MongoDB query/projection behavior.


Reproducible isolated comparison (project development services/dependencies):

```
python3.12 scripts/measure_detail_api_latency.py --output-dir /tmp/moso-detail-api-latency --samples 200
```

The script seeds only its own disposable test database, starts the real Flask
fixture and Go service, alternates warm requests and saves percentiles, payload
sizes, cache headers and source hashes. It overrides the historical fixture
cleanup to drop only its own database. Do not present HTML-vs-JSON results as a
Go-only gain or page-rendering improvement. The frontend has not switched yet.

Production setup is documented in deploy/go-api/README.md. Publication requires
verified TLS/vhost/service and public health/data checks. Credentials are reused
only inside the server with a root-owned0600 environment file. No database
data write or existing website routing is changed by API publication.
The local default port8080 is already occupied on the inspected production host;
choose a verified unused loopback port in deployment, not the default blindly.


## Demonstration detail cache

The Go process caches successful projected demonstration documents for15minutes,
keyed by ObjectId. Localization still runs per request, so languages never share
rendered translations. Content edits may take up to15minutes to appear. Each
cache hit performs a lightweight indexed public-visibility check; hidden,
rejected or unapproved events are not served from stale cached content. Database
errors fail closed. Missing records/errors and oversized documents are not cached.

The concurrency-safe process-local cache holds at most1024documents of32KiB each
(approximately32MiB of BSON plus map overhead), pruning expired entries and
otherwise evicting the earliest-expiring entry. Restart clears it; multiple API
processes have independent caches. Health is not cached. HTTP responses retain
no-store, so browser/CDN caching cannot bypass visibility checks. No new database,
indexes, migrations or service dependencies. Disable by restoring the direct
mongoStore construction in main; no stored-data rollback is needed.

## Detail identifier compatibility

Production now carries non-unique, sparse `aliases_1` and `running_number_1`
indexes on `demonstrations`, alongside the existing `slug_1`. Verified on the
live database with `explain`: slug, running number and alias lookups each take
an `IXSCAN` with one document examined (zero for a miss), so resolution does not
scan the collection. These indexes were approved and created separately from the
code change; a deployment that skips them still works but resolves slugs,
running numbers and aliases by collection scan.


Public ObjectIds resolve in one indexed `_id` read. A miss checks whether a
nonpublic original exists before permitting alias fallback; numeric identifiers
try `running_number` before `slug`. Lookups project only `_id` and share the
existing three-second deadline, but a one-document result limit does not bound
how many records MongoDB must examine. Resolution is not cached, so slug or
visibility changes take effect on the next request. Existing public slug URLs
can therefore resolve without a Flask hop.

The cached detail handler performs the same resolution before its cache lookup
and keys the cache by the resolved ObjectId. Two URLs for one event share a
cached response, while a renamed slug or a moderation change is picked up on the
next request because only the body is cached. Invalid identifiers are rejected
before any query; unknown and nonpublic identifiers return 404 with the
not-found cache header.

### Identifier index rollout requirement

A read-only production check on 1 November 2026 found approximately 61,267
demonstrations, an existing `slug_1` index, and no identifier indexes on `aliases`
or `running_number`. `explain` with `queryPlanner` showed exact slug bounds for
slug lookup. Alias/running-number lookup instead used the approved-event index
with broad date/cancelled bounds and post-fetch filtering. This was a plan
inspection only: no full scans were executed and no latency claim is made.

Proposed non-unique indexes, to be approved before a production rollout:

```javascript
db.demonstrations.createIndexes([
  { key: { aliases: 1 }, name: "aliases_1", sparse: true },
  { key: { running_number: 1 }, name: "running_number_1", sparse: true }
]);
```

These do not impose uniqueness or rewrite stored events. Sparse indexes omit
documents lacking the identifier; array aliases use MongoDB's multikey index.
After creation, repeat the same plan check and require identifier equality
bounds on the corresponding index. No production index was created by this
change. Removing just these named indexes reverses the index addition if needed;
review other consumers before doing so.

## Portable home-page data

The React home page can read `GET /api/home?lang=fi` directly, without a Flask
content request. `lang` accepts fi/en/sv and defaults to fi. Unknown, duplicate
or unsupported parameters return 400. This public read needs no session/token;
CORS is uncredentialed and the normal GET/HEAD/OPTIONS, no-store and nosniff
policy applies. No personalized attendance or privileged override is provided.

Response: `{ "events": [...], "recommended": true|false }`. Each card contains
only `_id`, `title`, `date`, `date_display`, `start_time_display`,
`end_time_display`, `city`, `address`, `tags`, `cover_image`, `cancelled` and
`detail_url`. Title/tags use the existing supported-language field fallback.
Missing covers are empty strings. URLs use `/demonstration/<ObjectId>`, which
loads the selected public event directly, including a recurring occurrence.
No descriptions, organizer/contact records, translations object, accounts or
moderation fields cross the projection/response boundary.

Selection reads at most 50 recommendation references, ordered by
`recommend_till` and `_id`, then their matching future approved public events.
Invalid reference IDs are skipped. Recommended events retain their
recommendation order, with event date as fallback. If none remain, read the
first six future public events sorted by date and `_id`. Dates use
Europe/Helsinki. Events require scalar ObjectIds/ISO date strings,
approved exactly true, hidden/rejected absent or exactly false, and not
cancelled. Empty results are successful with an empty events array. This
retains the existing home recommendation precedence with an explicit public
payload/result bound, not a general listing/search API.

MongoDB operations are bounded projected reads of `recommended_demos` and
`demonstrations`, using the existing indexes; no schema, new index, authentication
or write changes. A three-second request deadline bounds database work. Failures
return generic 503, with no query/data details. Public content is not cached by
this endpoint, so moderation visibility is checked for each fetch. No browser or
Flask hop replaces that fresh check.

Deploy the Go binary exposing `/api/home` before enabling direct home requests
on the public frontend. Verify health SHA and a public home response, then
release the frontend. Keep the existing source/HTML fallback until that API
release is available; a pure React host uses the same response contract and
public URL paths. Roll back via the existing atomic Go release switch and
frontend source revert. Endpoint implementation alone is not a production
deployment or evidence of improved response latency.
