# Repository roadmap

Last reconciled: 2026-10-15. Evidence baseline: `main` at `9098c02affc1244d92911d3e2afae9842db284e5`.

This is the delivery plan for the **whole repository**: security, public and admin workflows, backend correctness, operations, privacy, localization, tests, and maintenance. Issue [#833](https://github.com/botsarefuture/mielenosoitukset_fi/issues/833) is one workstream within it. Existing issue trackers retain their detailed acceptance criteria; this document sets the order and dependencies.

An open issue is a candidate for investigation, not proof that its original report remains true. Verify the current code before fixing it. The dates and revision above are planning evidence, not a claim about current production.

## At a glance

- **Next:** Finish UI-02a shared footer/card width correction, then continue homepage/organization and UI-01 integration gaps, then continue remaining security/data test reviews and UI-01 integration/QA. Implementation slices are in open #929–#935; #929 committed-image rollback awaits per-change approval. Open PRs are not deployed fixes.
- **Alongside delivery:** QA-01/QA-02 — review security and data/workflow tests individually.
- **Verified merge checkpoint:** #926 is merged; #928 integrated #927 and the remaining organization/retry/attendance review corrections into main `9098c02a`. Required CI passed on its final integration head. No separate deployment or production verification is claimed. No new PR has merge/deploy authorization.
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

- **QA-01d · P1 · In review · Codex · M1/M6 · codex/edit-link-test-review:** Assess anonymous token form plus existing #672 lifecycle tests; prove 1h/24h/7d signature/registry agreement across GET/POST, revoked-session rejection, scoped bulk revocation, management/session CSRF, malformed registry/signature denial and immutable approval authority. Ten definitions assessed; 31 direct cases plus unchanged decision regressions total 37 passing. #672 remains closed; no production policy change or live-release claim.

- **QA-01c · P1 · In review · Codex · M1/M6 · codex/login-return-target-safety:** Verified locally that popup completion can interpret a return target as executable script. Serialize it with Jinja tojson and require unambiguous root-relative targets; reject controls, self-login loops and API variants using effective path classification. Preserve valid query/fragment targets and actual opener reload/close behavior. Five definitions individually assessed; 45 targeted cases pass; 97 combined focused cases and six-file CodeRabbit review pass. No live exploitation, production deployment or broader authentication-audit claim.

- **QA-01b · P1 · In review · Codex · M1/M6 · codex/fresh-deletion-test-review:** Individually assess seventeen existing plus two new fresh-deletion definitions. Replace vacuous expiry/replay scenarios with unused-token 60-second boundaries and same-target reuse; cover wrong actor, preserved proof on wrong target, JSON/form prerequisites and synchronized atomic consumption. Acceptance: 34 combined fresh-deletion/ordinary-step-up cases pass, isolated expiry/used predicate mutations are detected, per-definition fixture/assertion/coverage limits recorded. No production or #887 policy change.

- **QA-01a · P1 · In review · Codex · M1/M6 · codex/step-up-test-review:** Individually assess all eleven step-up test definitions; repair vacuous original-session logout coverage and strengthen configured time boundaries, actor/session isolation, invalid credential rejection and stored password outcomes. Acceptance: focused step-up and fresh-deletion regressions pass (30 cases), mutation confirms logout cleanup regression detection, fixture/mock limits and remaining cases recorded. No production authentication or #887 policy changes.

- [ ] **SEC-01 · P1:** #901 MFA challenge implementation is merged; preserve the shared legacy/no-JS behavior and obtain required release acceptance evidence.
- [ ] **SEC-02 · P1:** Inactive/banned-account enforcement and admin status workflows are merged through #915/#916/#919, including shared target checks and atomic duplicate-submit coverage. Tracker #763 is closed; broader integration/release acceptance still needs evidence. Its runtime-copy follow-up is I18N-01a, not a reopened authorization defect.
- [ ] **SEC-03 · P0/P1:** #918 target-organization/input validation and #917 case scope are merged; #919 user-action hierarchy/delegation, global clearance scope and audit searchability are merged through the account-management integration. Broader role lifecycle, concurrency, destructive-action and canonical audit requirements remain tracked.
- [ ] **SEC-04 · P1:** Reconcile token/approval lifecycle requirements and prior completed trackers against current routes; prove revocation, expiry, replay behavior, idempotent decisions, case closure, audit and notification effects for every entrypoint.
- [ ] **SEC-05 · P1:** Review incident #912/#913 protections and credential/session lifecycle regressions before touching related code. Keep secrets out of documentation and audit data.

### Backend, data, jobs and integrations

- [ ] **DATA-01 · P1:** Finish public pagination and totals; verify the API and browser controller together.
  - **DATA-01a · P1 · Merged · Codex · M2 · #927:** Clamp public tag/demo/organization page sizes to 1–100; skip out-of-range database offsets; isolate old oversized cache entries. Seven individually reviewed test definitions, 92 focused cases passed locally on 2026-10-13. No production load test, deployment or broader denial-of-service-resistance claim.
  - **DATA-01b · P2 · Merged · Codex · M2 · #928 · includes #927:** Automatic near-viewport loading, one list request at a time, five retained DOM pages (60 cards by default), no detached-page data cache. Backscroll re-fetches discarded pages; scroll anchor and focused cards are protected, including focus changes during slow requests. Filter/history cancellation and manual/retry/data-saving fallback remain. Four definitions individually assessed; nine new browser cases and 75 combined focused cases passed. Representative light desktop/dark mobile screenshots inspected. Live API performance, numerical heap profiling and broader assistive-technology acceptance remain unverified.
- [ ] **DATA-02 · P1:** Resolve worker fencing/rebuild pruning (#908) with multi-worker, retry, crash and rebuild overlap evidence. Verify rather than assume historical analytics repair has run in production.
- [ ] **DATA-03 · P2:** Review analytics accuracy/access/pagination (#551), large admin overview queries, and demonstration slow-query evidence from TODO.md. Establish measurement before index changes.
- [ ] **DATA-04 · P1:** Verify email queue retries/idempotency, outgoing case reply history (#771), background job leadership and external service failure handling (#176). Define redacted audit metadata separately from user message retention.
- [ ] **DATA-05 · P1:** Investigate image failure/retry/rate-limit reports (#579/#580/#581) and Socket.IO reconnect behavior (#640). Bound retries and prove failure recovery without request storms.
- [ ] **DATA-06 · P2:** Reconcile module TODO issues (#391/#392/#393/#394), user settings/configuration requests (#196/#226), invitation user creation (#387), and other open backend PRs. Inspect their current diff and dependencies before scheduling implementation.

### Product and shared UI

- [ ] **UI-01 · P1:** Shared labels and real pinned picker locale/min-max/selected-state/history/clear/keyboard/theme behavior are implemented and verified on this stack. Cropper, autocomplete keyboard, broader assistive-technology/browser and integration/release acceptance remain pending.
- [ ] **UI-02 · P2:** Consolidate homepage/city discovery using the existing shared design language; verify icon centering, content widths, restrained hero hierarchy, themes and mobile. Current main reproduced a 390px list body at 422px due to footer content-box padding; long card text was also internally clipped. UI-02a fixes these shared component causes on codex/public-mobile-width; broader homepage/organization, media/table, zoom/widget and release acceptance remain pending.
  - **UI-02a · P2 · In review · Codex · M2/M4 · codex/public-mobile-width:** Own footer box sizing, shrinkable single-column grid and long card text wrapping at component level, without new global overflow suppression. Validate list/city/tag in both themes at 320/360/390/1440px with empty and populated responses, complete text and keyboard footer link bounds. All three width-test definitions reviewed; 93 combined cases pass and final test-file review has zero findings. Retain wider UI-02 scope.
- [ ] **FORM-01 · P2:** Organization details/forms and submission wizard migrate incrementally to shared sections/fields/modals. Preserve current permission and request contracts.
- [ ] **UI-03 · P2:** Consolidate detail styles and invite modal, then shared error/status pages. Preserve recurring canonical URLs, cancellation notices, layout preferences and future-event navigation.
- [ ] **UI-04 · P2:** Audit remaining public/admin form, list, editor and feedback surfaces against the written product standard, including dropdown clipping (#743), moderation affordances (#552) and #770's visual-quality expectations. Admin #677 is completed work, not a reason to repeat its migration.
- [ ] **UI-05 · P2:** Calendar image fallbacks/internal links, accessible legacy-view policy, remaining public tables, no-JS behavior and mobile text stacks.
- [ ] **PRODUCT-01 · P3:** Specify broader societal events (#583), tag following (#117), and city/tag subscription email (#121) only after core reliability/UX work. Confirm product requirements before backend schema or scope expansion.

### Localization and documentation

- [ ] **I18N-01:** Inventory active untranslated strings and catalog gaps; deliver by route family with real FI/EN/SV render checks.
  - **I18N-01a · P1 · In review · Codex · M1/M5 · open #931:** Eight account-status source messages are absent from runtime catalogs on main 9098c02a. Compile only this verified set while preserving unrelated runtime entries and existing contextual status labels. Acceptance: exact shipped FI/EN/SV catalog values and actual localized activate/disable confirmation plus protected POST success; nine cases across two individually assessed definitions; all 31 focused account-status cases pass. Independent UI work remains in open #929/#930; no merge/release claim.
- [ ] **I18N-02:** Standardize backend/API/moderation/email messages (#582/#553), avoiding double translation in `flash_message()` and unsafe dynamic string interpolation.
- [ ] **DOC-01 · P2:** Update user/moderator guides (#563) and maintained setup/API/design docs against working code. Decide and document any intentionally Finnish-only surfaces.
- [ ] **DOC-02 · P2:** Keep this roadmap, detailed issues, release evidence and PMC aligned. Fix historical status conflicts through explicit updates, never by treating old notes as current implementation.

### Operations, performance and continuity

The PMC **Infrastructure and continuity work plan** owns the detailed OPS-001–OPS-010 documentation and subsequent live work. Reuse it; documentation completion does not prove live recovery.

- [ ] **OPS-01 · P1:** Verify backup coverage/freshness, failure alert delivery, recovery access and ownership. Prepare measurable acceptance evidence for gaps.
- [ ] **OPS-02 · P1:** Conduct authorized isolated application/mail/full-service recovery exercises; record RPO/RTO, dependency order, rollback and reproducible server construction.
- [ ] **OPS-03 · P2:** Review released Web Vitals only after minimum sample thresholds; correlate route/device percentiles with controlled measurements. Verify alert routing and job/email latency coverage.
- [ ] **OPS-04 · P1:** Maintain exact-build deployment/rollback and CDN dependency contracts. Production, provider, credential, backup-policy, DNS and database mutations follow their established approval scope.

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

The baseline [individual review inventory](docs/test-review-inventory.md) contained **997 test definitions across 140 Python test files**: 992 under `tests/` and five in the standalone recurrence script. Public-width branch based on main 9098c02a: **1,105 definitions across 153 files**, with 144 assessed definitions. These totals exclude independent open PRs #929–#935. The two test-named fixtures in `conftest.py` have separate supporting-audit entries and do not count as tests. It is a repository-wide tracked-Python AST inventory, not pytest collection and not a completed test review. Parameter expansion, generated cases, integration dependencies and skips are verified during collection. Audit `conftest.py`, shared fixtures, pytest configuration, CI, standalone test scripts and browser harnesses as dependencies too.

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
| QA-01 | P1 | In progress | Codex | M1, then ongoing | QA-01a/#932, QA-01b/#933 and QA-01c/#934 remain open. QA-01d on codex/edit-link-test-review assesses ten token/shell definitions; 37 focused cases pass. Remaining security/data/fixture reviews continue alongside UI integration, not as a reason to leave verified mobile defects untouched. |
| SEC-02 | P1 | Merged | Codex | M1 | #915/#916/#919 are in main; shared status-action visibility and synchronized duplicate-submit coverage are included. #763 integration/release acceptance remains pending. |
| SEC-03 | P0/P1 | In progress | Codex | M1 | #918/#917/#919 are merged, including user hierarchy/delegation, global clearance gates and searchable redacted audits. Broader role/audit acceptance remains pending. |
| QA-02 | P1 | In progress | Codex | M2–M3 | Five API, five request-state, five listing-contract and three URL/history definitions reviewed on this stack. Remaining data/workflow tests pending. |
| QA-03, QA-05 | P2 | Backlog | Unassigned | M4–M6 | Review shared UI and operations/remaining tests. |
| QA-04 | P2 | In progress | Codex | M2, then M4–M6 | Two field, four existing accessibility and four real-picker definitions assessed; broader browser/assistive-technology evidence remains pending. |
| DATA-01 | P1 | In progress | Codex | M2 | #920–#924 public API/request/history/search/picker code is in main 60992b19. Bounds/legacy times, broader integration and release acceptance remain pending. |
| UI-01 | P1 | In progress | Codex | M2 | Search labels/picker merged through #924. Cropper is in open #929. City autocomplete in open #930 shares safe combobox/keyboard/active-option behavior across list/tag, preserving existing selection/search contracts. Two definitions reviewed, 64 focused cases passed. Full wizard, broader browser/assistive-technology and release acceptance remain pending. |
| DATA-02 / OPS-01 | P1 | Backlog | Unassigned | M3 | Verify #908 and load the existing continuity plan. |
| ACCEPT-01 | P1 | Backlog | Unassigned | M6 | Depends on delivered milestones and completed per-test reviews. |
| UI-02a | P2 | In review | Codex | M2/M4 | Footer padding is inside width; card title/address/tag text can wrap. Empty/populated route/theme/viewport and keyboard controls validate this slice; 93 combined cases pass; broader UI-02 acceptance remains open. |
| All other IDs | As assigned above | Backlog | Unassigned | Assign before starting | Verify requirement, dependencies and acceptance before promoting to Ready. |

The repository programme is complete only when each in-scope requirement has evidence, the per-test reviews are recorded, relevant checks pass, trackers match merged state, and release claims have actual deployment evidence. Do not equate this roadmap's creation with completion of the work.
