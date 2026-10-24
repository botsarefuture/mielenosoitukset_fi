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

## CITY-01b scoped dashboard (branch implementation)

Limited city admins now render a shared review queue at `/admin/dashboard`
instead of redirecting into LIST_DEMOS. Only current city grants for
LIST_DEMOS/VIEW_DEMO/ACCEPT_DEMO contribute readable cities; the query's scope is
applied before counting or sorting. A nonempty city_key wins over a conflicting
legacy city name. No global panic/login/user metrics or submitter fields are
loaded into this surface. Existing global-only dashboard APIs remain forbidden.
An ACCEPT_DEMO-only reviewer can use #962's scoped review entry point; VIEW_DEMO
gets a view link, while LIST-only cannot see an unauthorized decision button.

Twenty records per server page, exact permission-scoped total, ascending deadline
then ObjectId tie-breaker; invalid/explicitly null deadlines sort last. Legacy
absence uses the same configured duration as `city_review_deadline()`, while
explicit malformed/null values never get a fabricated fallback. Counts/rows are
bounded reads with five-second query limits. Reads, browser refresh and ticking
do not reset assigned_at, persist a computed legacy deadline or trigger escalation.

The exact deadline is always a visible `<time datetime>` with Helsinki timezone.
A shared display-only script uses server time plus monotonic elapsed time, once
per minute and on tab visibility, not the browser's wall clock. Countdown text is
aria-hidden so it does not repeatedly interrupt assistive technology; the exact
deadline remains accessible without JavaScript. Expiry says awaiting national
escalation, never that a browser performed the server-side transition. Reload
obtains fresh canonical state; there is no per-row/background API polling.

Five new test definitions/eight cases plus the updated existing scoped-dashboard
case are individually assessed.115 focused cases pass, including real Mongo,
localized FI/EN/SV GETs, deadline ordering/count/page bounds, unchanged assignments,
real Chromium mobile/light and desktop/dark, deliberately wrong client clock and
no-JS contexts. The shared opt-in stacked table keeps deadline and action bounding
boxes inside the mobile viewport; is_visible alone previously missed clipped
columns. CSS cache key is bumped. Generated catalog extension preserves unrelated
old runtime keys/values, including contextual/plural entries; the existing wrong
English Näytä=Users value intentionally becomes View. A full ordinary compile was rejected because
the baseline PO/MO already diverge. Fifteen new source entries per language and
five reused English/Swedish labels are translated. This is not a migration of that catalog debt.
No SMTP, in-app notification, production UI, fleet latency or cross-city
reassignment acceptance is implied.
