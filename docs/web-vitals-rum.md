# First-party real-user Web Vitals

## Purpose

Synthetic checks remain useful for repeatable release comparisons, but they do
not represent the devices and networks visitors actually use. Public pages
therefore collect LCP, INP, CLS and TTFB through the official `web-vitals`
library and expose aggregate p50, p75, p95 and p99 values to administrators.

The implementation follows the upstream reporting lifecycle, including the
fact that INP has no sample when a visitor never interacts with the page:

- <https://github.com/GoogleChrome/web-vitals>
- <https://web.dev/articles/vitals>

## Browser payload and dependency

The browser sends one JSON object per available metric:

```json
{"metric": "LCP", "value": 1604.2}
```

It does not send the library's metric ID or attribution data, the page URL, a
DOM selector, a user or session identifier, or any browser fingerprint. A
metric is sent at most once per metric for each page visit.

`web-vitals` 6.2.2 is served from the versioned first-party path
`cdn2.mielenosoitukset.fi/vendor/web-vitals/6.2.2/`. The JavaScript SHA-256 is
`1e5e9b9af6b8d71cfef508e5a869c53b4cf2bbccad8c9b5ac664c34e93f6151a`.
The object is create-only and has a one-year immutable cache policy. The
application continues normally if this optional dependency or `sendBeacon`
is unavailable.

The public template also pins those exact bytes with Subresource Integrity and
loads the library only outside admin, account, board, and developer surfaces.
The browser therefore rejects a changed CDN response, and sensitive
application surfaces do not add this analytics executable to their existing
script trust boundary.

## Server validation and storage

`POST /api/analytics/vitals` returns a small successful response for accepted
and validation-rejected payloads so malformed analytics cannot break the page.
Requests over the endpoint or shared application rate limits receive HTTP 429
and are not recorded. A sample is stored only when:

- the metric is exactly CLS, INP, LCP or TTFB;
- the value is finite and inside the hard validation ceiling;
- the request has a same-origin referrer that classifies as a public page; and
- the existing coarse user-agent classifier does not identify a bot.

The server derives `page_type` from the referrer and `device` from the existing
desktop/mobile/tablet/other classifier. It deliberately discards the resource
ID, so individual demonstration, organization, city or tag URLs never enter
the Web Vitals collection.

`web_vitals_daily` contains one document per local date, coarse page type,
coarse device type and metric. Each document stores only a count, sum, minimum,
maximum and fixed-bucket histogram. Bucket keys come from a closed server-side
set, keeping document shape and database cardinality bounded even if the public
endpoint receives unusual input. A TTL index removes daily documents after
400 days.

## Percentiles and interpretation

The admin analytics page combines the selected date range and shows percentiles
only after at least ten samples exist for a metric. Percentiles are nearest-rank
upper bounds from fixed histogram buckets, not falsely precise raw-event
calculations. Millisecond metrics use 50 ms buckets through 5 seconds and
250 ms buckets through 10 seconds; CLS uses 0.01 buckets through 1.0.

Use p75 for the standard Core Web Vitals health view and p95/p99 to find tail
problems. Always read the sample count. INP normally has fewer samples because
non-interactive visits do not produce an INP value, and browser support can
also make metric sample sizes differ.

## Operational checks

After deployment:

1. Confirm `/health` reports the deployed commit.
2. Load one public page and confirm the first-party Web Vitals asset succeeds.
3. Interact with the page, hide it, and confirm only allowlisted metric/value
   payloads reach the endpoint.
4. Confirm aggregate documents contain no raw route, resource ID or identifier.
5. After ten or more samples, confirm the admin p50/p75/p95/p99 table renders.
6. Treat a missing optional metric as an observability warning, not a public
   availability incident; use emergency alerting only if the production site
   itself is materially affected.
