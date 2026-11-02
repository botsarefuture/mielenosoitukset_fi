# Public organization profile API

`GET /api/organizations/<id>` replaces the public profile read performed by
Flask's `/organization/<id>` page. The identifier must be a nonzero MongoDB
ObjectId. Invalid or missing identifiers return 404; database failures return
503. Errors are generic and `no-store`. The optional `lang=fi|en|sv` parameter
uses the existing query validation, but stored organization profiles are not
translated. Unknown or duplicate parameters return 400.

The JSON response contains exactly `_id`, `name`, `description`, `email`,
`website`, `logo`, `social_media_links` and `verified`. Text fields are strings,
missing values become empty strings and social links form a string-to-string
map. Website, logo and social links accept HTTP(S) and site-relative URLs;
unsafe schemes, embedded credentials and control characters are omitted.
Descriptions remain plain text as on the existing public template.

The existing organization route exposes profiles regardless of verification.
Verification is a public badge, not an access decision. The Go route therefore
does not invent an approval gate. The database query projects only the eight
public profile fields. Memberships, invitation lists, internal metadata,
permissions and account records are never read or returned. Cookies do not
change the response. Follow state, invitations and authorized actions stay with
Flask's existing session and write handlers.

An uncached read is one indexed `_id` lookup on `organizations`, with a
three-second deadline including queue time. Successful public JSON is cached
for 60 seconds, keyed by ObjectId, with at most 128 entries and 2 MiB total.
Individual entries larger than 64 KiB are returned without entering the cache.
Identical loads are coalesced; at most four database loads and sixteen queued
variants are admitted. A cancelled caller does not cancel another caller's
shared read. Missing organizations and failed reads are never cached, and no
expired value is served on failure.

Successful responses advertise `public, max-age=30, s-maxage=60`; HTML and
session information remain private. Host, API and browser cache windows can add
freshness delay. The endpoint creates no collections, indexes or credentials.
The organization's events use the existing Go listing endpoint with its fixed
`organization_id` scope. Rollback restores the preserved Flask page routing.
