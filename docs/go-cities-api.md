# Cities and today discovery API

Purpose: replace Flask's city-directory aggregation and today-page reads while
retaining existing URLs, public visibility and administrative city settings.
The React host owns `/cities`, `/mielenosoitukset-tanaan` and
`/city/<city>/tanaan`; other paths/actions keep their existing handlers.

## Contract

`GET /api/cities` accepts only the existing optional `lang=fi|en|sv` parameter.
It is public, uncredentialed, read-only JSON:

```
{ "day": "2026-11-02", "cities": [
  { "key": "helsinki", "name": "Helsinki", "phrase": "Helsingissä",
    "demo_count": 20, "today_count": 2, "upcoming_count": 5 }
] }
```

The directory includes enabled/default-active cities and cities with visible
events. `demo_count` retains the historical public count; `upcoming_count`
matches the ordinary future listing, excluding cancelled events. Today's count
includes public cancellation notices, matching the existing today pages.
Names/keys/phrases/defaults are generated from the existing Finnish catalog and
Flask constants using `scripts/generate_city_catalog.py`, without importing the
application or introducing a competing municipality list.

MongoDB work: a projected city-settings read and two public, grouped event reads
(all visible dated events and upcoming non-cancelled events). No private
settings/contact/account fields are projected. Existing moderation/type filters
are reused; a three-second deadline bounds loads. No schema/index/write changes.

`GET /api/demonstrations?today=true` extends the existing listing contract. It
locks selection to today's Helsinki date, includes cancellation notices, and
returns an additional `day` field. Date/max-days/in-past parameters cannot widen
that selection. City filters now recognize canonical city keys as well
as the city name, as the former Flask today query did. This also keeps ordinary
city listings consistent with summary counts when legacy city names differ.
Other listing behavior
and response fields stay unchanged.

## Caching and errors

Reuse the shared Redis/CDN response policy: five minutes, capped at the Helsinki
day boundary, with complete filter/page/language keys. A single-entry,
coalesced 60-second directory cache protects MongoDB if Redis is unavailable.
The React host caches public directory data briefly, keyed by API origin/day.
No errors or private header/session data enter those caches. Invalid query 400,
load failure 503/no-store; never represent an unavailable directory as empty.

The initial HTML retains title, description, canonical, social previews,
structured data and no-JS public links. Normal document navigation preserves
the shared header, native Back/Forward and scroll behavior. No Helmet dependency
or public Flask endpoint is introduced. Apache activation is a separately
reviewed GET/HEAD route update; rollback restores its previous include and app
release. Deploy the Go endpoints before the new React host.
