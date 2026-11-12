# Public write APIs: Flask to Go proposal

Status: analytics-event step 1 implemented (shipped dark, not routed) on 11 November 2026 at the
maintainer's request; remaining steps are proposals. No session change,
schema/index migration, email delivery or production activation was performed.

## Scope and evidence

Move the five write families listed under “Move APIs to Go” in `TODO.md:29`.
Preserve MongoDB data, public URLs, React forms and Flask administration.
`AGENTS.md:68` requires incremental React-compatible migration;
`docs/modernization-context.txt:1` is guidance, not an approved specification;
`docs/modernization-assessment.md:100` calls for compatibility and rollback first.

Sections labelled **Verified** describe this checkout, not a production audit.
References are repository-relative `file:line` locations; line numbers refer to
the inspected source. **Proposed** sections are recommendations, and **Approval
questions** are unresolved decisions. No live database, index catalog, proxy,
session secret, SMTP service or performance baseline was inspected. Tests below
were initially read, not executed; their presence is not a claim that they
pass today. For event step 1, focused Go and routing tests, Go vet, TypeScript
checking and the client/SSR builds passed locally. Full socket-based suites
and live MongoDB checks remain blocked by the sandbox; Mongo integration is
opt-in via `TEST_MONGODB_URI`.

Two important corrections to the task inventory:

- **Verified:** demonstration suggestions insert `demo_suggestions` and queue
  mail, but do **not** create a case (`mielenosoitukset_fi/basic_routes.py:3589`).
  Organization suggestions do create one (`mielenosoitukset_fi/basic_routes.py:4234`).
- **Verified:** the email worker consumes rendered messages, **not** template
  names/context (`mielenosoitukset_fi/emailer/EmailJob.py:99`,
  `mielenosoitukset_fi/scripts/process_email_queue.py:72`).

## Shared boundaries

### Verified: Flask, sessions and middleware

- Flask-Limiter, when `ENFORCE_RATELIMIT` is enabled, uses `get_client_ip` and
  Mongo-backed storage. Defaults are 86,400/day, 3,600/hour and 10/second;
  UptimeRobot addresses are exempt (`mielenosoitukset_fi/app.py:110`). Route
  limits retain defaults and become no-ops if no limiter is registered
  (`mielenosoitukset_fi/basic_routes.py:1160`). These are not proof of the live
  limiter configuration or its storage collection/indexes.
- `ProxyFix(x_for=1, x_host=1)` precedes trusted-client-IP extraction;
  Cloudflare client headers are accepted only from a Cloudflare peer
  (`mielenosoitukset_fi/app.py:127`, `mielenosoitukset_fi/utils/request_ip.py:44`).
  Blindly accepting forwarded headers in Go would change both rate limits and
  stored IPs. Existing Go proxy handling is in `go-api/submission_handler.go:49`
  and `go-api/submission_proxy.go:1`.
- The shared public request hook reads `panic` for any active `global` or
  `security` record and returns HTML 503 with `no-store`, `Retry-After: 60` and
  `noindex` (`mielenosoitukset_fi/basic_routes.py:4787`). This can preempt every
  endpoint here, including the nominally always-200 analytics handlers.
- Logged-in identity is loaded from `users._id`, with suspension, `auth_epoch`,
  god-session and password/MFA binding checks (`mielenosoitukset_fi/app.py:179`).
  Do not equate a cookie's user ID with an authenticated user. Anonymous `_id`
  resolves to `None` (`mielenosoitukset_fi/users/models.py:814`). Locale comes
  from session/public-locale selection (`mielenosoitukset_fi/app.py:135`).
  God-session validation can additionally read `mfa_login_challenges`, `mfas`,
  `user_passkeys`, `board_clearances`, `memberships` and `organizations`; those
  authentication reads stay behind Flask, not a replacement Go user-ID check
  (`mielenosoitukset_fi/users/god_auth.py:42`,
  `mielenosoitukset_fi/users/god_auth.py:69`,
  `mielenosoitukset_fi/utils/system_teams.py:61`,
  `mielenosoitukset_fi/utils/system_teams.py:96`).
- Flashes are translated, stored in Flask's session and mark the response as
  carrying feedback (`mielenosoitukset_fi/utils/flashing.py:4`).
  `/get_flash_messages` consumes them once and returns
  `{"messages":[{"category":...,"message":...}]}`, `no-store`, `Vary: Cookie`
  (`mielenosoitukset_fi/basic_routes.py:4311`). Error handlers render HTML for
  400, 429 and 500 (`mielenosoitukset_fi/error_handlers.py:22`,
  `mielenosoitukset_fi/error_handlers.py:117`).
- The inspected handlers/form consumers have no general CSRF middleware contract:
  contact explicitly checks its own token; organization/demo suggestions and
  volunteer signup have no CSRF check in their handlers. See the endpoint
  references below; do not infer protection from browser field validation.
- Successful HTML GETs can cause additional analytics writes through the
  after-request hook; POSTs, HEADs and `/api/*` are excluded from pageviews
  (`mielenosoitukset_fi/app.py:281`,
  `mielenosoitukset_fi/utils/site_analytics.py:293`,
  `mielenosoitukset_fi/utils/site_analytics.py:407`). Template rendering can
  also invoke logged-in shell reads, such as notifications
  (`mielenosoitukset_fi/basic_routes.py:4399`). These are presentation/session
  dependencies, not additional business writes to port into Go intake.

### Verified: email queue and worker contract

`EmailSender.queue_email` renders Jinja HTML with autoescaping before insertion.
These four callers use its non-strict mode: an insert error is logged and retried
by an in-process one-hour timer, up to three attempts; the caller receives no
durable receipt. Template/rendering errors still propagate. Strict acknowledged
mode exists but these callers do not request it
(`mielenosoitukset_fi/emailer/EmailSender.py:42`,
`mielenosoitukset_fi/emailer/EmailSender.py:396`). Consequently, a success response
today is not proof of persisted mail or delivery.

The `email_queue` document is `subject`, `recipients` (array), `body`, `html`,
`sender` (normally null here), `attachments` (empty array), `extra_headers`
(object), `instance_id`, `status: "pending"`, `attempts: 0`, plus Mongo `_id`
(`mielenosoitukset_fi/emailer/EmailJob.py:99`). No queue index creation is defined
in this producer/claimer path; inspect deployed indexes before changing it.

The scheduled drainer binds the active database, claims jobs atomically with
`find_one_and_update`, sends through SMTP, and deletes by `_id` **after** success.
The claim is not filtered by `instance_id`, so a Go-produced job is eligible.
Failure retains the job, marks it `failed`, records `last_error` and
`last_attempt_at`, and upserts an `admin_logs` `email_delivery_failed` record
keyed by `details.job_id`. Retry settings are 30 attempts, 60-second cooldown
and recovery of claims stale for 600 seconds
(`mielenosoitukset_fi/scripts/process_email_queue.py:57`,
`mielenosoitukset_fi/emailer/EmailSender.py:16`,
`mielenosoitukset_fi/emailer/EmailSender.py:97`,
`mielenosoitukset_fi/emailer/EmailSender.py:144`,
`mielenosoitukset_fi/emailer/EmailSender.py:213`). SMTP configuration is resolved
at send time for a null sender (`mielenosoitukset_fi/emailer/EmailSender.py:268`).
Case-message delivery updates require a matching `Message-ID` header; none of
these four ingress callers supplies one, so they do not get that case tracking
(`mielenosoitukset_fi/emailer/EmailSender.py:179`).

### Proposed: common implementation and durability

- Extend the existing Go server; do not create another service, broker or public
  subdomain. Its read handler currently rejects writes and supplies wildcard
  CORS (`go-api/main.go:125`). The outer submission handler already shows how
  to isolate a write route before that read middleware (`go-api/main.go:248`,
  `go-api/submission_handler.go:99`). New writes need their own exact method
  dispatch, same-origin checks and no-store responses, not wildcard write CORS.
