# MongoDB performance — `mielenosoitukset.analytics` COLLSCAN investigation

**Status:** investigated, fix implemented on branch `codex/analytics-rollup-aggregation`
(commit `250684b2`), **awaiting merge/deploy**. No index was created — none was justified.

**Scope:** Task #2 of the infrastructure reliability plan (production MongoDB `lc-db`,
`mielenosoitukset`, MongoDB 7.0.37). Read-only evidence gathering only; production was never
modified (no index, config, profiler, data or server changes).

---

## Executive summary

The background job **“Analytics rollup” (`prep`) runs every 15 minutes** and executes
`analytics.find()` — an *unfiltered* query over the whole collection — then counts
1,041,654 documents **in Python**. The admin `demo_analytics` overview page runs the same
query on demand.

Because the query has no filter, sort or projection, there is nothing an index can satisfy:
MongoDB performs a `COLLSCAN` (`keysExamined: 0`). PyMongo drains the cursor in ~16 MB
batches, so each run emits ~6 `getMore` operations, each examining *and* returning ~205,000
documents (16,777,226 bytes/batch at an average 74 B document) — exactly the pattern seen
in the profiler/slow-query evidence.

Measured cost (production slow-query log, ~7 weeks): **3,488 slow operations** against
`analytics` from the app host, `100–1,923 ms` (median 117 ms), ~50–70/day; each job run
moves ~77 MB over the wire and takes **6.4–8.8 s** end to end.

**Fix: count inside MongoDB** with a `$group` aggregation instead of streaming raw events
into Python — measured on production data (read-only `explain("executionStats")`): one
operation, **28,604 rows, ~1.5 MB, 1,103 ms**, no `getMore`s. **No index added:** the
existing `demo_id_1` index already makes every *filtered* analytics query a covered
`IXSCAN` (`docsExamined = 0`, verified), and no index can avoid a full scan for an
unfiltered collection-wide count — even a covered-projection variant was planner-rejected
in favour of `COLLSCAN` (measured).

---

## 1. Current collection state (verified 2026-10-06)

```text
Collection:            mielenosoitukset.analytics
Documents:             1,041,654
Data size:             77,139,666 B (~73.6 MB), storage 31,289,344 B
Average document:      74 B
Age range:             2024-11-17 → 2026-10-06
Write rate:            ~27–31 inserts/day (~357/week) — very low
Indexes (2):
  _id_                 { _id: 1 }                                19,709,952 B
  demo_id_1            { demo_id: 1 } (background: true)          9,105,408 B
Total index size:      28,815,360 B
Related collections:   prepped_analytics 28,604 docs / 1.5 MB
                       d_analytics       28,604 docs / 30.4 MB
```

## 2. Affected application queries

| Location | Operation | Filter | Sort | Result size | Frequency | Problem |
| --- | --- | --- | --- | ---: | --- | --- |
| `utils/analytics.py` `prep()` → `get_demo_views()` (job `prep`, 15 min) | `find()` full docs, iterated in Python | `{}` | none | **1,041,654 docs (~77 MB)** | every 15 min | **Primary offender** — COLLSCAN + ~6×16 MB `getMore` |
| `admin/admin_bp.py` `render_analytics_overview()` (`GET /admin/demo_analytics`) | same `find()` + Python count | `{}` | none | 1,041,654 docs | on admin visit | same query shape |
| `admin/admin_bp.py` `_rollup_demo_analytics_on_demand()` | `find({demo_id}, {timestamp:1})` | `demo_id` | none | ~128 docs | rare | OK — IXSCAN `demo_id_1`, 8 ms |
| `admin/admin_bp.py` `_build_analytics_summary()` (`/admin/stats`, `/admin/api/stats/summary`) | 3× `aggregate` `$match demo_id $in` + `$group` | demo id list | `$sort`+skip/limit | — | admin stats | OK — covered IXSCAN, `docsExamined = 0` |
| `utils/aggregate_analytics.py` `rollup_events()` (separate `run_aggregate.py`, 60 s) | `find({_id: {$gt: last_seen}})` | `_id` range | `_id:1` | new events only | every 60 s | OK — `_id` index, incremental |
| `utils/analytics.py` `log_demo_view()` | `insert_one` | — | — | 1 doc | ~30/day | OK |
| `api/routes.py` `get_prepped_data()` (`/api/v1/demonstrations/<id>/stats`) | `find_one` on `prepped_analytics` | `demo_id` | — | 1 doc | public API | OK (depends on `prep` output, unchanged) |
| `admin/admin_demo_bp.py`, `admin_bp.py` `get_per_demo_anal()` | `d_analytics.find_one({_id})` | `_id` | — | 1 doc | admin pages | OK |

`site_analytics` / `site_analytics_visitors` are separate collections (different feature),
not part of this issue.

## 3. Profiler / slow-query evidence

Profiler configuration (verified, **left untouched**):
`db.getProfilingStatus()` → `{"was": 0, "slowms": 100, "sampleRate": 1}` — profiling is at
level 0, so `system.profile` only holds historical entries (latest 2026-08-20). Current
evidence therefore comes from the mongod log, where ops above `slowms=100` are still written.

