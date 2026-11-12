# Submission notification recovery (DATA-04)

Applies only to `demo_notifications_queue` and `process_submit_notifications`.
The separate generic email queue is unchanged. This protocol is not an
exactly-once SMTP guarantee and is not proof of live delivery or CITY-01 completion.

## Automatic handling

- Atomic claims have unique ownership tokens and at most five attempts. Confirmed
  SMTP refusal (connect/authentication/sender/recipient/DATA refusal) retries after
  60, 120, 240 and 480 seconds. The existing five-minute scheduler can run later
  than those deadlines; these are minimum delays, not delivery promises.
- A recorded `delivered_indices` entry prevents that message being sent again.
  Message order/content must not be edited underneath an active job.
- A processing claim older than ten minutes can recover automatically only when
  the current protocol proves no send is in progress. A crash during SMTP or its
  receipt write becomes `delivery_unknown`, not a blind retry. Stale legacy claims
  and legacy errors lack delivery receipts and also require reconciliation.
- Current moderation state is checked before dispatch. Resolved/deleted demos are
  cancelled; city recipients are the intersection of queued addresses, original
  assigned users and current active approval grants. National jobs do not bypass
  a live city assignment. This is a pre-dispatch check, not an atomic SMTP/rights
  transaction or a new assignment/escalation policy.
- Retryable errors and unknown delivery block duplicate national reminders.
  Exhausted errors block reminders for 24 hours after their last update, then
  the normal daily reminder path may create a fresh job. Unknown delivery stays
  blocked until explicitly reconciled.

## Operator checks

Inspect status counts and project only `_id`, `demo_id`, `notification_type`,
`status`, `attempts`, `updated_at`, `next_attempt_at`, `sending_index`,
`delivered_indices` and `messages_sent`. In particular check `delivery_unknown`
and `error` with `attempts >= 5`. Do not export `messages`, recipient addresses,
submitter details or bearer links into logs, issues or screenshots.

For each unknown job, correlate its sending index and delivery time with trusted
SMTP records. Confirm whether the server accepted that exact message. If accepted,
record its delivered index; if definitively refused, leave the index undelivered.
Only after reconciliation may an operator clear `sending_index`, set
`delivery_tracking_version=1` and requeue the job with a bounded attempt budget.
Do not reset an active claim or bulk-requeue unknown jobs. If delivery cannot be
established, keep the unknown state and escalate for a human decision.

Before replaying old payloads, verify the demo/assignment, addresses and action-link
validity; expired links require a fresh authorized notification, not sending the
old bearer URL. Superseded jobs should be explicitly cancelled. Do not mark admin
contact on failed or unknown delivery. The worker updates it after completed mail.

New worker failure metadata contains only exception class names. This does not
retroactively sanitize old queue payloads or the shared EmailSender's existing
SMTP logging. Automated failure dashboards, retention policy and broader external
service recovery remain separate DATA-04 work.

## Validation boundary

`tests/test_submission_notification_recovery.py` exercises real Mongo transitions
with a controlled UTC clock and mocked SMTP. It covers progress, cooldown/attempt
limits, stale claims, unknown outcomes, ownership loss, resolved moderation,
recipient narrowing, failed receipt writes and legacy reconciliation. Existing
background/city assignment tests protect compatibility. No real emails are sent.