- Preserve the panic hook's **any active record** semantics, trusted peer rules,
  configurable kill switch, bounded body reading, bounded in-flight work and
  database deadlines. Do not blindly copy the submission panic query, which
  reads one matching name rather than querying for any `panic: true` record
  (`go-api/submission_handler.go:135`). Authentication stays in Flask unless
  separately approved; no JWT, session-secret copying or browser-supplied actor ID.
- Keep existing business collections, BSON ObjectIds, string IDs where specified,
  UTC BSON dates and admin status fields. Do not replace records on retry:
  moderation may already have changed them. Index additions below require a
  separate reviewed migration and deployed-index check, not request-time DDL.
  Flask's `utcnow()` returns naive UTC for legacy compatibility; Go must encode
  the same instant as a BSON datetime, not local time or a JSON date string
  (`mielenosoitukset_fi/utils/time_utils.py:6`).
- Go should enqueue **fully rendered**, escaped `body`/`html` in `email_queue`
  using the existing job shape, null sender and a producer UUID. Port only the
  four required email templates to Go `html/template`, with golden fixtures for
  escaping, links and Finnish copy. Do not enqueue `{template_name, context}`:
  today's worker cannot render that. Keep Flask's SMTP worker and credentials;
  no new SMTP sender in Go. Email content parity needs review before activation.
- Require acknowledged persistence before claiming acceptance. For the
  multi-write flows, use small endpoint-owned durable reservations with stable
  business/case/mail IDs and a payload fingerprint. The existing insert-only
  reservation pattern does not require replica-set transactions
  (`go-api/submission_store.go:59`, `go-api/submission_store.go:127`); reuse its
  approach, not its demonstration-specific collection/schema. Proposed additive
  reservation fields/collection, expiry and indexes need maintainer approval.
  Retain enough pending state to resume after a crash; never rely on a timer.
- A request key binds to the normalized payload and route. Same key/content
  resumes or returns its previous result; changed content gets 409. Existing
  clients without keys retain separate-submission semantics until their forms
  gain a stable per-attempt key. Content hashes alone must not merge different
  people's submissions. Contact's existing used token still returns 400, not
  a new public idempotency success. Internal recovery must nevertheless finish
  any durable contact work after token consumption.
