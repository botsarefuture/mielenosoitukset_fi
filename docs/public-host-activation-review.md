# Public host activation review, 1 November 2026

Reviewed main `9ccdd4e34a9277e3da8d43bd4d035245a88947bc` before enabling
the standalone detail and recurring-series pages. The existing home host was
still running `0a10d619`, without the latest home bootstrap/cache work.

The review found and fixed lost Matomo initialization on detail routes,
browser Back retaining a home screen under a detail URL, and session socket
reads losing the proxy client address used by Flask's rate limiter. Production
server reads now use the local Go listener, avoiding an unnecessary CDN hop.
Series parent visibility must reject malformed moderation flags, and explicit
archived/cancelled occurrence links must keep selecting the requested event.

Cache boundaries: public configuration 5 minutes, home bootstrap 30 seconds
(4 entries), detail metadata 60 seconds (500 entries), series 30 seconds
(200 entries). Cookie-bearing sessions and complete HTML are never shared.
The Go home cache coalesces concurrent loads, refreshes after 60 seconds and
permits stale data for up to 15 minutes on failure. Hashed client assets use
one-year immutable caching. API cache headers are set by Go, not Apache.
Cloudflare currently reports DYNAMIC for API JSON, so edge hits are not assumed.

Validation uses the existing app build, `scripts/verify_public_host.mjs`,
focused Go checks and independent real-application visual review. A production
smoke check must verify exact host/API build SHAs, rendered home/detail/series,
cache headers, preserved preview and unmigrated routes, and one cold/warm home
sample. These are rollout checks, not a statistically controlled benchmark.

CodeRabbit CLI authentication was unavailable in this execution environment
(`credentials_unavailable`); no CodeRabbit analysis or pass is claimed.

Rollback: restore the saved Apache include to return detail/series to Flask,
then restore the previous host/API release and environment from the deployment
backup. The approved sparse identifier indexes do not require removal.
