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
