# Urgent review alerts (CITY-02)

## Implementation and release status

`utils/urgent_review_alerts.py` builds an allowlisted message snapshot. It does
not access Telegram, store credentials, enqueue jobs or send messages. The existing
subscription bot/poller remains unchanged. The opt-in scheduled outbox uses this
policy and retains one provider message ID per demo/channel, including reopened
reviews. This implementation is not live-delivery acceptance.

Read-only operational discovery confirmed an existing active Telegram bot service,
the expected bot identity and post/edit administrator rights in the owner-selected
urgent channel. No test message was sent. Keep the numeric route and bot token in
deployment configuration; neither belongs in this module or a public issue.

## Timing and states

- Compare the event's Helsinki-local date/start time as a UTC instant against an
  explicit reference clock. Project naive datetimes mean UTC. Date without a
  valid time does not imply midnight. Nonexistent spring times and ambiguous
  autumn times require correction rather than choosing a DST fold silently.
- New pending events strictly below48h are `urgent`, strictly below24h `critical`.
  Exactly48h is not yet eligible; exactly24h remains in the48h tier. Thresholds
  are positive ordered integer hours; configured labels use those actual values.
  This window is independent of city-review duration, deadline and escalation.
- Do not create fresh alerts for already-started, archived, missing-time or
  already approved/rejected/cancelled records. This avoids historical backlog
  spam. A worker must discover future events as they cross thresholds, not rely
  only on form submission.
- If a message already exists, keep it and edit its state: pending, started,
  rescheduled outside the urgent window, invalid time, archived, approved,
  rejected or cancelled. Archive/start/reschedule are not moderation decisions.
  Cancellation takes precedence over a prior approval. Decision time is shown
  only from matching persisted moderation metadata or `cancelled_at`; never use
  the worker's current time as a fabricated handled time.
- Reopening a review is not a fresh decision merely because stale metadata is
  present. The flags/current canonical state determine the snapshot. A future
  outbox must define review-lifecycle identity and reconcile stale/out-of-order
  edits against the latest persisted state before delivery.
- A valid future start overrides a stale `in_past` flag after rescheduling.
  Terminal snapshots omit responsibility when the decision has cleared its
  assignment: missing historical assignment does not establish national ownership.

## Message privacy and update stability

Messages contain bounded escaped title/city, exact Helsinki start, responsibility,
available review deadline, verified handled time and a fixed canonical
login-protected admin link. They contain no submitter details, description, actor
metadata, edit/approve/reject bearer links or arbitrary document fields. Invalid
IDs cannot produce links. Use Telegram HTML parse mode; do not interpolate raw
fields in another transport formatter.

The link targets `/admin/demo/review/<id>`, requiring authenticated admin access
and `ACCEPT_DEMO` for that specific demonstration. Its content-only review page
does not grant `EDIT_DEMO`, command-center/analytics or submitter access. Decisions
require a session CSRF token and use the existing canonical decision service;
GET never approves or rejects. Existing editor/command-center guards are unchanged.

`text_sha256` changes with actual displayed state/content, not each minute or
worker tick. This supports bounded edits without per-second Telegram traffic.
It is not an idempotency token, a concurrency fence or a delivery receipt.

## Opt-in scheduled delivery

`process_urgent_review_alerts` is registered with the existing scheduler every
two minutes; `URGENT_REVIEW_TELEGRAM_ENABLED` defaults to false and only boolean
true enables work. The service environment supplies `URGENT_REVIEW_TELEGRAM_TOKEN`
and numeric `URGENT_REVIEW_TELEGRAM_CHAT_ID`; neither is serialized into jobs or
review payloads. The target is pinned per record and workers do not claim another
channel's records. No incoming polling, bearer-link generation or public API
credential reuse is involved.

- Discovery reads at most100 projected candidate documents per run, cycling a
  persisted `_id` keyset across the current/following three Helsinki calendar
  dates. Canonical ISO date strings and BSON dates are supported; the shared
  instant policy rejects out-of-window/missing/ambiguous starts. Latency depends on candidate count and
  scheduler health, so verify the sweep duration before release. Database reads
  have a five-second execution bound; inspect date-query index/explain and real
  volume before enabling, rather than claiming a production performance result.
- A unique `_id` per demo/channel makes repeated discovery idempotent. The worker
  atomically claims at most10 due records and reloads canonical content before
  sending/editing. No new alert if approval/reschedule makes it ineligible before
  this read. A valid receipt persists `message_id` and acknowledged text hash;
  unchanged confirmed text does not trigger another request. Deletes replace an
  existing alert with a content-free deleted state, never a new announcement.
- Confirmed receipts become `settled`, outside the send-claim query. A separate
  bounded100-record observation pass detects changed active receipts, so unchanged
  historical messages cannot consume the ten delivery slots. Observe through one
  day after the known start (two days from now if the time is invalid), then keep
  the receipt as non-polling `done`; deleted messages become done immediately.
  Future pending reschedules/reopens discovered in the urgent window can re-arm
  that same retained receipt. Changes to old settled records after the observation
  window are not continuously polled; this is not indefinite historical syncing.
- Rate limits honor `retry_after` plus bounded exponential backoff; at most five
  attempts before `blocked`. Retries re-read current content, not a stale saved
  payload. Confirmed refusal is blocked; unconfirmed first-send acceptance is
  `delivery_unknown`, never blind automatic replay. A ten-minute stale sending
  claim without a receipt is also quarantined. Known-message edits can retry;
  uncertain edits force reconciliation even if current text returns to the last
  acknowledged hash. No transport exception, raw provider body or credential URL
  is stored. Terminal/failed records are not TTL-deleted.
- Unresolved `blocked`/`delivery_unknown` rows keep the existing background job
  visibly in error each enabled run. Operators inspect status, demo/message ID,
  attempt count and fixed error code. They must verify the actual channel before
  adopting a missing receipt or authorizing a new send; clearing an unknown state
  blindly can duplicate a real accepted message. Do not retry a missing/deleted
  provider message by automatically creating a replacement.

## Remaining release gates and limits

Read-only production preflight,2026-10-24: the exact four-date discovery filter
with `_id` sort/100 limit used the existing
`approved_1_date_1_cancelled_1_hide_1_rejected_1` index (IXSCAN, bounded SORT),
examined5 keys/0 documents and completed in1ms, with0 matching candidates in an
estimated59,265-document collection. No indexes/config/data changed or Telegram
messages sent. This verifies an empty-date query plan, not peak-volume sweep
latency, nonempty-batch performance or deployment of this worker.

Focused real-Mongo tests use a fake provider and do not prove Telegram acceptance.
Staging send→edit, monitored sweep latency/index selection and verified production
secret/configuration deployment remain required before enablement. The read-only
live bot permission check proves rights, not delivery. Do not claim absolute
cross-system exactly-once behavior: Telegram has no first-send idempotency key,
and the worker quarantines ambiguous acceptance rather than hiding that limit.
Canonical state can change while an HTTP request is in flight; subsequent
scheduled reconciliation corrects the same message. Arbitrary suspended-worker
or provider reordering is not a fenced distributed transaction.

Protocol reference: [Telegram Bot API](https://core.telegram.org/bots/api).
