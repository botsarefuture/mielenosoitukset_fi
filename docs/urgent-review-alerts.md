# Urgent review alerts (CITY-02)

## Current slice: state/message policy, not delivery

`utils/urgent_review_alerts.py` builds an allowlisted message snapshot. It does
not access Telegram, store credentials, enqueue jobs or send messages. The existing
subscription bot/poller remains unchanged. A later scheduled outbox/transport must
use this policy and retain one provider message ID per review lifecycle.

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

## Remaining delivery requirements

Scheduled bounded discovery and reconciliation, durable provider IDs, single-send
claims, per-lifecycle deduplication, retries/429 handling, ambiguous acceptance
reconciliation, same-message edit/terminal-state safety and visible failure
handling are not implemented by this slice. Do not substitute a second incoming
poller or reuse public-read API credentials to expose pending private submissions.
Staging send→edit and verified production routing/configuration remain release
gates. The live bot permission check proves rights, not message delivery.

Protocol reference: [Telegram Bot API](https://core.telegram.org/bots/api).
