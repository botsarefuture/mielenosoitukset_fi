# Public demonstration listing API

`GET /api/demonstrations` replaces the public listing reads currently made to
Flask by the main, city and tag screens. Existing authenticated attendance,
administration and writes remain with Flask. The Go endpoint is public-only:
cookies never change visibility or response data, and no account data is read.

Parameters: `lang=fi|en|sv` (default fi), `page` (default 1), `per_page`
(default 20, maximum 100), `search`, `title`, `city` (up to 20 comma-separated
names), `tag`, `location`, ISO `date_start`/`date_end`, `in_past`,
`include_cancelled`, `parent_id`, `organization_id`, `max_days_till` and the
legacy reserved `recurring` parameter. Text matching is literal, case
insensitive; city and tag match complete values. Search/title/tag inspect the
base content and Finnish, English and Swedish translations. The public React
screen requests 12 rows per page.

The shared strict public visibility predicate is always applied. Cancelled
events are excluded unless requested explicitly or scoped to a parent or
organization. Without `in_past=true`, dates start at the current Helsinki day.
Both explicit date bounds override the default date range, matching Flask;
a single bound combines with it. Parent and organization identifiers accept
only ObjectIds. Sorting is `date`, `start_time`, `_id`, ascending, before
skip/limit. Counts and results use the same filter.

The response is `{page, per_page, total, total_pages, result_start, result_end,
results}`. Results contain only public card fields, localized title/tags,
readable dates, cover URLs, coordinates, identifiers and the public detail URL.
The detail URL always targets the individual occurrence; the detail host redirects
to its selected series occurrence only when the parent is public. Public children
of hidden parents therefore remain independently reachable.
Descriptions, organizer contacts, moderation fields and account state are not
projected or returned. No new collection, index or authentication is introduced.

One count plus one projected bounded find serves a cache miss, inside a
three-second deadline. Queries are limited to 4096 bytes and each text value
to 200 characters. Pagination cannot skip more than 100,000 rows. Invalid,
duplicate or unknown parameters return 400; storage failures return 503.
These limits intentionally reject unbounded legacy requests instead of silently
normalizing them. An out-of-range valid page returns an empty result set.

Only successful public JSON is cached, keyed by normalized parameters,
language and Helsinki day. The process cache is capped at 128 entries and
8 MiB, coalesces simultaneous identical loads and limits concurrent database
loads. Fresh entries live for 30 seconds; a failed refresh may reuse the prior
public response for up to 120 seconds after its load. New failures are never
cached. A successful response advertises `public, max-age=30, s-maxage=30`;
stale fallback responses force revalidation. Errors are `no-store`.
Moderation and edits may consequently remain visible for the declared cache
window, unlike an uncached visibility read. Cookies never create cache variants.

Rollback is route-level: remove the listing GET rules from the React Apache
include to return to the preserved Flask listing shells and APIs.
