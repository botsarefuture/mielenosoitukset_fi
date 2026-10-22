# Repository roadmap

Last reconciled: 2026-10-22. Verified merge baseline: `main` at `fcb6a295`; PRs #929–#941, #943–#945, #947 and #950 are merged. #941's production evidence remains separately recorded below. Open #942/#946 and draft #951 are not part of this baseline.

This is the delivery plan for the **whole repository**: security, public and admin workflows, backend correctness, operations, privacy, localization, tests, and maintenance. Issue [#833](https://github.com/botsarefuture/mielenosoitukset_fi/issues/833) is one workstream within it. Existing issue trackers retain their detailed acceptance criteria; this document sets the order and dependencies.

An open issue is a candidate for investigation, not proof that its original report remains true. Verify the current code before fixing it. The dates and revision above are planning evidence, not a claim about current production.

## At a glance

- **Security interruption — P1 (2026-10-22):** #951 draft pins certifi2026.10.19 and hash-verified pip for CI/Docker; local project environment updated. Production emergency certifi-only update is separately verified: existing Ubuntu CA already fixed, distro pip uses that patched store, updated application bundle excludes the affected root, graceful reload remains healthy atfcb6a295. #952 tracks the explicit/retry-safe production install contract and package drift; resolve before merging #951. No broader environment or exploitation claim.

- **Next:** Final #942 integration includes #946 and has passing exact-head CI at85481260 (1,486 passed /327 skipped); proper review/normal merge remains pending. OPS-04a/#950 is released, including actual challenge-warning acceptance. Address OPS-04c/#952 before merging the security build-pinning draft #951. Continue ordinary functional/user-visible work after these bounded delivery tasks, not speculative edge-case expansion.
- **Alongside delivery:** QA-01/QA-02 — review security and data/workflow tests individually.
- **Verified release checkpoint:** #941 merged as `e6383141`; final required CI passed 1,370 tests with 325 skips. Public HTTPS and direct Gunicorn health probes both verify that exact running build; pre-existing tracked server overlays are byte-preserved. Automatic deploy run39149112591 remains failed because its public probe hit Cloudflare403; independent runtime verification is not a green-workflow claim. Authenticated production visual acceptance is not claimed.
- **Then:** reliable public listings, accessible forms/modals, and shared UI.
- **Ongoing:** operational continuity, privacy/audit planning, localization and maintenance.
- **Tracking:** stable task IDs below; detailed implementation lives in linked issues/PRs. Tests have their own [review inventory](docs/test-review-inventory.md).

## Priority policy

P0–P3 are common engineering conventions. The definitions below are this repository's policy; they are not a universal standard. **Priority decides urgency; severity describes impact.** A security label or an old issue title alone does not prove P0.

| Priority | Meaning | Scheduling rule | Examples |
|---|---|---|---|
| **P0 — Critical** | Confirmed active compromise, production outage, ongoing data loss, or an exposed critical authorization failure. | Interrupt planned work; contain the incident immediately, then verify recovery. | Live exploitation, unavailable core service, active destructive data corruption. |
| **P1 — High** | Verified security gap, broken core workflow, material data-integrity risk, or accessibility failure preventing a core action. | Next delivery cycle; resolve before expanding the affected feature. | Authentication lifecycle flaw, unreliable pagination, inaccessible essential modal. |
| **P2 — Medium** | Important usability, consistency, performance or maintainability improvement with a working core path. | Schedule after related P1 work and required dependencies. | Component consolidation, broader localization, measured performance improvements. |
| **P3 — Low** | Optional enhancement or low-risk cleanup without immediate user harm. | Pull when higher-priority dependencies are clear. | Verified orphan assets, optional new product features. |

Priorities below are planning assignments. Revalidate reported defects before implementation; promote a confirmed urgent defect to P0 and record the evidence. SEC-03 confirmed P0 code defects in case reads (#917), cross-organization authorization (merged #918) and direct user-role saving (#919). Neither live exploitation nor fresh production verification is claimed.

Owner direction, 2026-10-19: prioritize ordinary functional workflows and concrete user-visible failures before speculative/hard-to-reach edge cases. Preserve critical security safeguards and focused regressions; defer broader concurrency/crash matrices until the core workflow works. Do not expand a narrow fix into an unnecessary framework or an unbounded review loop.

## Status and ownership

| Status | Meaning / required evidence |
|---|---|
| **Backlog** | Captured, but current behavior/scope or dependencies still need verification. |
| **Ready** | Current issue verified; scope, owner, acceptance criteria, dependencies and validation defined. |
| **In progress** | An assigned owner is implementing or reviewing the task. |
| **In review** | PR/artifact exists and awaits review; not yet merged. |
| **Blocked** | Cannot proceed; name the blocker, responsible decision/dependency and next action. |
| **Merged** | Target branch contains the accepted change. |
| **Released** | Deployed change verified with build/runtime evidence. |
| **Closed** | Acceptance criteria satisfied; required merge/release evidence linked. Documentation/review tasks can close without deployment. |

All backlog owners are **unassigned** until a contributor takes the task. Do not invent names or delivery dates. Before starting, record an accountable owner and a target milestone; milestones below express sequence, not calendar promises.

Use one task record: **ID · priority · status · owner · milestone · issue/PR · dependencies · acceptance criteria · validation evidence**. Keep status in the ledger below and the detailed issue synchronized. Grouped roadmap entries are work packages: split them into small child issues/PRs with their own records before implementation.

## How to choose the next task

1. Fetch current main, inspect the relevant PR and issue, and read the applicable PMC notes. Preserve unrelated local changes using a clean isolated checkout.
2. Select the first unblocked item in the next queue below. Record its ID, intended result, dependencies, focused validation, and current status here before starting.
3. Finish one reviewable batch before opening another in the same workstream. Independent work may proceed while a PR awaits human review; record that explicitly.
4. Use shared product components and existing Flask/Jinja/Bootstrap contracts. Preserve permission enforcement, payloads, routes, token scope, and fresh per-deletion reauthentication from #887. Preserve the incident containment/hardening merged in #912/#913.
5. Every behavioral or visual batch includes CHANGELOG, applicable CSS cache version changes, focused validation, and PR evidence. Documentation-only batches need document validation, not a full application suite.
6. After creating a PR, continue the next unblocked item. Merge/deploy requires authorization for that action. Mark implementation merged only after verifying main contains it; mark released only with deployment evidence.
7. Change the order for a confirmed incident or higher-impact defect, documenting the reason. Do not start speculative rewrites or infrastructure changes merely because a task is blocked.

## Next delivery queue

| Milestone | Priority | IDs | Deliverable | Acceptance criteria |
|---|---|---|---|---|
| **M1 — Secure core workflows** | P1 | SEC-01, QA-01 | Repair MFA lifecycle; review authentication/permission evidence. | Server-held opaque proof, atomic consume, reset revocation, expiry and bounded attempts; meaningful replay/concurrency/negative-path tests; #887/#912/#913 protections retained. Verify #763/#778 before scheduling fixes. |
| **M2 — Reliable discovery and accessible actions** | P1 | DATA-01, UI-01 | Stable list pagination/result counts; accessible search/cropper. | Date/time/ID ordering, no page-boundary duplicates/gaps, correct ranges/totals, filter reset/URL state across list/city/tag; safe DOM, labels, keyboard/focus/Escape, both themes and mobile. |
| **M3 — Operational correctness** | P1 | DATA-02, OPS-01 | Verify worker coordination and backup/alert gaps. | #908 investigated against merged code; overlap/retry/crash evidence; current recovery/alert evidence and explicit next actions in the continuity plan. Live changes follow its dependencies. |
| **M4 — Consistent product UI** | P2 | UI-02, FORM-01, UI-03 | Shared homepage/city, organization/submission, detail/error/status components. | Preserved requests/permissions/drafts/imports/SEO/preferences; shared geometry/tokens/states, localized copy, keyboard/mobile/light-dark acceptance and relevant performance checks. |
| **M5 — Localization and maintainability** | P2/P3 | I18N-01, CLEAN-01, CLEAN-02 | Complete route-family translations and remove verified styling/dead-code debt. | Actual FI/EN/SV translations; reference audit before deletion; legacy calendar decision; smaller inline baseline and valid shipping variables/cache keys. |
| **M6 — Acceptance** | P1 gate | ACCEPT-01, QA-01–QA-05 | Reconcile all delivered work with original requirements and test reviews. | Individual reviews complete, required CI and representative browser checks pass, trackers reflect actual merge/release evidence. Outstanding repository work remains visible. |

Inspected main `175cb1fd` contains #901, #915, #918, #917, #916/#919 and the public #920–#924 stack. #921/#924 were merged; intermediate #922/#923 were closed only after their commits were verified in main. Merge does not establish release acceptance; retain #900 recurring discovery behavior.

Test review runs alongside each milestone. Operations and privacy planning may proceed independently when their dependencies and ownership are clear. A confirmed P0/P1 failure takes precedence over the milestone sequence.

## Workstreams and remaining backlog

### Security and permissions

- **QA-01g · P1 · In review · Codex · M1/M6 · #945 / codex/passkey-challenge-lifecycle · depends on #943:** Three individually reviewed definitions /ten cases verify server expiry at299/300/301 seconds, purpose binding independently of user/session binding, and two real concurrent counterless assertions against the same challenge. All71 combined cases pass; targeted predicate mutations cause nine intended failures while retaining the valid299s control. Authentication/#887 policy unchanged; clock and synchronization wrappers delegate actual crypto verification and Mongo writes. Inventory exact; no hardware, replica-set or distinct-challenge counter-concurrency claim.

- **QA-01f · P1 · Merged · Codex · M1/M6 · #943 / codex/passkey-boundary-test-review:** Four individually reviewed definitions add six cases for forged elevated cross-user rename/delete, signed origin/RP mismatch and consumed assertion/session binding. Actual crypto verification and disposable MongoDB, positive controls and exact credential/session assertions; all61 combined focused cases pass. Six targeted in-process boundary mutations each produce the intended HTTP200-versus-denial failure. Required CI and exact-head review passed before normal merge `9a86b4ce`. Authentication policy and #887 are unchanged. Broader physical-device/browser acceptance and concurrent counter updates remain separate; this batch does not close QA-01.

- **QA-01a · P1 · Merged · Codex · M1/M6 · codex/step-up-test-review:** Individually assess all eleven step-up test definitions; repair vacuous original-session logout coverage and strengthen configured time boundaries, actor/session isolation, invalid credential rejection and stored password outcomes. Acceptance: focused step-up and fresh-deletion regressions pass (30 cases), mutation confirms logout cleanup regression detection, fixture/mock limits and remaining cases recorded. No production authentication or #887 policy changes.

- [ ] **SEC-01 · P1:** #901 MFA challenge implementation is merged; preserve the shared legacy/no-JS behavior and obtain required release acceptance evidence.
- [ ] **SEC-02 · P1:** Inactive/banned-account enforcement and admin status workflows are merged through #915/#916/#919, including shared target checks and atomic duplicate-submit coverage; #763 is closed. #931 supplies runtime translation coverage; broader release acceptance remains separate from issue closure.
- [ ] **SEC-03 · P0/P1:** #918 target-organization/input validation and #917 case scope are merged; #919 user-action hierarchy/delegation, global clearance scope and audit searchability are merged through the account-management integration. Broader role lifecycle, concurrency, destructive-action and canonical audit requirements remain tracked.
- [ ] **SEC-04 · P1:** Reconcile token/approval lifecycle requirements and prior completed trackers against current routes; prove revocation, expiry, replay behavior, idempotent decisions, case closure, audit and notification effects for every entrypoint.
  - **SEC-04a/b · P1 · Merged · Codex · M1/M6 · #935/#938–#940:** Individual lifecycle and decision tests, bounded conditional case reconciliation, and content-save preservation are included in the #940 integration. Generic MCP patches reject approval changes before any write; they do not invent a new moderation transition. Rollback authorization/state restoration, stale content edits racing decisions, provider-acceptance crash windows, and unknown-field retention remain open.
- [ ] **SEC-05 · P1:** Review incident #912/#913 protections and credential/session lifecycle regressions before touching related code. Keep secrets out of documentation and audit data.

### Backend, data, jobs and integrations

- [ ] **CITY-01 · P2 · Backlog · Unassigned · M2/M4:** Complete the existing city-admin submission notification and review-deadline experience; do not build a parallel assignment system.
  - **Delivery dependency — DATA-04:** notification acceptance requires recovering failed `error` jobs and abandoned `processing` jobs with bounded retries/idempotency and visible failure handling. Current `process_submission_notifications.run()` claims only `pending`/unset status and records send failures as `error`; the existing code must not be credited with retry recovery it does not perform. Complete/verify this DATA-04 slice before CITY-01 delivery acceptance.
  - **Verified starting point (2026-10-19, main `e6383141`):** `utils/city_assignment.py` assigns new submissions to active, non-banned city admins with live `ACCEPT_DEMO` grants; `basic_routes.py` queues their email instead of the national notification. `scripts/escalate_city_assignments.py` escalates overdue pending submissions to the national team. The demo list renders responsibility/escalation badges; the admin overview counts assigned and escalated items. These code observations do not prove production email delivery or scheduler health.
  - **Deadline contract:** use one server-authoritative deadline for notification copy, dashboard and escalation job, derived from the existing `CITY_ASSIGNMENT_ESCALATION_HOURS` setting (**24h code default**, not an assumed48h; deployed value is unverified). If48h is desired, explicitly change and test policy/configuration together, rather than hardcoding a different UI timer. Decide and document whether existing assignments retain their original duration after configuration changes. Current `touch_city_assignment()` resets `assigned_at` on edits: explicitly review which meaningful actions may extend the window; reads, reloads and unrelated edits must not accidentally defer processing indefinitely.
  - **Notifications and scope:** verify submission→queued notification→delivery for all eligible admins of the submitted city, including scoped/legacy grants, duplicate memberships, revoked/disabled/missing-email recipients and failures/retries. Preserve national fallback when no eligible city admin exists and national escalation after the configured interval. Add an in-app notification/deep link using the existing notification mechanism as well as the existing email; expose only authorized demo details and audit notification failures without secrets. Verify deduplication and decision-versus-escalation races; no duplicate announcements or revived queues after approval/rejection/cancellation.
  - **Dashboard UX:** show authorized pending assignments in the shared admin dashboard with demo, city, responsibility, localized exact deadline and remaining hours/minutes (e.g. “23 h 15 min jäljellä”), ordered by nearest deadline. Link directly to review. Distinguish awaiting city review, deadline passed/awaiting escalation, escalated, and resolved; do not imply browser countdown completion performed the server action. Use server time/UTC storage, accessible `<time>`/non-color status, a no-JS absolute-deadline fallback, low-frequency updates and no per-row polling or per-second screen-reader announcements. Preserve identical light/dark/mobile components and permission-scoped counts.
  - **Acceptance / tests:** actual submission route plus queue worker and escalation integration; zero/one/multiple eligible admins, configured24h/48h, just-before/exact/after expiry, allowed reset actions, empty/resolved queues, retry/concurrent sweep and decision races. Clock-controlled tests must compare the same deadline across email, dashboard and job. Add focused responsive/theme/keyboard tests and individually assess new and touched definitions in `docs/test-review-inventory.md`; captured enqueue/send calls are not proof of SMTP delivery. Dependencies: existing assignment/notification worker, scoped admin queries and shared dashboard; promote a verified security/delivery failure to P1 under the priority policy.

- [ ] **CITY-02 · P1 · Backlog · Unassigned · M2:** Urgent pending-demonstration alerts to the Telegram channel **“Mielenosoitukset.fi kiireelliset admin jutut”**, using **@mielenosoituksetbot**, as requested by the owner.
  - **Trigger:** evaluate time until the event starts, independently of CITY-01's review/escalation interval. Proposed explicit policy: pending events starting in less than48h produce an urgent alert; less than24h is a higher-urgency state on the same message. Verify/configure thresholds before release; do not wait24h for city escalation when an event starts sooner. Evaluate on submission, start-time changes and scheduled threshold crossings so an initially distant event is not missed. Include city-assigned and national-fallback pending submissions; approved/rejected/cancelled events must not create fresh review alerts. Define already-started and missing/invalid-time handling explicitly; never invent a start instant.
  - **One maintained message:** retain demo ID plus Telegram chat/message IDs and delivery/state metadata, not raw bearer links. Create one alert per pending review lifecycle and **edit that same message** when urgency/responsibility changes or processing resolves it: approved, rejected, cancelled or escalated, with handled time and a clear status. Use canonical persisted decisions, not browser clicks or an ordinary content save, as the resolution source. Define reopened-review behavior explicitly. Guard stale retries from overwriting a newer resolved state; do not post a new message for every tick or edit.
  - **Safe delivery:** verify the channel's numeric chat ID and the bot's send/edit permissions before enabling; channel display name/bot username alone are not sufficient routing configuration. Keep bot credentials in existing secret/config facilities, never Git/roadmap/logs. Send only necessary event title/city/start/deadline/status and an authenticated admin-review link: no submitter contact data, tokens or unauthenticated approval actions. Escape event text for the chosen message format. Preserve server-side role/scope checks on linked pages.
  - **Reliability / acceptance:** use bounded asynchronous delivery, deduplication/concurrency guards, backoff/rate-limit handling and observable failures. Persist provider message IDs and reconcile ambiguous send outcomes rather than promising impossible exactly-once network delivery or blindly reposting. Handle message deleted/edit forbidden/bot removed without blocking submission or moderation; define an explicit visible fallback. No Telegram polling per dashboard row or per-second countdown edits. The inspected Python application currently has no Telegram implementation; first locate any separately deployed bot integration before choosing a shared adapter.
  - **Tests / release gate:** clock-controlled before/exact/after24h/48h; upcoming event crossing thresholds without edits; reschedule; city/national queues; canonical approval/rejection/cancellation and reopening; duplicate/concurrent workers, decision-versus-send/edit races, stale/out-of-order retries,429/timeouts/deleted-message/permission failures and escaped malicious titles. Assert the same provider message ID is edited and no private/bearer data is sent. Individually assess all new/touched tests. Mocked transport proves payload/retry behavior only; authorized staging-channel send→edit plus production routing/permission verification are required before claiming release. This roadmap addition does not send messages or store credentials.

- [ ] **DATA-07 · P2 · Backlog · Unassigned · M4:** Support **multi-day demonstrations** as a first-class event duration, distinct from a recurring series.
  - **Import round trip:** `FacebookEventImporter` already parses `utcEndDate` into `event.end_date`. Preserve a later end date through import response → wizard prefill/draft/preview → submission payload → persisted event → detail/calendar output. Add a real importer-fixture-to-persistence regression, not only hand-entered multi-day form tests; retain single-day and omitted-end compatibility. Current start-date/time-only prefill is not multi-day acceptance.
  - **Definition of Ready:** confirm continuous multi-day events versus separate daily sessions, inclusive displayed end date, omitted end time and overnight semantics. Choose an incremental date-range contract with Helsinki-local display and explicit timezone handling. Preserve existing single-day records, field/route/API compatibility and recurring-series identity; do not silently split one event into unrelated daily submissions.
  - **Delivery slices:** (1) optional end-date/range model, server validation and backward-compatible readers/API payloads; (2) public submission plus admin create/edit/review, previews, confirmation/email text and translations using shared form/date components; (3) discovery and exports. Validate chronological start/end, partial updates, old records and malformed ranges server-side. Preserve approval, edit-token, city/org scope and #887 reauthentication safeguards.
  - **Discovery / acceptance:** an ongoing event appears on every covered day's today/city/tag/calendar views, and upcoming/ongoing filters, counts and deterministic pagination agree without duplicating the event. Detail/cards show an unambiguous localized date/time range. Google Event structured data and iCalendar exports use correct start/end instants (including iCalendar exclusive all-day end semantics where applicable). Preserve #885's indexability window, recurring canonical/next-occurrence behavior and nearest-relevant event ordering; define the window behavior for a range spanning its boundary rather than guessing from start date alone.
  - **Validation:** single-day compatibility, overnight/multiple-day duration, month/year/leap-day and Europe/Helsinki DST boundaries; missing/invalid/reversed end dates, create/edit/token/recurring interactions, ongoing-versus-ended filtering, page-boundary counts/order and structured-data/calendar round trips. FI/EN/SV rendering plus desktop/mobile/light/dark form/detail/calendar checks. Individually assess every new/touched test in the inventory. Dependencies: explicit duration semantics, existing date/SEO/list contracts and incremental schema compatibility; this roadmap entry does not authorize a bulk production migration.

- [ ] **DATA-01 · P1:** Finish public pagination and totals; verify the API and browser controller together.
  - **DATA-01a · P1 · Merged · Codex · M2 · #927:** Clamp public tag/demo/organization page sizes to 1–100; skip out-of-range database offsets; isolate old oversized cache entries. Seven individually reviewed test definitions, 92 focused cases passed locally on 2026-10-13. No production load test, deployment or broader denial-of-service-resistance claim.
  - **DATA-01b · P2 · Merged · Codex · M2 · #928 · includes #927:** Automatic near-viewport loading, one list request at a time, five retained DOM pages (60 cards by default), no detached-page data cache. Backscroll re-fetches discarded pages; scroll anchor and focused cards are protected, including focus changes during slow requests. Filter/history cancellation and manual/retry/data-saving fallback remain. Four definitions individually assessed; nine new browser cases and 75 combined focused cases passed. Representative light desktop/dark mobile screenshots inspected. Live API performance, numerical heap profiling and broader assistive-technology acceptance remain unverified.
- [ ] **DATA-02 · P1:** Resolve worker fencing/rebuild pruning (#908) with multi-worker, retry, crash and rebuild overlap evidence. Verify rather than assume historical analytics repair has run in production.
- [ ] **DATA-03 · P2:** Review analytics accuracy/access/pagination (#551), large admin overview queries, and demonstration slow-query evidence from TODO.md. Establish measurement before index changes.
- [ ] **DATA-04 · P1:** Verify email queue retries/idempotency, outgoing case reply history (#771), background job leadership and external service failure handling (#176). Define redacted audit metadata separately from user message retention.
- [ ] **DATA-05 · P1:** Investigate image failure/retry/rate-limit reports (#579/#580/#581) and Socket.IO reconnect behavior (#640). Bound retries and prove failure recovery without request storms.
  - **DATA-05a · P1 · Merged · Codex · #947 / #581 / codex/profile-image-fallback:** Handler is disabled before the one fallback attempt, stopping repeated CDN requests. Exact-head required CI passed before normal merge63c85eae; both new browser cases executed locally, not proven by CI skips. One individually assessed definition covers fallback success/failure across all three avatar instances. Broader preview/Cloudflare/Socket.IO diagnosis remains separate; no production rate-limit claim.
- [ ] **DATA-06 · P2:** Reconcile module TODO issues (#391/#392/#393/#394), user settings/configuration requests (#196/#226), invitation user creation (#387), and other open backend PRs. Inspect their current diff and dependencies before scheduling implementation.

### Product and shared UI

- [ ] **UI-01 · P1:** Shared labels/picker, native cropper focus/source-resolution/accepted-image rollback and safe keyboard city suggestions are merged through #924/#929/#930/#940. Whole-wizard, broader assistive-technology/browser and release acceptance remain pending.
- **USER-01 · P2 · Released · Codex · M4 · #941 / codex/user-status-history:** Account-status confirmation and scoped before/after history use shared components and preserve permission/reauth contracts. Review corrections atomically retain each user/grant mutation's safe event in its source document, conditionally reject stale writes and project idempotently into admin/super audit stores; authorized reads/mutations retry delivery. Grant and role writes remain separate exact events, not one request-wide transaction. A bounded queue blocks unrecordable updates; deletion cannot remove undelivered events or reuse consumed fresh proof. Legacy status events, FI/EN/SV, fixed pagination and real-framework responsive themes retained. This is not canonical audit/GDPR or full retention acceptance. Public HTTPS and origin probes verify merge build `e6383141`; local fixture tests, not authenticated production inspection, cover visual acceptance.
- [ ] **UI-02 · P2:** Footer/card overflow and shared homepage/organization hero/mobile typography fixes are merged through #936/#937 in main 6ef40610. Broader media/table, zoom/widget, locale and release acceptance remain pending.
  - **UI-02a · P2 · Merged · Codex · M2/M4 · codex/public-mobile-width:** Own footer box sizing, shrinkable single-column grid and long card text wrapping at component level, without new global overflow suppression. Validate list/city/tag in both themes at 320/360/390/1440px with empty and populated responses, complete text and keyboard footer link bounds. All three width-test definitions reviewed; 93 combined cases pass and final test-file review has zero findings. Retain wider UI-02 scope.
  - **UI-02b · P2 · Merged · Codex · M2/M4 · codex/public-page-width · depends on #936:** Shared hero content/actions shrink and wrap; remove legacy forced mobile heading sizing and page-local organization min-width/home nowrap conflicts. Acceptance: actual home/normal/long-organization SSR in both themes at 320/360/390/1440px preserves complete text, centered bounds, shared mobile typography and visible actions. All 117 combined focused cases pass, including 24 new browser cases; broader UI-02, localization, widget and release acceptance remain pending.
- [ ] **FORM-01 · P2:** Organization details/forms and submission wizard migrate incrementally to shared sections/fields/modals. Preserve current permission and request contracts.
- [ ] **UI-03 · P2:** Consolidate detail styles and invite modal, then shared error/status pages. Preserve recurring canonical URLs, cancellation notices, layout preferences and future-event navigation.
- [ ] **UI-04 · P2:** Audit remaining public/admin form, list, editor and feedback surfaces against the written product standard, including dropdown clipping (#743), moderation affordances (#552) and #770's visual-quality expectations. Admin #677 is completed work, not a reason to repeat its migration.
- [ ] **UI-05 · P2:** Calendar image fallbacks/internal links, accessible legacy-view policy, remaining public tables, no-JS behavior and mobile text stacks.
- [ ] **PRODUCT-01 · P3:** Specify broader societal events (#583), tag following (#117), and city/tag subscription email (#121) only after core reliability/UX work. Confirm product requirements before backend schema or scope expansion.

### Localization and documentation

- [ ] **I18N-01:** Inventory active untranslated strings and catalog gaps; deliver by route family with real FI/EN/SV render checks.
  - **I18N-01a · P1 · Merged · Codex · M1/M5 · codex/account-status-runtime-translations:** Eight account-status source messages are absent from runtime catalogs on main 9098c02a. Compile only this verified set while preserving unrelated runtime entries and existing contextual status labels. Acceptance: exact shipped FI/EN/SV catalog values and actual localized activate/disable confirmation plus protected POST success; nine cases across two individually assessed definitions; all 31 focused account-status cases pass. Compiled changes and #929/#930 are merged in main 6ef40610; production acceptance remains unverified.
- [ ] **I18N-02:** Standardize backend/API/moderation/email messages (#582/#553), avoiding double translation in `flash_message()` and unsafe dynamic string interpolation.
- [ ] **DOC-01 · P2:** Update user/moderator guides (#563) and maintained setup/API/design docs against working code. Decide and document any intentionally Finnish-only surfaces.
- [ ] **DOC-02 · P2:** Keep this roadmap, detailed issues, release evidence and PMC aligned. Fix historical status conflicts through explicit updates, never by treating old notes as current implementation.

### Operations, performance and continuity

The PMC **Infrastructure and continuity work plan** owns the detailed OPS-001–OPS-010 documentation and subsequent live work. Reuse it; documentation completion does not prove live recovery.

- [ ] **OPS-01 · P1:** Verify backup coverage/freshness, failure alert delivery, recovery access and ownership. Prepare measurable acceptance evidence for gaps.
- [ ] **OPS-02 · P1:** Conduct authorized isolated application/mail/full-service recovery exercises; record RPO/RTO, dependency order, rollback and reproducible server construction.
- [ ] **OPS-03 · P2:** Review released Web Vitals only after minimum sample thresholds; correlate route/device percentiles with controlled measurements. Verify alert routing and job/email latency coverage.
- [ ] **OPS-04 · P1:** Maintain exact-build deployment/rollback and CDN dependency contracts. Production, provider, credential, backup-policy, DNS and database mutations follow their established approval scope.
  - **OPS-04a · P1 · Released · Codex · #950:** Normal merge fcb6a295 and automatic deploy39732901474 succeeded. Origin served exact build; actual initial403/cf-mitigated:challenge emitted the intended warning. Public reachability is not established by that warning. Ordinary errors, wrong SHA, missing/mismatched origin receipt and later challenges masking prior failures remain strict. No WAF/TLS/auth weakening. Forty focused verifier cases and exact-head CI preceded merge.
  - **OPS-04c · P1 · In progress · Codex · #952 / codex/deploy-dependency-receipt:** Atomic root-state receipt, installed changed-pin checks and read-only legacy-system adoption replace checkout-based skip. Owned venv installs/bootstrap/check must succeed before acknowledgement; unrelated legacy drift is reported, never silently downgraded. Eight individually assessed definitions /20 cases;64 combined focused cases pass locally. Proper review, main integration, normal PR delivery and actual production receipt adoption/exact-build health remain pending. No full venv migration or broader drift-reconciliation acceptance is claimed.

### Privacy and audit architecture

- [ ] **PRIV-01 · P1:** Produce a reviewed canonical audit schema and migration plan for every source in TODO.md; UTC, stable identity/correlation, outcomes, field allowlists and centralized redaction.
- [ ] **PRIV-02 · P1:** Implement observability for audit delivery, tamper evidence, cross-source investigation permissions and retention/deletion/export rules in separate reviewed batches.
- [ ] **PRIV-03 · P1:** Resolve #596 with the responsible privacy/legal owner; data-flow/consent/retention and backup policies need human policy review as well as technical tests.

### Maintenance

- [ ] **CLEAN-01 · P3:** Inventory references before removing orphan `list_legacy.html`, template `submit.css` and tracked backups; revalidate against current main.
- [ ] **CLEAN-02 · P2:** Consolidate legacy palettes and shared hero geometry incrementally. Do not move all inline CSS into one unstructured stylesheet.
- [ ] **CLEAN-03 · P2:** Reconcile open dependency PRs with compatibility/security evidence; retire stale branches/PRs only with the appropriate authority.
- [ ] **CLEAN-04 · P2:** Keep a finite exception list for dynamic styles/variables and an enforceable CSS/asset-cache contract.

## Test-by-test review programme

**Every existing test must receive a review entry**, including parametrized variants and tests added while work continues. This is a review of meaningful protection, not a demand to add a test for every function (#174) or to delete inconvenient failures.

The baseline [individual review inventory](docs/test-review-inventory.md) contained **997 test definitions across 140 Python test files**: 992 under `tests/` and five in the standalone recurrence script. Branch **`codex/deploy-cloudflare-health`** on main `63c85eae` has **1,173 definitions across 161 files**, with **268 assessed definitions**. Independent #942/#946 are excluded until integration; retain all reviews. These are tracked-Python AST branch counts, not collected cases, completed suite review or release evidence. Older per-branch counts remain historical. The two test-named fixtures are excluded and assessed separately. Audit fixtures, CI, standalone scripts and browser harnesses too.

For each test, record:

| Field | Required review evidence |
|---|---|
| Requirement | The user behavior/security/data invariant and issue or contract it protects. |
| Setup | Fixture realism, database/session/role state, dependencies and whether mocks erase the behavior being claimed. |
| Assertion quality | What fails if the behavior breaks; check real outcome/state, not only source text, a loose status-code range or mirrored implementation. |
| Cases | Parametrized variants, positive/negative paths, scope boundaries, cancellation/retry/concurrency and locale/theme/device where applicable. |
| Reliability | Isolation, deterministic time/data/order, cleanup, skipped cases, external network assumptions and flakiness. |
| Disposition | Keep; strengthen; merge duplicate; retire obsolete with reason; or blocked with exact dependency. |
| Evidence | Reviewer/date, revision, relevant node IDs, observed run result and linked fix PR when needed. |

Leave a checkbox unchecked until that evidence exists. A passing run alone does not satisfy review. Static guards can prevent structural regressions but cannot prove visual quality, authorization or runtime correctness.

Review order:

1. **QA-01 · P1 — security:** login/MFA/passkeys, fresh step-up, tokens, role/scope/anonymous/banned access, unsafe input/output.
2. **QA-02 · P1 — data and workflows:** demo approval/recurrence/pagination, organizations/invites/cases, submissions/drafts/imports, mail/jobs/analytics.
3. **QA-03 · P2 — shared UI:** CSS/token/inline-style contracts, public/admin form/list/modal/chrome tests; identify brittle snapshots and missing runtime assertions.
4. **QA-04 · P2 — localization/accessibility/browser:** FI/EN/SV, keyboard/focus/no-JS, themes, mobile/desktop/zoom, errors/loading/empty/disabled states.
5. **QA-05 · P2 — operations and remaining tests:** deployment/configuration/integrations/retention/performance and all remaining inventory entries.

These are review-batch priorities, not the severity of every contained test. Escalate a discovered critical/core-workflow gap under the P0/P1 policy immediately. Record the requirement, review status and justified priority for each test; do not mechanically assign priorities from file names.

Run the relevant focused tests after changes. Run the broader required CI suite at integration milestones; do not rerun the whole suite for each documentation or CSS edit. Record unavailable dependencies honestly. Fix substantive gaps in small PRs without weakening valid security or workflow checks.

Test review proceeds beside each delivery batch: review its existing tests before relying on them, record gaps, and strengthen only the evidence the change requires. At each milestone refresh the inventory against current pytest collection, investigate additions/removals and cover tests outside `tests/`. No unchecked test may disappear silently.

## Delivery gates

**Definition of Ready:** the current requirement is verified, an owner and milestone are recorded, dependencies are explicit, the batch is reviewable, and acceptance/validation are agreed.

**Definition of Done:** acceptance criteria are demonstrated; applicable tests and review are complete; CHANGELOG/cache keys/docs are updated as needed; no unresolved blocking review finding remains; merge/release evidence is linked when required. A green check or an open PR alone does not meet this definition.

## Active status ledger

| ID | Priority | Status | Owner | Milestone | Evidence / next action |
|---|---|---|---|---|---|
| SEC-01 | P1 | Merged | Codex | M1 | #901 in inspected main `3c2c8d3c`; release acceptance not established here. |
| QA-01 | P1 | In progress | Codex | M1, then ongoing | #932–#935/#938–#940 add individually reviewed step-up, deletion, redirect, token and moderation protection to the combined inventory. Remaining authentication/permission tests are still unchecked. |
| QA-01e / SEC-04a/b | P1 | Merged | Codex | M1/M6 | #938–#940 supply decision side-effect tests, deterministic opposite-decision/CAS retry cases and content/MCP preservation regressions. Provider acceptance/crash, rollback and stale-content races remain open. |
| SEC-02 | P1 | Merged | Codex | M1 | #915/#916/#919 are merged; #763 is closed. Shared status-action visibility, hierarchy checks and duplicate-submit protection are integrated. Runtime translation follow-up #931 and broader release acceptance remain open; merge and issue closure do not establish production acceptance. |
| SEC-03 | P0/P1 | In progress | Codex | M1 | #918/#917/#919 are merged, including user hierarchy/delegation, global clearance gates and searchable redacted audits. Broader role/audit acceptance remains pending. |
| QA-02 | P1 | In progress | Codex | M2–M3 | Five API, five request-state, five listing-contract and three URL/history definitions reviewed on this stack. Remaining data/workflow tests pending. |
| QA-03, QA-05 | P2 | Backlog | Unassigned | M4–M6 | Review shared UI and operations/remaining tests. |
| QA-04 | P2 | In progress | Codex | M2, then M4–M6 | Two field, four existing accessibility and four real-picker definitions assessed; broader browser/assistive-technology evidence remains pending. |
| DATA-01 | P1 | In progress | Codex | M2 | #920–#924 and bounded pagination/automatic loading #927–#928 are merged. Broader integration, legacy data and release acceptance remain pending. |
| UI-01 | P1 | In progress | Codex | M2 | Search labels/picker and #929/#930 cropper/autocomplete are merged in main 6ef40610. Whole-wizard, broader browser/assistive-technology and release acceptance remain pending. |
| DATA-02 / OPS-01 | P1 | Backlog | Unassigned | M3 | Verify #908 and load the existing continuity plan. |
| ACCEPT-01 | P1 | Backlog | Unassigned | M6 | Depends on delivered milestones and completed per-test reviews. |
| UI-02a | P2 | Merged | Codex | M2/M4 | Footer padding is inside width; card title/address/tag text can wrap. Empty/populated route/theme/viewport and keyboard controls validate this slice; 93 combined cases pass; broader UI-02 acceptance remains open. |
| UI-02b | P2 | Merged | Codex | M2/M4 | Depends on #936. Shared hero geometry/mobile typography with no fixed-min-width or nowrap conflict; 117 focused cases pass, including 24 actual SSR cases. Wider product acceptance remains open. |
| USER-01 | P2 | Released | Codex | M4 | #941 merge build e6383141 verified through public HTTPS and direct origin health probes; service active, existing tracked server overlays preserved. Final CI: 1,370 passed /325 skipped. GitHub deploy public-probe403 failure remains explicitly recorded; no authenticated production visual QA claim. |
| CITY-01 | P2 | Backlog | Unassigned | M2/M4 | Extend existing city assignment/email/escalation with in-app notification and a shared authoritative dashboard deadline/countdown. Code default24h; deployed setting unverified. Define reset/config-change policy before implementation. |
| CITY-02 | P1 | Backlog | Unassigned | M2 | Urgent pending-event Telegram alert (<48h, higher urgency <24h proposed) via @mielenosoituksetbot to the owner-named channel; edit the same message after canonical processing. Verify numeric chat ID, permissions, existing external bot, retry/state policy and staging send/edit before release. |
| DATA-07 | P2 | Backlog | Unassigned | M4 | Multi-day duration, compatible model/forms, ongoing discovery, SEO/calendar exports and explicit recurrence boundaries. Confirm duration semantics before schema/UI implementation. |
| All other IDs | As assigned above | Backlog | Unassigned | Assign before starting | Verify requirement, dependencies and acceptance before promoting to Ready. |

The repository programme is complete only when each in-scope requirement has evidence, the per-test reviews are recorded, relevant checks pass, trackers match merged state, and release claims have actual deployment evidence. Do not equate this roadmap's creation with completion of the work.
