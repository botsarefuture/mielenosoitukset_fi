# Public performance baseline — 2026-10-07

This note records the reproducible baseline and the first critical-path fixes. It
does not claim to replace real-user monitoring; the browser values below are a
small synthetic sample from Helsinki.

## What users saw before the change

HTTP measurements used 20 sequential requests after three warm-ups. The browser
measurement used seven isolated Chromium mobile contexts, disabled browser cache,
4× CPU slowdown, 100 ms network latency and approximately 1.6 Mbit/s download.

| Page / metric | p50 | p95 | p99 | Sample |
| --- | ---: | ---: | ---: | ---: |
| Front page HTTP total | 90.8 ms | 110.2 ms | 139.9 ms | 20 |
| Demonstration list HTTP total | 71.7 ms | 109.7 ms | 347.0 ms | 20 |
| New demonstration TTFB, cold mobile browser | 57.7 ms | 86.7 ms | 94.7 ms | 7 |
| New demonstration FCP, cold mobile browser | 1,620 ms | 1,636 ms | 1,636 ms | 7 |
| New demonstration LCP, cold mobile browser | 2,136 ms | 2,163 ms | 2,167 ms | 7 |
| New demonstration DOMContentLoaded | 4,391 ms | 4,413 ms | 4,416 ms | 7 |
| New demonstration load event | 5,315 ms | 5,325 ms | 5,328 ms | 7 |

The measured new demonstration was
`/demonstration/6ac685802673bd409050ecb3`, created on the measurement day. The
server-side response was already cached by the time its clean URL was checked,
so query-string cache bypasses were also sampled; they remained below 100 ms.
This isolates the main problem to the browser critical path rather than MongoDB.

## Evidence from the critical path

The page requested 46 resources. Under the throttled mobile profile, the slowest
dependencies included:

- jQuery UI: approximately 4.0 seconds; loaded site-wide despite no active
  `.datepicker()`, autocomplete, sortable or draggable use in public templates;
- Leaflet: approximately 2.3 seconds even though the map is below the fold;
- third-party Bootstrap CSS and JavaScript: approximately 1.5–1.9 seconds;
- a second Font Awesome stylesheet on the demonstration page.

## Implemented first pass

- Removed the unused global jQuery UI CSS and JavaScript.
- Removed duplicate Font Awesome and Google Fonts requests from the front and
  demonstration pages.
- Changed the demonstration map to load Leaflet and tiles only when the map is
  within 400 px of the viewport.
- Mirrored the exact Bootstrap 5.3.0 CSS, bundle and license to
  `cdn2.mielenosoitukset.fi/vendor/bootstrap/5.3.0/` with one-year immutable
  caching and SHA-256 metadata. The upload helper refuses to overwrite a
  versioned object with different content.
- Added a low-impact HTTP percentile probe and admin p50/p95/p99 visibility for
  background jobs and queue depth.

## Verification and next measurements

The same seven-run browser profile was repeated after production deployment of
commit `86466e54eb607dca9e3af1b5bbc936c88555257e` on 2026-10-08. All seven
responses were HTTP 200 with no failed browser requests. A separate browser
smoke test confirmed that Bootstrap loaded from the first-party CDN, Leaflet
was absent before scrolling, and the map initialized after it entered the
viewport with no console errors.

| Cold-mobile metric | Before p50 | After p50 | Change | Before p95 | After p95 | Before p99 | After p99 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| TTFB | 57.7 ms | 61.9 ms | +7.3% | 86.7 ms | 78.1 ms | 94.7 ms | 79.0 ms |
| FCP | 1,620 ms | 1,092 ms | -32.6% | 1,636 ms | 1,235 ms | 1,636 ms | 1,239 ms |
| LCP | 2,136 ms | 1,604 ms | -24.9% | 2,163 ms | 1,710 ms | 2,167 ms | 1,715 ms |
| DOMContentLoaded | 4,391 ms | 1,840 ms | -58.1% | 4,413 ms | 1,960 ms | 4,416 ms | 1,977 ms |
| Load event | 5,315 ms | 3,666 ms | -31.0% | 5,325 ms | 3,692 ms | 5,328 ms | 3,694 ms |

The cold page made 38 requests after the change instead of 46 before it, a
17.4% reduction. The slightly higher median TTFB in this small sample is within
normal network variation; its p95 and p99 both improved, while the targeted
browser rendering milestones improved materially.

The post-deployment HTTP probe used 20 sequential requests after three warm-ups:

| Page | p50 | p95 | p99 | Failures |
| --- | ---: | ---: | ---: | ---: |
| Front page | 62.9 ms | 101.0 ms | 112.1 ms | 0 / 20 |
| Demonstration list | 53.6 ms | 70.6 ms | 72.6 ms | 0 / 20 |
| Measured demonstration | 67.2 ms | 82.6 ms | 91.0 ms | 0 / 20 |
| Health endpoint | 40.7 ms | 46.2 ms | 46.2 ms | 0 / 20 |
| Public status endpoint | 47.5 ms | 89.6 ms | 91.3 ms | 0 / 20 |

The acceptance checks completed as follows:

1. the full CI suite passed;
2. the health endpoint returned `status: ok` and the deployed commit SHA;
3. the front page, list and measured detail page returned HTTP 200;
4. first-party Bootstrap and the lazy map worked in a real browser; and
5. cold-mobile TTFB, FCP, LCP, DOMContentLoaded and load p50/p95/p99 are
   recorded above.

The next performance iteration should add production real-user Core Web Vitals
(LCP, INP, CLS and TTFB) by route family so p75 can be optimized from actual
visitor devices and networks rather than synthetic tests alone.