Historical `system.profile` entries (`getmore`, `ns: mielenosoitukset.analytics`):

| ts | op | planSummary | keysExamined | docsExamined | nreturned |
| --- | --- | --- | ---: | ---: | ---: |
| 2026-08-20T06:25:01Z | getmore | **COLLSCAN** | 0 | 205,930 | 205,930 |
| 2026-08-20T06:24:52Z | getmore | **COLLSCAN** | 0 | 205,651 | 205,650 |
| 2026-08-20T06:09:57Z | getmore | **COLLSCAN** | 0 | 205,936 | 205,936 |

(pattern repeats every 15 min: :09/:10, :24/:25, :39/:40, :54/:55 …)

mongod slow-query log, app origin (`lc-main`), `analytics` ns, 2026-08-18 → 2026-10-06:

```text
entries:            3,488   (3,343 originatingCommand: {"find":"analytics","filter":{}})
durations:          min 100 ms, median 117 ms, avg 151 ms, max 1,923 ms
per day:            ~50–70
sample:             getMore … planSummary COLLSCAN, keysExamined 0,
                    docsExamined 205,930, nreturned 205,930, nBatches 1,
                    reslen 16,777,226 (16 MB), durationMillis 122
nreturned clusters: 205,650 ×982, 205,930 ×458, 205,936 ×657,
                    205,951 ×633, 205,953 ×613 (sum = 3,343)
```

**Correlation with source:** `background_job_runs` shows `prep` executed at 09:41, 09:56,
10:11, 10:26, 10:41, 10:56 — exactly the 15-minute cadence of the getMore clusters,
durations 6.42–8.78 s. Log entry `2026-10-06T10:26:54` falls inside run
`10:26:47.919 → 10:26:56.700`. Query shape (`find analytics filter {}`,
`queryHash 773D8541`) matches `get_demo_views()` with no `demo_id`.

## 4. Root cause

`prep()` (every 15 min) calls `get_demo_views()`, which executes `analytics.find()` with
no filter/projection/sort and iterates the cursor in Python (`count_per_demo`). With no
predicate nothing an index can satisfy exists, so MongoDB scans all 1,041,654 documents.
PyMongo’s default batching returns 101 docs first, then 16 MB batches ≈ 205,000 docs each —
producing the repeated `getmore` entries with `COLLSCAN`, `keysExamined: 0` and 100–600+ ms
durations. The full ~77 MB result is transferred to the app and counted in Python
(job: 6.4–8.8 s). `render_analytics_overview()` runs the identical query on demand.

Ranked by impact:

1. `prep()` — every 15 min, full scan + 77 MB transfer + Python counting (dominant).
2. `render_analytics_overview()` — same query, admin-on-demand.
3. `prep()`’s `prepped_analytics` drop+re-insert of 28,604 docs (4,385 slow inserts).

## 5. Proposed optimization (implemented)

No index. Server-side counting — new helper in `mielenosoitukset_fi/utils/analytics.py`:

```python
mongo.analytics.aggregate([
    {"$group": {"_id": "$demo_id", "views": {"$sum": 1}}},
    {"$sort": {"_id": 1}},
])
```

* **Why no index:** an unfiltered collection-wide count cannot be made selective; the
  planner even rejects a covered projection (`find({}, {demo_id:1,_id:0})` → `COLLSCAN`,
  `docsExamined 1,041,654`, measured). `demo_id_1` already covers every filtered shape.
* **Why this fix:** the app only ever needed **28,604 counters**, not 1,041,654 documents.
  Counting in MongoDB removes the cursor/`getMore` pattern, the 77 MB transfer and the
  1M-doc Python loop; the `$sort` keeps output deterministic (old order was scan order).
* **Callers benefited:** `prep()` and `render_analytics_overview()` (one helper, both).
* **Alternatives rejected:**
  * New index / covered projection — measured, does not help (see above).
  * Reusing `d_analytics` — **not parity-safe**: its counters sum to 1,930,142 vs
    1,041,654 raw documents (1.85× overcount). Separate investigation needed.
  * Fully incremental rollup (`_id > last_seen`) — the only way to eliminate the scan
    itself; needs idempotency design, recorded as follow-up.
* **Trade-off:** +~0.8 s server CPU per run (1,103 ms vs 286 ms scan-only) in exchange for
  removing ~77 MB transfer and Python work — negligible at 15-min cadence on a ~30
  inserts/day collection.

## 6. Before/after `explain()` (production data, read-only)

| Metric | Before (`find({})`) | After (`aggregate $group`) |
| --- | ---: | ---: |
| Winning plan | **COLLSCAN** | **COLLSCAN** + `$group` |
| Execution time | 286 ms server-side (whole job **6.4–8.8 s**) | **1,103 ms** (single op, log-confirmed) |
| Docs examined | 1,041,654 | 1,041,654 |
| Keys examined | 0 | 0 |
| Returned | 1,041,654 docs (~77 MB, ~6 `getMore`) | **28,604 rows (~1.5 MB, one batch)** |

