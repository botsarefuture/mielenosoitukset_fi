# React month calendar

The standalone host owns GET/HEAD `/calendar/` and
`/calendar/<year>/<month>/`. Explicit month URLs, previous/next month links and
the year-view link keep normal document navigation. Day selection and pagination
use `?day=9&page=2#calendar-agenda`, preserving Back/Forward and reload behavior.
The annual `/calendar/<year>/` view remains in Flask for a later slice.
Years 2000–2100 and months 1–12 are accepted; invalid months return 404.
The default month and today's indicator use Europe/Helsinki. Existing legacy
calendar layout cookies do not select a second layout in the React screen.

## Public API contract

`GET /api/calendar/<year>/<month>` returns
`{year, month, total, days: [{date: "2026-11-09", count: 2}]}`.
Only nonempty days appear, sorted by ISO date, with at most 31 rows.
There is no authentication, privileged override or private field projection.
Invalid month/query values return 400; unavailable database returns 503 with
no-store. Optional `lang=fi|en|sv` is validated but does not change numeric counts.

MongoDB applies the shared public visibility/type predicate, excludes cancelled
events, bounds `date` to the selected month, groups by date and returns counts
only. Invalid calendar dates are discarded. It neither loads every event into
Python nor retrieves event bodies. No new indexes, collections or writes.
Selected-day cards use the existing public listing endpoint with exact start/end
date, `in_past=true`, language and pages of 20. This includes past public events
without truncating a busy month. Images/attendance use the shared card component.

## Caching and failure behavior

The summary has a bounded 24-month, one-minute in-process cache, four concurrent
database reads, singleflight per normalized month and a three-second deadline.
Redis uses the existing source-scoped response cache with a versioned month key;
shared/CDN freshness is five minutes, browser freshness one minute. ETag, Age,
HEAD and 304 use the existing public response layer. Failed reads are not cached.
Moderation changes can take the existing cache windows to appear (up to one
additional minute if a shared miss reuses a warm process entry).
The host caches successful summaries for one minute (24 entries, eight pending
keys, 1.5-second API deadline). It inlines the summary into the document so the
browser paints the grid without another summary request. Day lists use existing
listing caches and are fetched only for the selected nonempty day.
Private header sessions and page HTML are never shared-cache entries.

The head includes a Finnish month title, description, canonical explicit month
URL and CollectionPage metadata. Query variants are noindex/follow. No-JS output
lists populated dates linking to selected-day calendar URLs. An explicit day
URL reads one cached Go listing batch and renders actual event-detail links and
pagination in the no-JavaScript fallback. React reuses that inlined batch without
another browser fetch. The plain month URL still loads only its summary before
the first paint. This preserves discovery without new Flask markup. Global pageview/Matomo
tracking uses the existing standalone application path.

## Rollout

Build with `npm run app:build` and `npm run build`, run the public-host verifier
and focused Go/Mongo tests, and complete independent visual acceptance. The
reviewed Apache include claims only month GET/HEADs, never the annual route or
writes. After approved deployment, activate with the documented
`deploy/release_routing.sh <release-sha>` flow. Its backups and configtest provide
rollback; restoring the previous include returns months to Flask without data
changes. This PR alone does not activate production routing.
