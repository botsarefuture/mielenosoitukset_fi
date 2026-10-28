# Public demonstration RSS

The existing `/demonstrations.rss` route returns RSS 2.0 with at most 50 upcoming
public events, earliest first using the public listing's stable date/time/ID
order. No login is required. The shared `DEMO_FILTER` excludes unapproved,
hidden, rejected and cancelled records, including for signed-in administrators.
Historical data and attempts to override visibility through query parameters
are not supported.

Subscriptions:

- `/demonstrations.rss`: all upcoming public demonstrations.
- `/demonstrations.rss?city=Helsinki`: exact city, case-insensitive.
- `/demonstrations.rss?tag=pride`: exact tag, including translated tags.
- `/demonstrations.rss?city=Helsinki&tag=pride`: both constraints.

Values are literal escaped matches, never user-supplied regular expressions.
The content remains Finnish/source text; no new localization API is introduced.
Listing RSS links follow the page's fixed city/tag scope, rather than transient
search/date filters. Organization and recurring-series list sections do not
advertise an unsupported scoped feed. The public shell advertises the global
feed through RSS autodiscovery. Feed readers may need the URL pasted manually.

The handler performs one projected Mongo read capped at 50 documents. Canonical
series links may check parent visibility, using the existing per-request cache.
It makes no database writes and changes no authentication or schema. Escape
untrusted text for the RSS description's HTML layer and serialize XML with
ElementTree. Use stable per-occurrence GUIDs even when canonical links coincide.
The old permalink GUID format changes once during this migration, so some feed
readers may show the first migrated batch again.

XML is cached for five minutes, partitioned by normalized city/tag, date and
origin, in a versioned namespace separate from the historical unfiltered cache.
Visibility changes may therefore take up to five minutes to appear. Redeploying
or rolling back does not purge readers' already downloaded entries. ETags are
stable hashes of the XML and conditional requests are evaluated separately on
every request, including weak/list/wildcard validators. Do not cache a 304 as
the feed's content. No publication timestamp is invented from the event date.

`tests/test_rss_feed.py` exercises visibility, filters, cap/order, escaping,
canonical links/GUIDs, scope isolation, conditional requests, and listing links.
The visible links additionally require in-conversation visual acceptance under
`.agents/skills/moso-visual-qa/SKILL.md`. Reverting the source and rebuilding
frontend assets restores the old behavior, but restores its visibility defect;
prefer a corrective patch rather than rolling back that security fix.

## Feed usage reporting

Server-side events appear in the existing admin site-analytics Events table:
`rss_fetch` counts successful GETs including cached XML and 304s;
`rss_not_modified` counts conditional 304 checks; `rss_reader_day` estimates
active fetching clients per Helsinki-local day. Summing a date range yields
reader-days, not unique readers across that range or subscribers. The first
two events retain a bounded normalized city/tag resource for existing event
resource reporting. Feed reader/bot user agents are included because automated
polling is the RSS protocol; HEAD, DNT and disabled analytics are excluded.

Estimated reader-days reuse the existing weekly HMAC of trusted client IP, in
a separate RSS namespace, with a cache marker expiring at Helsinki midnight.
No raw IP, user-agent, cookie or account identifier is stored. No new database
collection or index is required, and website pageviews/visitors stay separate.
The visitors-enabled setting controls this estimate. Accurate deduplication
requires a working shared cache; worker-local caches, eviction or outages can
overcount or leave estimates unavailable. An aggregator may represent many
subscribers behind one fetching client; shared IPs merge clients, rotating IPs
split them, and CDN hits never reaching Flask cannot be counted. These numbers
must never be labelled subscriber counts. Analytics failures do not break RSS.