- A queue ID alone is insufficient durable deduplication: the worker deletes
  successful jobs. Keep the reservation's “mail enqueued” receipt across queue
  deletion. Proposed nontransactional handoff: insert the stable job as `held`
  (excluded by today's claim allowlist), durably record its ID/rendered payload
  in the reservation, then conditionally release `held` to `pending`. Recovery
  resumes release, never recreates a released/deleted job. Do not release before
  the durable receipt; reconcile ambiguous writes before moving stages. This
  additive status/receipt protocol needs approval and crash-boundary tests.
  A crash between SMTP success and deletion can still resend mail. Promise
  at-least-once delivery attempts, **not** exactly-once SMTP. Redact email bodies,
  tokens and raw client IPs from new operational logs.
- Initially keep session-dependent public adapters in their **existing Flask
  handlers**, if needed: validate tokens/identity, retain flash redirects, and
  call Go over an authenticated loopback-only boundary. Go owns persistence;
  Flask must not also insert. This is an intermediate stage, not a claim that
  the public POST has moved. Authenticate the adapter and bind assertions to
  payload, actor and expiry; client headers alone are not assertions. Direct
  public Go routing waits for the session/feedback decisions below. Do not add
  new Flask routes or extend React-island props as a permanent contract.

### Proposed: focused performance checks

No latency improvement is claimed. Measure the existing path and proposed path
with the same synthetic workload and queue configuration:

| Family | Work to bound and measure |
| --- | --- |
| Contact | Body parsing, limiter storage, token insert, queue acknowledgement and optional event upsert; no SMTP on the request path. |
| Organization suggestion | Organization lookup, suggestion insert, largest-case-number read, case upsert and mail enqueue; avoid a growing unindexed max-number scan and coordinate the allocator. |
| Demonstration suggestion | One demonstration lookup, list/Markdown CPU, suggestion insert and mail enqueue; adversarial list/text sizes must not monopolize a worker. |
| Volunteer signup | Publication read, optional Flask identity validation, volunteer insert, optional event upsert and mail enqueue; withdrawal must not wait for a stale publication cache. |
| Confirmation | Token lookup plus conditional update; verify the lookup index and concurrent confirmation behavior, not a collection scan. |
| Beacons | Aggregate upserts only; bounded latency and graceful storage failure, with no queue or synchronous reporting query. |

The operation counts follow the endpoint source references below; additional
shared panic, authentication and rate-limit work is described above. Record
request percentiles, CPU, database time, queue age and rejection/error counts;
set acceptance thresholds from a measured baseline rather than invented targets.

## 1. Contact: `POST /contact`

### Verified

- **Purpose/consumer:** anonymous support intake. Both the old form and standalone
  React `ContactScreen` post a normal URL-encoded form: `csrf_token`, honeypot
  `website`, `name`, `email`, `subject`, `message`. Not a JSON API; Flask reads
  `request.form` (multipart forms also reach that parser)
  (`mielenosoitukset_fi/templates/contact.html:60`,
  `frontend/src/app/ContactScreen.tsx:46`,
  `mielenosoitukset_fi/basic_routes.py:4042`).
- **Token/session:** React SSR calls Flask `/api/session?contact_form=1`, even
  without an incoming cookie, privately rather than through its anonymous
  summary cache. It forwards the returned Set-Cookie; HEAD does not issue a
  form token (`frontend/src/app/render.tsx:272`,
  `frontend/src/app/session-server.ts:54`,
  `frontend/src/app/session-server.ts:87`). The scope returns enabled state,
  limits, flashes and a token, with `no-store`/`Vary: Cookie`
  (`mielenosoitukset_fi/basic_routes.py:1872`).
- **Token validation:** 32 random bytes, URL-safe encoding; token/issued_at in
  signed session `contact_form_tokens`, at most five unexpired entries by
  default. POST removes the matching entry, compares in constant time, requires
  age 2–7,200 seconds inclusive, and atomically inserts SHA-256(token) as `_id`
  in `contact_form_tokens` with UTC `expires_at = consumption time + max_age`.
  Duplicate `_id` rejects restored-cookie replay; `expires_at` has TTL 0.
  This consumes a valid token before honeypot/field validation
  (`mielenosoitukset_fi/basic_routes.py:141`,
  `mielenosoitukset_fi/basic_routes.py:3932`,
  `mielenosoitukset_fi/basic_routes.py:4042`). No login/role permission is required.
- **Limits/normalization:** disabled form short-circuits before token/body work.
  Default body ceiling 16,384 bytes, including streamed-body handling (unknown
  length reaching the bound is rejected). Strip name, subject and message;
  strip and Unicode-casefold email, then validate ASCII email regex. Required:
  nonblank name ≤120 characters, email ≤254, message 10–5,000 characters;
  subject exactly `Tuki`, `Yleinen kysymys`, `Palautetta` or `Muu`. Nonblank
  honeypot gets fake success, no mail/event
  (`mielenosoitukset_fi/basic_routes.py:3928`,
  `mielenosoitukset_fi/basic_routes.py:4010`,
  `mielenosoitukset_fi/utils/validators.py:62`,
  `mielenosoitukset_fi/utils/validators.py:110`).
- **Responses:** 302 to `/contact`, no-store, correlation header
  `X-MF-Request-ID` (32 lowercase hex characters). Success/honeypot flash:
  `success: Yhteydenottopyyntö välitetty onnistuneesti!`; invalid fields:
  `error: Tarkista lomakkeen tiedot ja yritä uudelleen.`; disabled:
  `warning: Yhteydenottolomake on tilapäisesti poissa käytöstä. Voit lähettää sähköpostia tukeen.`
  Bad/early/expired/replayed token is 400, oversized body 413, limiter 429;
  these abort paths do not use the correlated redirect helper. Uncaught token
  storage/template errors can be 500. No success JSON
  (`mielenosoitukset_fi/basic_routes.py:3988`,
  `mielenosoitukset_fi/basic_routes.py:4010`).
- **Database/side effects:** token insert above, then email queue insert:
  `customer_support/new_ticket.html`, subject `Uusi tukipyyntö!`, recipient
  `tuki@mielenosoitukset.fi`, context name/email/subject/message/request_id,
  `extra_headers.X-MF-Request-ID`. Then best-effort `site_analytics`
  `contact_message` counter with request dimensions. There is **no direct case,
  notification, submitter or business audit-log insert** in this handler;
  support mail is not itself a created support case
  (`mielenosoitukset_fi/basic_routes.py:4106`,
  `mielenosoitukset_fi/templates/emails/customer_support/new_ticket.html:54`,
  `mielenosoitukset_fi/utils/site_analytics.py:781`). Shared panic/user/locale
  dependencies and queue delivery failures are described above.
- **Abuse:** per-IP 3/10 minutes and 10/day, global 25/10 minutes and 100/day,
  configurable and applied only to POST, plus default limits, token age,
  single use, honeypot and kill switch
  (`mielenosoitukset_fi/basic_routes.py:3997`).
- **Tests:** `tests/test_contact_security.py:34` covers correlation/normalized
  email; `:63`, `:85`, `:113` missing/replay/restored cookie/concurrent forms;
  `:138`, `:173`, `:193`, `:225` streamed bound/honeypot/validation/disabled;
  `:250`, `:285` IP/global limits; `:336`, `:360`, `:378`, `:390` scoped tokens,
  one-use messages, age/cap/cookies/disabled scope. Host integration assertions
  are in `scripts/verify_public_host.mjs` (contact scope/form checks). Shared
  trusted-IP fixtures are in `tests/test_request_ip.py:6` (socket, trusted and
  spoofed Cloudflare headers, invalid values and pseudo-IPv4/IPv6).

### Proposed

Go route `POST /contact`, same form fields, configurable limits, regex/casefold
semantics, response codes, recipient and queue header. Count Unicode characters,
not UTF-8 bytes, for field limits. Preserve token-consumption order and the
existing `contact_form_tokens` `_id`/TTL shape. Enqueue rendered support mail and
increment the same counter only on real acceptance; never on honeypot success.

Keep Flask token issuance, session verification/removal, flashes and `/api/session`
for the intermediate adapter stage. Make exactly one owner consume the MongoDB
token hash: Go, after receiving the authenticated validation assertion, not both
Flask and Go. Before acceptance, bind that consumption to durable recoverable
mail intent (an approved additive token/reservation record); a crash after hash
insertion must not strand an accepted request without recovery state. Preserve
the public 400 replay behavior rather than asking the browser to reuse its token.
Do **not** route browsers directly to Go
while those checks remain only in Flask. Final cutover requires an approved
token/feedback owner: either a deliberately reviewed narrow session bridge or
Go-owned anonymous form-token issuance with updated React loading and a legacy
token compatibility window. Do not make Go decode/re-sign Flask sessions by
default. Preserve several outstanding tabs and no shared caching of tokens.

Mirror contact IP/global limits across Go processes; transition must not reset
quotas or allow one quota per runtime. Gate direct routing on the approved
token issuer, durable consume-to-enqueue recovery and tested feedback. Rollback
restores POST to Flask, leaves consumed hashes and already queued mail intact,
and retains the issuer needed by forms opened before rollback.

**Compatibility risks:** sessions/Set-Cookie loss, consuming tokens twice across
adapter and Go, validation-error token reuse, Unicode differences, forged proxy
IPs, success before durable enqueue, and duplicate email after an ambiguous write.

**Approval questions:** session/token ownership and compatibility period;
replacement for Flask flashes on the React screen; quota continuity/storage;
durable token-to-mail reservation schema; reviewed email rendering and permission
to test/send real support mail. All session/authentication and real-email changes
need explicit maintainer approval.

## 2. Organization suggestions: `POST /organization/<id>/save_suggestion`

### Verified

- **Purpose/consumer:** propose organization changes for moderation, never edit
  the organization directly. React and Jinja forms URL-encode `name`,
  `description`, `website`, `email`, `logo` and repeated `social_platform[]` /
  `social_url[]` pairs. React uses browser required/URL/email controls, no token
  (`frontend/src/app/OrganizationFillScreen.tsx:56`,
  `mielenosoitukset_fi/templates/organizations/fill_info.html:565`).
- **Authentication/authorization:** public handler, no login, membership,
  permission, CSRF, honeypot or one-time-token check. Uses current user's `_id`
  for case attribution (anonymous yields None), not for authorization. Org
  existence is the only target gate. Invalid ObjectId is uncaught; absent org
  flashes `error: Organisaatiota ei löytynyt.` and redirects 302 to index
  (`mielenosoitukset_fi/basic_routes.py:4180`,
  `mielenosoitukset_fi/users/models.py:835`). React's existing session summary
  supports the page shell; it supplies no write token here. After redirect,
  `OrganizationScreen` fetches flashes only for an authenticated matching
  organization scope with `hasMessages`; it does not currently show this
  feedback for anonymous submitters (`frontend/src/app/OrganizationScreen.tsx:13`,
  `mielenosoitukset_fi/basic_routes.py:1858`). The server flash contract and
  actually displayed feedback are therefore different.
- **Validation:** strip nonblank scalar values; blank means omit, not delete.
  No comparison with original values, required-field check, URL/email validation
  or explicit body/field/list limit in this handler. Zip the two social lists
  (unmatched tails ignored), strip both, omit empty pairs; last duplicate
  platform wins. Empty `fields` still inserts. `email` is simultaneously a
  proposed organization email and the **untrimmed** `meta.submitter_email`, not
  a distinct reporter address (`mielenosoitukset_fi/basic_routes.py:4187`).
- **Database:** read `organizations` by ObjectId `_id`; insert
  `org_edit_suggestions` with ObjectId `_id`, ObjectId `organization_id`, UTC
  `timestamp` and `created_at`, `fields`, `meta:{ip,user_agent,submitter_email}`,
  `status:{state:"pending",updated_at,updated_by:null,notes:null}`,
  `audit_log:[{action:"created",timestamp,user:null}]`
  (`mielenosoitukset_fi/basic_routes.py:4182`). Then `Case.create_new` reads the
  largest `cases.running_num` and upserts a new case by `_id`: `type` is
  `organization_edit_suggestion`, embedded `suggestion` includes inserted `_id`,
  `submitter_id` is current ObjectId/null, `meta:{urgency:"high"}`. Model defaults
  are `demo_id:null`, **top-level `organization_id:null`**, `submitter:null`,
  `error_report:{}`, empty `action_logs`/`case_history`, UTC created/updated dates;
  first running number 100001, otherwise max+1
  (`mielenosoitukset_fi/basic_routes.py:4234`,
  `mielenosoitukset_fi/utils/classes/Case.py:38`,
  `mielenosoitukset_fi/utils/classes/Case.py:87`,
  `mielenosoitukset_fi/utils/classes/Case.py:100`,
  `mielenosoitukset_fi/utils/classes/Case.py:146`). Allocation is a read then
  write, **not atomic** across producers.
- **Indexes/readers:** `_id` lookup; source declares `cases(demo_id,created_at
  desc)`, not a running-number allocator/index here
  (`mielenosoitukset_fi/basic_routes.py:183`). No additional organization-
  suggestion/volunteer indexes were found in the inspected migration files.
  Admin task discovery reads suggestion `status.state`, sorts `created_at`,
  reads organizations and checks `EDIT_ORGANIZATION`; review/apply remain Flask
  (`mielenosoitukset_fi/app.py:439`,
  `mielenosoitukset_fi/admin/admin_org_bp.py:1035`). Deployed index presence and
  uniqueness have not been verified.
- **Side effects/response/errors:** queue
  `admin_org_suggestion_notification.html`, subject
  `Uusi organisaatiotietojen muokkauspyyntö: <org name>`, support recipient,
  context org_name/org_id/fields/review_link/submitted_at/ip/user_agent. The
  absolute review link resolves Flask admin. Success flashes
  `success: Kiitos! Ehdotuksesi on tallennettu ja se tarkistetaan pian 💖`
  and redirects 302 to `/organization/<id>`. No JSON, separate notification,
  ingress analytics event or top-level audit write. Insert/case/template errors
  propagate; partial suggestion/case writes can remain after 500. Non-strict
  queue insertion failure can still produce success. Only shared rate limits
  apply (`mielenosoitukset_fi/basic_routes.py:4229`,
  `mielenosoitukset_fi/templates/emails/admin_org_suggestion_notification.html:7`).
- **Tests:** `tests/test_organization_fill_page.py:1` checks old page fields;
  `:15` posts anonymously and checks stored logo; `:38` checks Flask admin
  application. React host form/action assertions:
  `scripts/verify_public_host.mjs:678`. These do not establish case atomicity,
  mail durability, list bounds, bad-ID behavior or abuse protection.

### Proposed

Go route `POST /organization/{id}/save_suggestion`, retain form encoding,
repeated-field pairing and all existing BSON/status fields. Keep empty/no-op
suggestions initially; changing that is a separate contract decision. Do not
silently repurpose `email` or populate the currently null case organization ID.
Malformed IDs should become a controlled 400, not an internal failure; retain
the existing missing-target redirect/message. Only a trusted Flask adapter may
assert an authenticated submitter during transition. Anonymous intake remains
permitted; moderation permissions remain Flask-owned.

Persist suggestion, case and rendered notification using reserved IDs and
insert-only recovery; never reapply `pending` to a moderated record. Keep
`audit_log` creation embedded as above. **Block multiple case producers until
running-number allocation is coordinated with Flask**; a Go-only counter does
not fix the mixed-writer race. Prefer a shared atomic allocator adopted by both
writers in a separately approved change, with an additive index after data checks.

Proposed abuse baseline for this and demo suggestions: same-origin Origin/
Referer checks, cross-site rejection, ≤64 KiB body, ≤100 list entries,
≤10,000 characters per text field and ≤254 for email, per-IP 3/10 minutes and
10/day plus global 25/10 minutes and 100/day. These are **new proposed limits**,
not today's validation or measured capacity. Confirm against realistic data and
traffic before adopting; malformed/over-limit input gets controlled 400/413/429
without writes. Never fetch a proposed URL server-side. Add format validation
only after deciding compatibility with existing free-text suggestions.

Keep Flask moderation, sessions/actor validation, flashes and redirect adaptation
until equivalent React feedback is approved. Direct POST routing waits for
that decision and safe case numbering. Rollback restores the Flask handler,
keeps new suggestion/case documents readable, and lets queued emails drain once.

**Compatibility risks:** embedded vs top-level organization IDs, conflated email,
duplicate case numbers, a suggestion without its case/mail, lost flash cookies,
new bounds rejecting previously accepted values, and review URLs using the wrong
host. No auto-application to `organizations` is part of this migration.

**Approval questions:** session-bound attribution/feedback; authorization and
CSRF/origin policy; case-number allocator/index migration; proposed limits and
idempotency fields; whether empty suggestions and conflated email should later
change; moderator email parity and any real-email test.

## 3. Demonstration suggestions: `POST /suggest_change/<demo_id>`

### Verified

- **Purpose/consumer:** public correction proposals, moderated later. React posts
  URL-encoded `title`, `date`, `start_time`, `end_time`, `city`, `address`,
  `facebook`, `tags`, `route`, `organizers`, `description_markdown`,
  `reporter_email`, `reporter_comment`. Lists are serialized into form fields;
  organizers are not submitted as a replacement when the prefill is redacted.
  Error feedback is fetched from Flask `/get_flash_messages`
  (`frontend/src/app/SuggestChangeScreen.tsx:11`,
  `frontend/src/app/SuggestChangeScreen.tsx:60`,
  `frontend/src/app/SuggestChangeScreen.tsx:82`). Legacy form fields match
  (`mielenosoitukset_fi/templates/suggest_change.html:564`).
- **Authentication/authorization:** no login, permission, CSRF/token or visibility
  check in the POST handler. It reads `demonstrations._id` directly, unlike the
  public Go detail read's visibility rules. Bad ID **or any lookup exception**
  is treated as not found: flash `error: Mielenosoitusta ei löytynyt.` and 302
  to index (`mielenosoitukset_fi/basic_routes.py:3491`, `go-api/main.go:115`).
  React gets public prefill data, not a write token; GET/HEAD routing is already
  React-only for exact 24-hex paths (`deploy/apache/react-ssr-routing.conf:90`).
- **Validation/normalization:** strip values; case-insensitive `none`/`null`
  becomes blank for candidate fields. Blank does not request deletion. Tags
  split on commas, strip leading `#`/whitespace and drop empty entries, preserving
  order/duplicates. Route accepts stored lists, Python-literal list strings or
  comma/newline text. Organizers parse newline/top-level-comma-separated names,
  `Name (email, website)` and `Name <email>`, compare only name/email/website,
  excluding preserved metadata. Nonempty changed lists/scalars only are stored;
  time comparison treats equivalent `HH:MM`/`HH:MM:SS` as unchanged. Other
  date/time/URL/email values have no format validation or explicit length limit
  (`mielenosoitukset_fi/basic_routes.py:3508`,
  `mielenosoitukset_fi/basic_routes.py:237`,
  `mielenosoitukset_fi/basic_routes.py:311`,
  `mielenosoitukset_fi/basic_routes.py:332`,
  `mielenosoitukset_fi/basic_routes.py:488`,
  `mielenosoitukset_fi/utils/demo_seo.py:99`).
  Organizer text parsing gives newline splitting precedence over comma splitting,
  separates details by comma/semicolon, recognizes website-like tokens before
  email-like tokens and collapses name whitespace. Stored dictionary normalization
  strips visibility flags, stringifies IDs and preserves other metadata for
  comparison; original_values still holds the raw stored value
  (`mielenosoitukset_fi/basic_routes.py:332`,
  `mielenosoitukset_fi/basic_routes.py:397`,
  `mielenosoitukset_fi/basic_routes.py:427`).
- Description is compared first against server HTML-to-Markdown conversion;
  only changed nonblank Markdown is converted to safe HTML and compared again.
  Conversion escapes raw HTML, uses `sane_lists`/`nl2br`, allowlists tags and
  permits only http/https/mailto link schemes. Reporter fields are stripped or
  null; a comment alone is valid. No field changes and no comment flashes
  `error: Kirjoita vähintään yksi kenttämuutos tai kommentti ennen lähettämistä.`
  and redirects 302 back to `request.url`
  (`mielenosoitukset_fi/basic_routes.py:3573`,
  `mielenosoitukset_fi/utils/content_formatting.py:9`,
  `mielenosoitukset_fi/utils/content_formatting.py:31`,
  `mielenosoitukset_fi/utils/content_formatting.py:257`).
- **Database/index:** insert `demo_suggestions` with ObjectId `_id`,
  **string** `demo_id` preserving the path's spelling, `suggested_fields`, raw
  changed `original_values`, reporter_comment/email, UTC created_at, trusted
  ip, user_agent and `status:"new"`. Index `(demo_id asc,created_at desc)`
  (`mielenosoitukset_fi/basic_routes.py:3589`,
  `mielenosoitukset_fi/basic_routes.py:161`). No demonstration update, case,
  notification or audit record at ingress. Flask admin later reviews/applies
  selected fields and updates suggestion status (`mielenosoitukset_fi/admin/admin_demo_bp.py:875`,
  `mielenosoitukset_fi/admin/admin_demo_bp.py:903`,
  `mielenosoitukset_fi/admin/admin_demo_bp.py:951`).
- **Side effects/responses/errors:** after insert, flash
  `success: Ehdotuksesi on vastaanotettu. Kiitos!`, queue
  `admin_suggestion_notification.html`, subject
  `Uusi ehdotus mielenosoitukselle: <title>`, support recipient, context
  `{demo,suggestion_doc}`, then 302 `/demonstration/<demo_id>`. Queue exceptions
  are logged and do not undo acceptance; insert exceptions log and flash
  `error: Palvelinvirhe: ehdotuksen tallentaminen epäonnistui.` then 302 back.
  Pre-insert normalization failures are outside that catch. No JSON, dedicated
  rate limit, honeypot or ingress analytics event
  (`mielenosoitukset_fi/basic_routes.py:3600`,
  `mielenosoitukset_fi/templates/emails/admin_suggestion_notification.html:8`).
- **Tests:** `tests/test_demo_suggestion_public.py:1` exact GET routing;
  `:15` legacy prefill; `:39` route/tags/Markdown persistence; `:74` unchanged
  lossy Markdown; `:115` time equivalence. Host assertions include redacted
  organizer omission and form method/action (`scripts/verify_public_host.mjs:684`).
  Empty-submission localization is covered by
  `tests/test_public_message_localization.py:44`; legacy missing-time form values
  by `tests/test_demonstration_legacy_none_time.py:14`; the detail dialog's
  structured suggestion link by `tests/test_react_demonstration_detail.py:155`.
  Shared Markdown formatting and active-content rejection are covered by
  `tests/test_support_ticket_markdown.py:15` and `tests/test_support_ticket_markdown.py:50`.
  There is no case-creation behavior in these handler tests to preserve.

### Proposed

Go route `POST /suggest_change/{demo_id}`, unchanged form/status/redirect
contract and `demo_suggestions` shape. Preserve string ID spelling initially;
canonicalizing uppercase IDs would change existing admin lookup compatibility.
Port normalization and safe Markdown conversion using shared golden fixtures,
including Python-literal route lists and commas inside organizer display names.
Do not treat client preview HTML as trusted or persist redacted organizer data
as a replacement. No new case creation: that would be a separate feature.

Use the suggestion abuse baseline above after approval, reservation-based
idempotency/recovery and one rendered notification. Keep original_values from
the server read, never client-supplied. Remain proposal-only: no public event
update or cache invalidation is necessary before moderation.

Keep Flask admin apply/reject, sessions and flash adaptation. Decide whether
POST should retain direct lookup or adopt the public Go visibility/alias rules;
do not change that accidentally by reusing `FindPublic`. For direct routing,
provide equivalent React success/error feedback without forging a Flask cookie.
Roll back POST independently of GET/HEAD; leave saved suggestions and pending
mail untouched and recover any incomplete reservations before retiring Go work.

**Compatibility risks:** parser/Markdown differences causing phantom changes,
lossy HTML round trips, metadata loss, blank-as-delete, private-event acceptance
vs public-only rejection, ID casing, new limits and failed-notification retries.

**Approval questions:** target visibility/authorization policy, origin/CSRF and
abuse limits, session/flash replacement, treatment of database outage vs missing
event, and email parity/real sends. Confirm the inventory should say “suggestion
and notification,” not “case,” unless a separate case workflow is desired.

## 4. Volunteers and confirmation

### Verified: `POST /kampanja/api/volunteers`

- **Purpose/request/consumer:** JSON signup consumed by `VolunteerForm`, with
  same-origin credentials, `Content-Type`/Accept JSON, fields name/email/phone/
  city/notes. Browser validation checks required name/email and native validity;
  pending-state/ref protection prevents same-tick double submits only in that
  browser (`frontend/src/components/VolunteerForm.tsx:46`,
  `frontend/src/components/VolunteerForm.tsx:67`,
  `frontend/src/app/campaign-route.ts:16`).
- **Auth/authorization:** read `campaign_settings` `_id:"public_pages"`;
  only boolean `published:true` is public. Missing state/read failure is private.
  While private, any authenticated Flask user may preview/signup; anonymous
  gets 401 `{"success":false,"error":"Kirjaudu sisään nähdäksesi valmisteilla olevan kampanjan."}`.
  Response is private/no-store and varies on Cookie, with noindex/nofollow
  while private. No extra role/permission or CSRF token. The React session
  summary is not a server-side authorization credential
  (`mielenosoitukset_fi/kampanja/routes.py:29`,
  `mielenosoitukset_fi/utils/campaign_publication.py:15`).
- **Validation/limits:** `request.get_json()` is not silent. Non-JSON/malformed
  JSON can raise framework 415/400 before validation. Require dict with string
  name/email, stripped and nonblank, else 400
  `{"success":false,"error":"Nimi ja sähköpostiosoite ovat pakollisia."}`
  (localized). No server email syntax/casefold, duplicate check or explicit
  length/body limits. Optional values default to `""` but otherwise keep even
  non-string JSON values; unknown keys are ignored. Shared rate limits only
  (`mielenosoitukset_fi/kampanja/routes.py:33`).
- **Database/side effects:** insert `volunteers` with ObjectId `_id`, name,
  email, phone, city, notes, `confirmed:false`, random URL-safe 16-byte
  `confirmation_token`, UTC `confirmation_expires = now + 1 day`. No created_at,
  user ID or consent timestamp. Then best-effort `site_analytics`
  `volunteer_signup` with city resource/request dimensions; then queue
  `kampanja/welcome.html`, subject
  `Kiitos ilmoittautumisesta! Vahvista sähköpostisi`, recipient submitted email,
  name and hard-coded `https://mielenosoitukset.fi/kampanja/confirm/<token>`.
  Return 201 `{"success":true}`. No case, separate notification or ingress audit
  record. Storage/template errors propagate after any earlier writes; non-strict
  mail insert failure may still return 201
  (`mielenosoitukset_fi/kampanja/routes.py:49`,
  `mielenosoitukset_fi/templates/emails/kampanja/welcome.html:1`).

### Verified: `GET /kampanja/confirm/<token>`

- Token possession is authority; no login, publication gate or CSRF/session
  token. Read `volunteers` by plaintext confirmation_token; absent gives HTML
  `invalid` 400, expiry strictly before now gives `expired` 400. Otherwise update
  by `_id`: `$set confirmed:true`, `$unset confirmation_token` and
  `confirmation_expires`, then HTML `success` 200. Sequential replay gives 400;
  the read/update is not atomic against simultaneous confirmation. No explicit
  token format/length limit, dedicated throttle, TTL deletion or confirmation
  index is declared in this handler (`mielenosoitukset_fi/kampanja/routes.py:81`).
- The page embeds a React confirmation island and readable fallback, no-store
  and noindex/nofollow; it is not a standalone-host route today. It exposes
  status, not volunteer identity. Missing/malformed stored expiry or DB errors
  are uncaught. No confirmation email, case or audit insert
  (`mielenosoitukset_fi/templates/kampanja/confirm_success.html:1`,
  `frontend/src/pages/ConfirmationPage.tsx:8`,
  `mielenosoitukset_fi/kampanja/routes.py:93`).
- **Privacy risk:** shared HTML analytics can classify this successful GET as
  `page_type:"campaign", resource_id:"confirm/<token>"`, increment
  `site_analytics`, optionally record campaign attribution and a visitor. This
  follows the broad campaign classifier and after-request hook, not an explicit
  confirmation analytics call (`mielenosoitukset_fi/utils/site_analytics.py:390`,
  `mielenosoitukset_fi/utils/site_analytics.py:491`,
  `mielenosoitukset_fi/app.py:281`). Do not replicate token-bearing resource IDs
  in Go. Existing stored data/retention needs a separately approved privacy review.
- **Tests for both:** required/localized/blank values
  `tests/test_campaign_volunteer_feedback.py:48`, `:68`; request outcomes,
  keyboard feedback and double-submit `:139`, `:176`, `:217`; payload/mail/link/
  confirmation `:287`; retry values `:322`. Publication/private/re-publish and
  DB-failure gates `tests/test_campaign_publication.py:35`, `:45`, `:110`;
  private confirmation still works `:142`. Success/invalid/expired/HTML privacy
  headers/replay `tests/test_campaign_page_refresh.py:24`. Tests do not establish
  server-side email validation, rate limiting or concurrent confirmation safety.

### Proposed

Go routes `POST /kampanja/api/volunteers` and `GET /kampanja/confirm/{token}`;
same JSON success/error shapes and volunteer fields. Keep email spelling and
optional-field semantics in compatibility fixtures; approve tightening before
rollout. Proposed safe input envelope: JSON object, ≤16 KiB body, all five fields
strings, name ≤120, email ≤254 with syntax validation, phone ≤64, city ≤200,
notes ≤5,000 characters. Reject unsupported types and malformed bodies without
inserting. These bounds/validation are **not** today's behavior.

Read publication state on signup, fail closed, and preserve authenticated
private preview through the existing Flask adapter until authentication is
approved. Do not trust a public session-summary boolean or fail open on a
cached published flag after withdrawal. Confirmation must work while private.
Add signup IP/global quotas (start with contact's proposed baseline), a
recipient-based resend budget and no automatic repeated welcome email for the
same idempotency key. Email-address deduplication is not implied: today's API
allows multiple signups. Reserve a stable volunteer/token/mail result and queue
rendered welcome mail through the existing worker. Do not count signup analytics
again during recovery.

Confirm with a conditional atomic update matching token **and** unexpired
confirmation_expires; retain expired-vs-invalid 400 distinction using a bounded
read when needed. Preserve existing plaintext tokens through their lifetime
and rollback; a hash-only format is a separate migration. Verify/add a
non-unique confirmation-token lookup index after inspecting duplicates; never
TTL-delete volunteer records merely to expire a link. Apply a per-IP confirmation
budget and path-length bound without rejecting already-issued links; redact
tokens in logs and exclude this path from analytics.

Keep confirmation's HTML response in Flask initially, calling Go's write owner
only through an approved adapter. Final public GET routing needs a standalone
React SSR confirmation screen: the host calls a private Go confirmation action
without publicly caching it and preserves the external 200/400 HTML contract.
Do not return JSON to an email link or build public HTML in Go. Decide HEAD
semantics explicitly: Flask's automatic HEAD currently reaches the GET mutation;
the future host must not accidentally confirm via prefetch/HEAD. Rendering failures
after successful confirmation need a safe, privacy-preserving response policy.

**Compatibility risks:** publication/session bypass, validation tightening,
duplicate signups/mail, city-to-analytics coercion, expiry timezone/boundary,
double-confirm races, link scanners consuming GET tokens, privacy leakage,
HEAD behavior and replacing HTML with JSON. Keep admin volunteer editing,
confirmation/export and campaign publication controls in Flask
(`mielenosoitukset_fi/admin/admin_kampanja_bp.py:111`).

**Rollout/rollback:** migrate signup and confirmation separately if necessary;
Go signups must issue tokens Flask can confirm, and vice versa. Test both
directions and expiry before activating either rule. On rollback restore
Flask signup/confirmation routes, preserve volunteer/token fields, stop duplicate
recovery ownership and let existing queue jobs finish. Do not delete volunteer
rows or invalidate already emailed links.

**Approval questions:** authenticated preview/session validation; CSRF/origin and
rate/resend budgets; email validation vs current acceptance; duplicate signup
policy; reservation/index changes; GET/HEAD/link-scanner semantics; React HTML
confirmation ownership; real welcome-email tests; privacy handling of existing
token-bearing analytics. Authentication, permissions, schema and real email
require explicit maintainer approval.

## 5. Analytics beacons

### Verified: `POST /api/analytics/pageview`

- JSON `{referrer?: string}` only, no other keys. Body is bounded at 1,024 bytes
  using both declared length and a 1,025-byte read. Referrer string ceiling is
  2,048 characters, but the body limit usually wins. Wrong MIME, bad UTF-8/JSON,
  oversized or invalid payload is silently discarded, returning 200
  `{"ok":true}`. Dedicated limit 60/minute plus shared defaults can return 429
  (`mielenosoitukset_fi/basic_routes.py:1303`).
- No login/token/CSRF-session contract. Requires same scheme/netloc Referer,
  optional matching Origin and no cross-site Fetch Metadata. Landing URL is
  derived from Referer, **not** payload. Accepts `/`, `/demonstrations`, `/cities`,
  `/mielenosoitukset-tanaan`, `/submit`, `/city/<one segment>` optionally `/tanaan`,
  `/tag/<one segment>`, `/organization/<24 hex>`. Rejects URL credentials,
  DNT=1, disabled analytics, bots and prefetch; parses at most 32 query fields
  (`mielenosoitukset_fi/utils/site_analytics.py:540`,
  `mielenosoitukset_fi/utils/site_analytics.py:546`,
  `mielenosoitukset_fi/utils/site_analytics.py:293`).
- React sends `document.referrer` once per displayed eligible route after
  activation, skipping DNT/prerendering. **Consumer/server drift:** its route
  list also includes calendar, Pride, information, campaign, fundraising,
  contact, organization-fill, suggest-change and api-docs, which the server
  allowlist above does not accept. Do not claim these views are currently
  persisted (`frontend/src/app/client.tsx:17`).
- **Database writes, no business reads:** `site_analytics.update_one(key,
  {$inc:{count:1}}, upsert:true)` keyed by Helsinki date/hour, page_type,
  optional resource_id (string capped at 200), language, device and coarse
  referrer. Payload referrer is only used for classification, never stored raw
  (`mielenosoitukset_fi/utils/site_analytics.py:511`,
  `mielenosoitukset_fi/utils/site_analytics.py:728`).
- Optional tagged view adds a separate `site_analytics` `campaign_view` event:
  resource_id is SHA-256 of sorted compact UTF-8 campaign JSON; same dimensions,
  count increment and `$setOnInsert:{campaign:...}`. Campaign dimensions are
  name/keyword/source/medium/content/id/group/placement, with exact Matomo,
  legacy and UTM alias precedence; strip values, require name, reject conflicting
  duplicates, control characters and selected values >100 characters
  (`mielenosoitukset_fi/utils/campaign_analytics.py:16`,
  `mielenosoitukset_fi/utils/campaign_analytics.py:31`,
  `mielenosoitukset_fi/utils/campaign_analytics.py:56`).
- Optional visitor upsert in `site_analytics_visitors` by Helsinki date and
  visitor_hash: `$inc pageviews`, `$setOnInsert bucket,expires_at`. Hash is first
  16 hex chars of HMAC-SHA256 with Flask SECRET_KEY over
  `bucket|normalized_ip|lowercase_device`; bucket is Helsinki-local days since
  2020-01-01 divided by seven. Normalize IPv4-mapped IPv6; skip unknown IP or
  missing secret. Expiry is local midnight plus 400 days stored as a BSON date.
  No raw IP, session, cookie or user agent in these documents
  (`mielenosoitukset_fi/utils/site_analytics.py:601`,
  `mielenosoitukset_fi/utils/site_analytics.py:626`,
  `mielenosoitukset_fi/utils/site_analytics.py:649`,
  `mielenosoitukset_fi/utils/site_analytics.py:680`). This secret dependency is
  not permission to share the authentication signing key with Go.
- Counter failure is swallowed; campaign failure does not undo the pageview;
  visitor failure does not undo either. No mail, case, notifications or audit.
  Responses still pass shared panic/rate-limit handling
  (`mielenosoitukset_fi/utils/site_analytics.py:511`).

### Verified: `POST /api/analytics/event`

- JSON or form mapping. JSON parse failure/None falls back to `request.form`.
  String-coerce/strip `event`, accept only map_interaction, external_link,
  demo_search; string-coerce/strip resource_id and cap to 200 characters.
  Unknown keys are ignored; no explicit endpoint body limit. Always 200
  `{"ok":true}` after helper rejection/storage errors, subject to shared
  middleware. No dedicated rate limit or session/CSRF token
  (`mielenosoitukset_fi/basic_routes.py:1289`,
  `mielenosoitukset_fi/utils/site_analytics.py:138`,
  `mielenosoitukset_fi/utils/site_analytics.py:810`).
- Cross-host Referer is rejected; missing Referer is accepted for map/external
  events. Unlike pageview this is a hostname comparison, not full origin.
  demo_search additionally requires resource length ≥2, migrated listing path,
  exact scheme/netloc and no cross-site Fetch Metadata. Bots are skipped.
  **Updated since #1072:** event recording enforces SITE_ANALYTICS_ENABLED and
  DNT server-side, like pageview. Go retains those privacy rules, with an
  explicit default-disabled environment switch for Flask's YAML-only setting
  (`mielenosoitukset_fi/utils/site_analytics.py:781`,
  `mielenosoitukset_fi/utils/site_analytics.py:810`).
- The shared JS sends map interaction once per page load with pathname, external
  clicks with target hostname, via JSON Blob beacons; listings send truncated
  search terms (120 characters). Server does **not** independently validate that
  external_link resource is a hostname. Pride search sends the same event but
  is outside the migrated-listing allowlist
  (`mielenosoitukset_fi/static/js/site_analytics.js:31`,
  `mielenosoitukset_fi/static/js/site_analytics.js:92`,
  `mielenosoitukset_fi/static/js/site_analytics.js:111`,
  `frontend/src/app/ListingScreen.tsx:13`, `frontend/src/app/PrideScreen.tsx:103`).
- Only `site_analytics` event counter upsert, same dimensions/date/hour and
  `$inc count` as above; no visitor/campaign write, mail, case, notification or
  business audit. Locale can depend on Flask session although event identity
  does not (`mielenosoitukset_fi/utils/site_analytics.py:466`,
  `mielenosoitukset_fi/utils/site_analytics.py:763`).

### Verified: indexes and tests

- `site_analytics`: non-unique `site_analytics_date_hour(date,hour)`,
  `site_analytics_resource_date(page_type,resource_id,date)`,
  `site_analytics_top_pages(page_type,date,count desc)`. No unique aggregate-key
  index in this migration: concurrent upserts can create multiple physical rows
  for the same dimensions (`mielenosoitukset_fi/utils/migrations/migration_007_site_analytics.py:10`).
  Visitor indexes: unique `(date,visitor_hash)`, date, TTL expires_at=0
  (`mielenosoitukset_fi/utils/migrations/migration_008_visitor_analytics.py:15`).
- `tests/test_public_app_analytics.py:20`, `:55`, `:63`, `:75`, `:87`, `:103`,
  `:116`: aggregate/visitor shape, origin/DNT/bot/prefetch/payload rejection,
  body/config limits, campaign counts, flags and listing/search eligibility.
  `tests/test_site_analytics.py:555`, `:570`, `:581`, `:594`, `:627`: event
  allowlist, malformed input, foreign referrer, external resources and cap.
  `tests/test_site_analytics_integrity.py:10`, `:27`, `:32`, `:39`: events are
  not pageviews; HEAD/prefetch excluded; visitor failure isolation.
  `tests/test_site_analytics_visitors.py:50`, `:112`, `:317`: hash vectors,
  visitor writes/flags and indexes. `tests/test_campaign_analytics.py:11`,
  `:47`, `:74`, `:82`: aliases, aggregate metadata, exclusions and safe failure.

### Proposed

Retain both exact POST routes and small 200 JSON acknowledgements for discarded
signals/storage failures; do not turn beacons into authenticated APIs. Mirror
existing allowlists, dimensions, Helsinki/DST boundaries and exclusions before
considering route coverage expansion. Keep the pageview 1,024-byte ceiling and
60 requests/minute limit. Propose an event 1,024-byte body bound and 60/minute per-IP limit plus
shared default ceilings; approve the behavior change (including 429) first.
Disabled analytics and DNT are now enforced for **both** Flask routes since
#1072; event step 1 preserves this. Do not add cookies, durable event IDs, raw URL/IP storage
or a queue to this hot path.

Each received signal increments once; repeated browser requests remain repeated
signals. There is no server idempotency key today and no exactly-once counting
promise. Do not dual-write to Flask and Go during comparison. Retain existing
aggregate/visitor collections and index shapes. Test concurrent visitor upserts
and treat duplicate-key races safely; do not automatically retry an ambiguous
`$inc`, which could double-count. A unique aggregate-key index would require
separate consolidation/migration approval, not incidental cutover DDL.

**Block pageview cutover on visitor hash ownership:** reproduce existing hash
vectors without granting Go the Flask signing key by default. A separately
approved dedicated analytics secret can be provisioned to both runtimes before
cutover at a documented salt boundary, with an explicit reporting discontinuity;
otherwise retain visitor hashing in Flask temporarily. Also decide how locale
is derived without decoding the session. Keep Flask dashboards, aggregate
reporting, retention migrations and analytics for remaining Flask HTML pages.
`/api/analytics/track_view`, `/api/analytics/vitals`, Matomo and rollup workers are
outside this proposal and must keep their routing/ownership.

**Performance:** event is one indexed counter upsert; eligible pageview is one
counter plus optional campaign and visitor upserts, not a raw-event scan. Bound
execution and measure p50/p95/p99, timeouts and write errors under concurrent
beacons; establish baseline before claiming Go is faster. Reporting remains
compatible, including existing non-unique aggregate rows. Do not retry/drop
silently without operational counters, but never log payload search terms.

**Compatibility risks:** origin-vs-host mismatch, client/server route drift,
missing-referrer policy, DNT/config inconsistency, locale change, hash-key or DST
differences inflating visitors, duplicate increments and unnecessary raw data.
Deploy event independently; move pageview only when campaign/visitor parity is
proved. Rollback restores only the relevant POST rule; keep aggregate rows and
the agreed hash secret/locale policy, do not replay accepted beacons.

**Approval questions:** whether to fix privacy/origin gaps and route coverage in
the same approved change; locale/session independence; dedicated hash secret
and reporting boundary; event limits; index needs based on deployed catalog and
measurements. Sharing the session secret is an authentication/security change,
even though analytics itself has no login requirement.

## Rollout and rollback gates

### Proposed routing (not an executable deployment change)

The existing file already separates GET/HEAD React routes from POST `/submit`
(`deploy/apache/react-ssr-routing.conf:42`,
`deploy/apache/react-ssr-routing.conf:55`). The following rules illustrate **one
approved family at a time**, before catch-all Flask routing; 8091 follows the
existing submission target, not a verified live listener. Preserve queries and
canonical/trailing-slash behavior; never enable a broad `/api/*` proxy.

```apache
# Activate only after the individual contract and approval gates pass.
RewriteCond %{REQUEST_METHOD} "^POST$"
RewriteRule "^/api/analytics/event$" "http://127.0.0.1:8091/api/analytics/event" [P,L]
RewriteCond %{REQUEST_METHOD} "^POST$"
RewriteRule "^/api/analytics/pageview$" "http://127.0.0.1:8091/api/analytics/pageview" [P,L]
RewriteCond %{REQUEST_METHOD} "^POST$"
RewriteRule "^/suggest_change/([a-fA-F0-9]{24})$" "http://127.0.0.1:8091/suggest_change/$1" [P,L]
RewriteCond %{REQUEST_METHOD} "^POST$"
RewriteRule "^/organization/([a-fA-F0-9]{24})/save_suggestion$" "http://127.0.0.1:8091/organization/$1/save_suggestion" [P,L]
RewriteCond %{REQUEST_METHOD} "^POST$"
RewriteRule "^/kampanja/api/volunteers$" "http://127.0.0.1:8091/kampanja/api/volunteers" [P,L]
RewriteCond %{REQUEST_METHOD} "^POST$"
RewriteRule "^/contact$" "http://127.0.0.1:8091/contact" [P,L]

# Final confirmation stage: HTML belongs to the React host, not the JSON API.
# Token pattern covers today's generated tokens; audit outstanding legacy links.
# HEAD is deliberately not activated until its mutation semantics are approved.
RewriteCond %{REQUEST_METHOD} "^GET$"
RewriteRule "^/kampanja/confirm/([A-Za-z0-9_-]+)$" "http://127.0.0.1:8090/kampanja/confirm/$1" [P,L]
```

The confirmation host-to-Go mutation contract is private and separately approved;
do not expose a public second mutation URL. Keep `/api/session`,
`/get_flash_messages`, authentication, admin and all nonselected methods in Flask.
For intermediate Flask adapters, **do not enable the corresponding rule above**.
Prevent bypass through a directly reachable Go port; enforce both loopback binding
and authenticated internal operations. Avoid Apache error-document/proxy retry
behavior that resubmits a write after a Go timeout.

### Proposed sequence for each family

1. **Expand:** approve the exact contract differences/security decisions; inspect
   representative shapes and deployed indexes without exposing personal data.
   Prepare additive schema/index changes and old-reader fixtures. Configure Go
   credentials with only necessary collection access. Review rollback before
   asking to activate production. No schema deletion or admin rewrite.
2. **Prove offline/staging:** use synthetic data, intercepted SMTP and isolated
   queues. Replay existing request fixtures through Flask and Go and compare
   status, headers, redirects/messages and BSON writes. Compare rendered mail,
   worker claims/retries and Flask admin reads of Go records. Relevant existing
   worker tests include cross-instance draining, retry retention and empty-queue
   idempotence (`tests/test_process_email_queue.py:41`, `:62`, `:89`, `:132`, `:167`).
3. **Prove failure boundaries:** bad/missing/replayed tokens, forged forwarded
   headers, origin/CSRF, shared quotas across processes, disabled/panic state,
   database outage and timeout, unacknowledged inserts, crash after each durable
   write, concurrent same-key/different-payload requests, worker deletion and
   retry. Verify old tokens/new producer and new tokens/old consumer, including
   confirmation expiry and contact forms opened before switching. Do not send
   a live request to both writers; shadow only pure parsing/comparison.
4. **Migrate:** activate one exact method/path rule with explicit maintainer
   deployment approval. Keep Flask code, worker and old schemas runnable. Watch
   accepted/rejected/429/5xx rates, queue depth/age/failed jobs, orphan
   reservations, duplicate cases, confirmation outcomes and aggregate deltas.
   Form deadlines/queue backlogs, not an assumed language speedup, set capacity.
5. **Rollback drill:** disable that family’s new rule, validate Apache config and
   reload; verify the same public URL reaches Flask and GET/HEAD still reaches
   its intended host. Quiesce Go ingress, drain/inspect in-flight reservations
   with one recovery owner, retain records/hashes/mail receipts and let the
   existing email worker drain. A timeout is an unknown outcome, not permission
   to resend. Already committed data is not rolled back or copied back.
6. **Contract later:** only after the compatibility window, pending queues and
   pre-cutover forms/links have been dealt with may unused adapters/legacy code
   be retired in another approved change. New React feedback/confirmation UI
   must pass the repository's visual acceptance then; this document requires
   no UI screenshots and claims no UI SHIP.

## Approval questions to resolve before implementation

1. **Sessions/authentication/permissions — explicit approval:** which approved
   narrow boundary validates contact tokens, authenticated organization actors,
   campaign private preview and locale/flash feedback? Keep Flask ownership
   until answered. No JWT or shared session-key migration is implied.
2. **Security/abuse:** approve proposed bounds, rate/resend budgets, trusted
   proxies, CSRF/origin policy and visibility rules. Decide whether privacy
   fixes (event DNT/disable enforcement and confirmation-token analytics) ship
   as prerequisites. Do not silently preserve or expand the identified gaps.
3. **Data/indexes — explicit approval:** reservation schema/retention, durable
   mail receipts, shared case-number allocator and confirmation lookup index;
   confirm deployed topology/indexes and mixed-version readers. No destructive
   migration, token invalidation or volunteer TTL deletion.
4. **Real email — explicit approval:** exact template parity, sender/config,
   recipient/resend budgets, approved test recipients and permission before
   anything reaches real people. Queued is not delivered; SMTP can duplicate.
5. **Product compatibility:** keep or change empty org suggestions/conflated
   email, demo private-target acceptance, missing-target vs DB-error responses,
   volunteer duplicate policy and GET/HEAD/link-scanner confirmation behavior?
   Confirm demonstration case creation is not part of parity.
6. **Analytics/privacy/security:** choose locale and visitor-hash secret ownership,
   acceptable reporting discontinuity and whether to expand the server route
   allowlist. Do not give Go Flask's signing key merely to preserve a chart.
7. **Operations — explicit activation approval:** establish baseline/thresholds,
   compatibility windows, recovery owner and rollback routing; confirm the
   actual Go listener and Apache proxy behavior before production changes.

## Recommended order: easiest and safest first

1. **Analytics event — DONE (implementation).** Go best-effort counter writer,
   privacy/validation/aggregate-key tests and exact Apache POST rule; Flask
   remains the rollback path. Contract and activation prerequisites are in
   `docs/go-public-api.md`. Existing prefetch behavior and absence of an event
   body cap/rate limit are preserved, not replaced by the proposed tightening.
   Finnish-only locale is retained without sharing Flask signing keys.
   Production activation and live Mongo/Apache checks remain operational work.
2. **Analytics pageview.** Still non-business data and easy routing rollback,
   but only after language, visitor-secret/privacy and campaign/hash fixture
   decisions. Do not bypass those gates to meet this ordering.
3. **Demonstration suggestions.** Isolated moderated collection, no case-number
   allocator or authenticated attribution. More work: normalization/Markdown,
   durable notification and flash compatibility.
4. **Organization suggestions.** Adds linked suggestion/case/mail writes,
   current-user attribution and a mixed-Flask/Go case-number race. Resolve
   coordinated allocation and session feedback first.
5. **Volunteer signup, then confirmation.** Publication/session gate, unsolicited
   recipient mail risk, durable token issuance and existing emailed links make
   this more sensitive. Move signup first while Flask confirms interoperable
   tokens; move confirmation only with its atomic mutation and React HTML plan.
6. **Contact.** Last: signed-session token issuance/consumption, restored-cookie
   replay defense, several concurrent forms, strict shared quotas, honeypot and
   feedback/email coupling. Migrating its database write alone is not completion.

This is a dependency-aware preference, not permission to start implementation.
If visitor-secret approval blocks step 2, step 3 can proceed independently after
its own gates; do not weaken privacy or authentication to keep a numeric order.
