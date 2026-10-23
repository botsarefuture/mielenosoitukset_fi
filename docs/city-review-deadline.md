# City review deadline contract (CITY-01a)

New `city_assignment` documents snapshot `review_hours` and naive-UTC
`review_deadline_at = assigned_at + review_hours`. The configured
`CITY_ASSIGNMENT_ESCALATION_HOURS` remains24 by default;48 is supported. This
change does not alter production configuration or migrate existing records.

`city_review_deadline()` is the common reader for subsequent dashboard/in-app
work. Assignment email context and escalation use the same persisted instant.
Changing configuration affects new assignments, not already-snapshotted windows.
Emails display an explicitly labelled absolute UTC time; no browser-local clock
is an authority for escalation.

Legacy assignments without a stored deadline use `assigned_at` plus the current
configured interval. Their original historical configuration cannot be inferred.
Reads do not backfill or reset them. Missing timestamps or malformed/null stored
deadlines do not invent a deadline or silently trigger escalation; they require
operational inspection. No bulk migration is part of this slice.

Ordinary admin content saves no longer reset review time. The existing protected
edit-link-send action retains its explicit `touch_city_assignment()` reset after
successful sending. Reset preserves the stored duration, or snapshots the current
duration for a legacy assignment, and updates start/deadline together. The helper
does not create a new public authorization surface. Old already-sent emails are
historical notices; later explicit actions can reset the authoritative deadline.

The snapshot is review policy, not the event's start time or Telegram urgency
threshold. Dashboard countdown, accessible local-time display, in-app notices,
assignment changes on cross-city moves, current routing verification and urgent
Telegram send/edit remain separate CITY-01/CITY-02 slices. Escalation transport's
provider-acceptance crash window is not solved by this deadline change. DATA-04a
delivery recovery remains a dependency, not a claim of exactly-once SMTP.

Validation uses actual Mongo assignment/submission/edit/escalation paths, a
controlled clock, real email rendering and mocked external effects. No real
messages are sent; production configuration and delivery are not proven by it.