Supporting explains (unchanged queries, existing index):

| Query | Plan | Keys | Docs | Time |
| --- | --- | ---: | ---: | ---: |
| `find({demo_id}, {timestamp:1})` | IXSCAN `demo_id_1` | 128 | 128 | 8 ms |
| `aggregate($match $in(200 ids), $group)` | covered IXSCAN | 23,988 | **0** | 35 ms |
| `distinct("demo_id")` | DISTINCT_SCAN | 28,604 | **0** | 100 ms |
| `find({}, {demo_id:1,_id:0})` *(index-hopeful)* | **COLLSCAN** (index rejected) | 0 | 1,041,654 | 429 ms |

## 7. Query redesign assessment

**Index is not the correct solution — query redesign is sufficient.**

* The offending query is an unfiltered full-collection count; no index reduces its
  `docsExamined`.
* Every filtered analytics query shape already uses `demo_id_1` as a covered IXSCAN
  (`docsExamined = 0`) — verified for `find`, aggregation `$match $in` and `distinct`.
* The waste was transferring/post-processing raw events; server-side `$group` removes it
  with identical output semantics.
* Residual COLLSCAN inside the aggregation is inherent to recounting raw events;
  eliminating it requires an incremental rollup (follow-up).

## 8. Production deployment recommendation

* **Deploy the code change.** No MongoDB object is created or modified: no index, no
  migration, no config/profiler change, no startup-hook DDL.
* **How:** branch `codex/analytics-rollup-aggregation` (from `origin/main` @ `8ce8f5e8`,
  commit `250684b2`, worktree `../mielenosoitukset_fi-analytics-rollup`) → merge → CI
  (`tests.yml`) → existing `production-deploy` workflow. `main` untouched.
* **Change set:** `utils/analytics.py` (new `count_views_per_demo()`, `prep()` uses it),
  `admin/admin_bp.py` (overview uses the helper), `tests/test_background_jobs.py`
  (asserts exact counts), `CHANGELOG.md`.
* **Risk: low** — read path only; `prepped_analytics` schema and `prep()` output unchanged,
  so `GET /api/v1/demonstrations/<id>/stats` is unaffected. Only behavioural delta: admin
  overview rows now sorted by `demo_id` (was scan order).
* **Rollback:** revert the commit and redeploy; no DB rollback needed.
* **Post-deploy verification:**
  1. `background_job_runs` `prep.duration_seconds` drops from 6.4–8.8 s.
  2. No more `getMore` / `reslen:16777226` log entries for `analytics` from lc-main;
     at most one `aggregate` slow query per 15 min (~1.1 s).
  3. `prepped_analytics.count()` stays 28,604; demo stats API values unchanged.
  4. `prepped_analytics` insert latency unchanged (not touched by this change).
  5. Disk/write latency unaffected (no index change).

## 9. Acceptance criteria

* [x] Exact source query identified (`get_demo_views()` → `analytics.find({})`).
* [x] Profiler/log operation correlated with source code and job cadence.
* [x] Current indexes documented with sizes/settings.
* [x] Query explained with execution statistics (before and proposed-after).
* [x] Root cause established (unfiltered count ⇒ inherent COLLSCAN + 16 MB batching).
* [x] Proposed change tested (production explain + local integration tests).
* [x] Before/after measurements recorded (no manufactured numbers; end-to-end “after”
      job time explicitly pending deploy).
* [x] No speculative indexes added (evidence why none helps).
* [x] Production impact assessed.
* [ ] Production query uses the intended plan — **pending merge/deploy** (§8 steps).
* [x] No unrelated changes introduced (4 files, one concern).

**Tests:** `tests/test_background_jobs.py` + `tests/test_admin_stats_collection.py`
(15 passed), `tests/test_admin_ui_contract.py` (57 passed). Full CI suite (needs
Redis/MailHog/LocalStack) not run locally; repo has no lint config (CI runs pytest only).

---

## Related findings (not fixed here — next performance task)

1. **`d_analytics` double-counting:** counters sum to 1,930,142 vs 1,041,654 raw events
   (1.85×). Blocks any future reuse of `d_analytics` as a source of truth; investigate
   the incremental rollup vs on-demand replace interaction in
   `utils/aggregate_analytics.py` / `_rollup_demo_analytics_on_demand()`.
2. **`demonstrations` is the biggest slow-query source:** 20,724 slow ops in the same log
   window (20,187 IXSCAN, **533 COLLSCAN**; 11,762 `aggregate`, 8,689 `find`) — matches
   the previously reported demonstrations issue.
3. **`prepped_analytics` churn:** `prep()` still `drop()`s + re-inserts 28,604 docs every
   15 min → 4,385 slow inserts (100–430 ms). A bulk-upsert variant would remove this.
4. **Admin overview renders 28,604 rows/labels** into one table and chart — UI/performance
   smell independent of MongoDB.
5. **Long-term:** an incremental rollup keyed on `_id` would remove the residual
   full-collection scan entirely (currently ~1.1 s per run).
