# Go submission intake and Flask delivery

The submission UI moves to the standalone React host. Go owns validation,
idempotency, duplicate warnings and durable storage. Flask retains email
templates, SMTP, secure moderation/cancellation links and city-review assignment.
The existing Facebook importer and image normalization/storage utilities remain
Flask integrations; uploaded images are processed by the delivery worker, never
published as raw uploaded bytes.

## Contract and safety

`POST /api/submissions` consumes the existing multipart form contract. Apache
forwards only same-origin `POST /submit` to it; `/submit/facebook_import` stays
with Flask. Requests require the configured exact public Origin and are never
cacheable. The primary production origin also accepts the site's existing exact
`https://www.mielenosoitukset.fi` alias; custom origins gain no implicit aliases.
Cookies grant no submission privileges. Client moderation, identity,
assignment and arbitrary document fields are ignored. Every new event is
unapproved, not rejected and not cancelled.

Cookie-bearing submissions resolve their actor ID through Flask's existing
read-only `/api/session` over the local Gunicorn socket, with a one-second
deadline and no shared cache. The ID is used only for the private admin case.
Go neither validates nor mints Flask cookies. An unavailable session check fails
closed; anonymous cookieless submissions need no Flask content request.

Bound the request, field sizes, image bytes/dimensions and organizer count.
Validate actual calendar dates, times, email, terms and supported languages.
Reject malformed/duplicate scalar fields. Sanitize rich text with a small
allowlist before storage. Fail closed on database/duplicate-check failures.
Apply shared per-client minute/hour limits using HMAC client keys, trusting
forwarded client addresses only from the loopback Apache proxy.
Limits are five attempts per minute and thirty per hour, including duplicate
confirmation attempts. Bodies are at most 9 MiB, decoded image headers at most
8 MiB/40 megapixels, scalar fields 2,000 bytes (description 100,000), and twenty
organizers. JPEG/PNG/WebP/GIF are supported. Rate records are pruned in bounded
batches after 48 hours. The global database panic switch also stops writes.
Four simultaneous intakes bound upload memory and database pressure; excess
requests receive a retryable 503. Trusted Cloudflare networks are generated from
Flask's existing policy, so visitors are not incorrectly limited by a shared
edge address and client-supplied forwarding headers cannot bypass limits.

Reuse `demo_submission_tokens` and its existing unique token index. Atomically
reserve a fingerprint record with a stable event identifier. Retry/recovery
uses insert-only upserts for the event, private submitter record and notification
job, so retries cannot overwrite moderation or create a second event. The
reservation is durable before those writes; Go recovery resumes interrupted
reservations. Private contact details and bounded pending image bytes stay in
the private token record, not the public event. Remove the pending payload
after delivery preparation. No new collection or index is required.

Keep success JSON, 409 conflict/stale-token responses and 429 retry feedback
compatible with React. Duplicate summaries include public events only. Force
submission bypasses only the duplicate warning, never moderation or rate limits.
The server generates IDs and never accepts a client-selected event identifier.
Completed form tokens retain their original event ID indefinitely; the
twelve-hour fingerprint window applies only to fresh form tokens. Token/event
bindings become durable before the acceptance record is marked completed, and
the Flask worker waits for that marker before preparing mail or removing payloads.

## Delivery and rollout

The existing Flask notification worker prepares Go-created jobs with its
existing trusted templates, magic-link helpers, city assignment and cancellation
workflow. Preparation must be replayable; delivery retains existing claim tokens,
per-message receipts and ambiguous-SMTP quarantine. Go never sends SMTP or holds
SMTP credentials. Submission acceptance does not claim email delivery.

Go writes are disabled unless explicitly configured with the public origin and
a dedicated secret. Prepare the worker first, then Go, then the React host and
exact Apache method/path rule. Verify isolated writes and worker delivery before
activation. Rollback routes GET/POST back to Flask while retaining pending jobs
and the compatible existing collections. No production activation is part of
this implementation task.

Set `GO_SUBMIT_ENABLED: true` only during the approved rollout. The environment
writer derives a separate HMAC key from the existing strong Flask secret and
copies the configured origin, supported content locales and Gunicorn socket
path without printing credentials. The Go service needs `www-data` supplemental
group access to that socket. Startup refuses enabled writes without the existing
unique `demo_submission_tokens.token` index; it does not create indexes.

Pending media preparation failures remain visible as worker errors and retain
their payload for retry/reconciliation. A server-only `submission_delivery_pending`
flag prevents national reminders racing ahead of city assignment. Preparation
clears it only after durable child jobs exist. Failed reservations retain the
same IDs and are retried by Go's bounded recovery loop every minute. Other
worker failures keep the existing five-attempt policy and operator visibility.
