# Site analytics definitions and campaign links

The server records eligible public GET HTML responses with a successful2xx
status. HEAD, redirects, prefetch, static/API/account/admin traffic and recognized
bot user agents are excluded. User-agent classification cannot identify every
bot or prove that a request represents a person. CDN responses that never reach
Flask are outside these counters.

Pageviews and events share the existing site_analytics collection. Pageview
summaries, daily charts and language/device/referrer breakdowns must explicitly
filter for nonempty page_type. Event records, including searches and RSS polls,
never contribute to those pageview totals. Correcting these read filters also
corrects historical summaries without rewriting stored counters. Historical
HEAD/redirect/prefetch traffic cannot be removed retrospectively because these
aggregate rows do not retain individual request methods or statuses.

Visitor figures remain estimates based on rotating IP/device identifiers,
not counts of people. Shared IPs can merge clients, changing IPs/devices can
split them, and the rotating seven-day identifier can count a client again
within a calendar reporting period. Browser Matomo and server-side measurements
have different coverage; compare the same period/timezone and pageview metric,
not visits or unique visitors. No production reconciliation is claimed without
reading the actual selected-range data.

## Campaign attribution

For example:
`/?mtm_campaign=pride2026&mtm_source=instagram&mtm_medium=social`

The first-party campaign report supports the standard Matomo campaign/keyword
parameters and legacy pk_/piwik_ aliases, plus documented UTM aliases and
Matomo source/medium/content/id/group/placement dimensions. Primary Matomo
parameters take precedence over legacy/UTM aliases. Custom Matomo parameter
configuration is not automatically imported. URL fragments never reach Flask
and are not supported by this server-side report.

Only explicitly named dimensions are stored, with at most100characters per
value. Invalid, control-character, conflicting duplicate or overlong selected
values are rejected rather than merged by truncation. Metadata is held in
aggregate campaign_view event rows, keyed by its deterministic hash in the
existing resource_id field. No new collection/index, cookie, session carryover,
user profile, raw URL or unrelated query string is introduced. Do not put
personal details in campaign names.

These are tagged pageviews: refreshing counts another pageview, not a unique
visit, approved campaign or conversion. Tracking settings and DNT are respected;
storage failures never prevent page delivery or its ordinary pageview count.
Old traffic cannot acquire campaign attribution retrospectively. Campaign
summary errors are displayed separately from a genuine empty report.

Official parameter references:
https://matomo.org/faq/how-to/faq_120/
https://matomo.org/faq/reports/what-is-campaign-tracking-and-why-it-is-important/

Rollback is a source revert; no database migration is required. Reverting the
pageview read-filter fix would reintroduce event inflation and is discouraged.
