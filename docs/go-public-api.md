# Public Go API: first read-only slice

Owner direction (29 October 2026): start with freely accessible demonstration
information APIs at api.mielenosoitukset.fi, using Go and the existing MongoDB.
The existing detail page will adopt the API in a later slice. No frontend,
Flask authentication, database schema or write ownership changes in this slice.
The initial server is based on the maintainer's `codex/go-mongodb-demonstrations-api`
working tree, not a parallel implementation.

## Contract before implementation

`GET /api/demonstrations/{id}?lang=fi` retrieves one public event by BSON ObjectId.
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
`slug`, `running_number`, `event_type`, `facebook`, `img`, `cover_picture`,
`cover_source`, `preview_image`, `gallery_images`, `organizers`, `default_language`,
`resolved_language`, `available_languages`. Route is a string array, accepting stored arrays and comma-separated/JSON-array legacy strings. Gallery images also support the old `images` field. Optional textual/numeric values
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

Recurring-parent selection, organization enrichment and personalized
follow/attendance state are intentionally not part of this initial contract.
This is not a drop-in replacement for the authenticated Flask API.

Invalid ID/parameters:400; unavailable event:404; database failure:503 with a
bounded generic error. Responses are JSON, no-store and nosniff. No cache initially:
visibility is checked on every request, including conditional/HEAD requests.
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
