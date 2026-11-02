# Public Go response caching and code map

The homepage and listing response bodies retain their previous contract. The
maintainer subsequently requested longer, shared caching, so cache headers and
the Redis tier intentionally change. City discovery adds a read-only public
route; there are no writes to MongoDB or account/session data in Redis.

## Reading the code

- `home.go`: load recommendation references, read matching public events (or six
  upcoming fallback events), sort recommendations, then build homepage cards.
- `listing.go`: normalize query values, parse pagination/scopes/dates, build
  date/search filters, and read one page. The normalized query struct is also
  the in-process/shared cache identity.
- `event_query.go`: shared scalar date/ObjectId and moderation filter.
- `cards.go`: shared date/image helpers; homepage formatting and recommendation
  ordering. Homepage gallery-first and listing cover-first precedence remain
  deliberately different. Homepage URLs still use ObjectIds; listings still
  prefer valid slugs/running numbers.
- `response_cache_policy.go`: allowlisted routes, canonical keys and TTLs.
- `response_cache.go`: HTTP hit/miss path, bounded buffering, Age and ETag.
- `response_cache_redis.go`: Redis connection, namespace, bounded storage and
  outage backoff. The existing feature caches remain independently readable.

## Freshness policy

| Successful public response | Redis and CDN freshness | Browser freshness |
| --- | --- | --- |
| Homepage | 5 minutes | 60 seconds |
| Demonstration listing, including search/city/tag/organization | 5 minutes | 60 seconds |
| City directory and today listings | 5 minutes, capped at Helsinki midnight | 60 seconds |
| Recurring series | 5 minutes | 60 seconds |
| Demonstration detail | 15 minutes | 60 seconds |
| Organization profile | 1 hour | 60 seconds |

These are response-tier budgets, not a promise of instant publication or an
end-to-end maximum edit delay. The existing in-process caches and React host
bootstrap caches have their own lifetimes and may add to observed delay. On
Redis hits, `Age` reports time since the response was stored so Cloudflare does
not restart that response's entire freshness budget. ETags identify exact JSON
bytes; matching GET/HEAD requests return 304 without a body. A HEAD miss loads
the GET representation but never sends its body.

The old comment saying the homepage "never caches public content" was wrong.
The MongoDB loader checks moderation on its reads; caches reuse that checked
payload. Delayed edits, cancellations and moderation changes are a tradeoff of
long public caching. Urgent removal requires clearing the relevant Redis
namespace **and** purging matching Cloudflare URLs, plus the existing origin
caches; deleting just one tier is insufficient. A deployment does not purge CF.

Health, unknown/private routes, non-read methods, Authorization requests,
errors, cookies set by responses, Vary/private/no-cache responses, malformed
queries, oversized bodies and stale listing failure fallbacks are not shared.
Existing hashed frontend assets already have immutable long-lived caching;
personalized HTML and Flask session/action endpoints remain outside this rule.

## Redis

Set `PUBLIC_REDIS_URL` for a directly run binary. The production environment
writer uses `GO_PUBLIC_REDIS_URL` from Flask config, defaulting to the already
installed local `redis://127.0.0.1:6379/0`. Set it to an empty string to disable
Redis. No installation or global Redis configuration is performed.

Keys are `moso:public-api:v1:<source hash>:<request hash>`, with MongoDB
scheme/host/database identity and no credentials in the source hash. Their identity
includes validated language (default-document language remains distinct from
explicit Finnish), all effective listing filters/page size/page number and
the Helsinki date for homepage/listing/series. Their Redis/CDN/browser lifetime
is capped at the next Helsinki midnight, including DST transitions.
Cookie/account identity is never
stored. Different database namespaces cannot share responses. Unknown
parameters bypass Redis and retain the handler's existing validation error.

Only successful JSON is stored. Each response is at most 256KiB; an atomic Lua
write limits a namespace to 256 responses, evicting the earliest expirations.
Raw bodies total at most 64MiB; base64 envelopes and Redis metadata add overhead.
Every response/index has an expiry. No `FLUSHDB`, global eviction change or
Flask cache key is touched. Redis operations have 100ms deadlines and no
automatic retries. Failures bypass Redis for 30 seconds and use the existing
bounded/coalesced in-process loaders. Cache TTLs are not extended by hits. The
in-process homepage cache also checks the Helsinki day before reuse, so a new
shared-cache miss does not pick up yesterday's upcoming selection.

## Cloudflare activation

JSON is not cached by default. Apply the reviewed rule in
`deploy/cloudflare/public-api-cache-rule.json` to the zone's Cache Rules
ruleset, retaining all unrelated rules. It makes only the public API paths
eligible and respects origin cache headers. It bypasses cookie/Authorization
requests and never includes the main site's HTML, admin, sessions or mutations.
Keep the full query string in Cloudflare's cache key: language, city, tag,
organization, search and pagination must never collapse into one response.
Query-string sorting may improve hit rates if the zone supports it; it is not
required for correctness. Do not override origin TTLs or cache error statuses.

Verify with repeated GETs: correct bodies for different filters/languages,
Cache-Control/Age/ETag/304, `CF-Cache-Status: MISS` then `HIT`, no health/error
cache, and successful origin reads with Redis stopped. API headers alone are
not evidence that the Cloudflare rule is active. This PR does not apply the
zone rule or deploy production. Roll back by disabling the rule and reverting
the Go binary; delete/purge this namespace/API URLs when invalidating data.

References:
- https://developers.cloudflare.com/cache/concepts/default-cache-behavior/
- https://developers.cloudflare.com/cache/how-to/cache-keys/
- https://redis.io/docs/latest/develop/clients/go/connect/
