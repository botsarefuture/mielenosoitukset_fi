# Repository roadmap

Last planned: 2026-10-12. Evidence baseline: `main` at `52a971e1e11c6560e1eb45393c2ef812bbadd693`.

This is the delivery plan for the **whole repository**: security, public and admin workflows, backend correctness, operations, privacy, localization, tests, and maintenance. Issue [#833](https://github.com/botsarefuture/mielenosoitukset_fi/issues/833) is one workstream within it. Existing issue trackers retain their detailed acceptance criteria; this document sets the order and dependencies.

An open issue is a candidate for investigation, not proof that its original report remains true. Verify the current code before fixing it. The dates and revision above are planning evidence, not a claim about current production.

## How to choose the next task

1. Fetch current main, inspect the relevant PR and issue, and read the applicable PMC notes. Preserve unrelated local changes using a clean isolated checkout.
2. Select the first unblocked item in the next queue below. Record its ID, intended result, dependencies, focused validation, and current status here before starting.
3. Finish one reviewable batch before opening another in the same workstream. Independent work may proceed while a PR awaits human review; record that explicitly.
4. Use shared product components and existing Flask/Jinja/Bootstrap contracts. Preserve permission enforcement, payloads, routes, token scope, and fresh per-deletion reauthentication from #887. Preserve the incident containment/hardening merged in #912/#913.
5. Every behavioral or visual batch includes CHANGELOG, applicable CSS cache version changes, focused validation, and PR evidence. Documentation-only batches need document validation, not a full application suite.
6. After creating a PR, continue the next unblocked item. Merge/deploy requires authorization for that action. Mark implementation merged only after verifying main contains it; mark released only with deployment evidence.
7. Change the order for a confirmed incident or higher-impact defect, documenting the reason. Do not start speculative rewrites or infrastructure changes merely because a task is blocked.

## Next delivery queue

| Order | ID | Work | Dependencies / exit evidence |
|---|---|---|---|
| 1 | SEC-01 | Finish open PR #901: remove password duplication in MFA and repair pending-login lifecycle. | Rebase on current main; server-held opaque challenge, atomic consumption, password-change revocation, expiry and bounded attempts. Prove copied-cookie replay, concurrent consume, reset revocation, invalid-code behavior, and preserved #887 fresh reauthentication. |
| 2 | QA-01 | Audit authentication/authorization tests individually and verify old security reports. | Start the per-test ledger below; verify #763 and #778 against current behavior before changes. Record negative-path assertions and gaps; no inference of completion from green checks. |
| 3 | DATA-01 | Public list ordering, pagination, and result summary. | Stable date/time/ID ordering, no duplicate or missing records at page boundaries, correct totals/ranges, filter reset and URL state. Share behavior across list/city/tag. |
| 4 | UI-01 | Search field labels and image-cropper modal. | Shared form/modal components; localized labels, focus entry/trap/return, Escape, safe DOM, loading/error states, desktop/mobile and both themes. |
| 5 | OPS-01 | Review worker coordination and recovery/alert evidence. | Verify #908 against merged #903 and recent hardening; prepare isolated coordination tests. Use the existing continuity plan for live recovery and alert tasks; record remaining approvals rather than improvising production changes. |
| 6 | UI-02 | City discovery and homepage component consolidation. | Token-based metric/card/hero geometry; remove overlapping palettes/imports after current asset verification; mobile, keyboard, light/dark and performance checks. |
| 7 | FORM-01 | Public organization forms and submission wizard. | Follow #178 and #833; preserve invitations, organizer hooks, draft/idempotency/import contracts. Shared field/section/feedback structure and removal of repeated inline styles. |
| 8 | UI-03 | Detail, shared error/status pages, and remaining page families. | Account for merged #900; preserve overview/classic preference and SEO. Shared dialogs/cards/feedback; all rendered variants verified. |
| 9 | I18N-01 | Complete localization in bounded route/page families. | Follow #582/#553. FI/EN/SV templates, JS, flash, JSON, email and metadata; catalogs contain actual translations. `flash_message()` already translates literal IDs. |
| 10 | CLEAN-01 | Remove verified dead assets and retire competing styling. | Reference inventory first; decide legacy calendar policy explicitly; shrink inline-style baseline and verify shipping variables/cache keys. |
| 11 | ACCEPT-01 | Repository-wide acceptance and tracker reconciliation. | Complete test audit, workflow/surface coverage, representative browser matrix and relevant CI. Close only requirements supported by evidence; document outstanding non-UI work separately. |

SEC-01 is currently **open PR** [#901](https://github.com/botsarefuture/mielenosoitukset_fi/pull/901), with verified review concerns about client-cookie replay and password-change revocation. Later queue entries are **planned**, not implemented or proven complete. #900 is merged; its recurring discovery changes must not be recreated.

## Workstreams and remaining backlog

### Security and permissions

- [ ] **SEC-01:** Complete the pending MFA challenge contract described above; review the legacy MFA verification route and no-JavaScript behavior as part of the same authentication workflow.
- [ ] **SEC-02:** Verify inactive/banned-account enforcement (#763) across password, MFA, passkey, session loading and protected requests; fix only remaining gaps.
- [ ] **SEC-03:** Verify city-admin case access (#778), organization invite/member rules (#550/#342), and privileged user operations (#547). Prove allowed and forbidden scopes server-side.
- [ ] **SEC-04:** Reconcile token/approval lifecycle requirements and prior completed trackers against current routes; prove revocation, expiry, replay behavior, idempotent decisions, case closure, audit and notification effects for every entrypoint.
- [ ] **SEC-05:** Review incident #912/#913 protections and credential/session lifecycle regressions before touching related code. Keep secrets out of documentation and audit data.

### Backend, data, jobs and integrations

- [ ] **DATA-01:** Finish public pagination and totals; verify the API and browser controller together.
- [ ] **DATA-02:** Resolve worker fencing/rebuild pruning (#908) with multi-worker, retry, crash and rebuild overlap evidence. Verify rather than assume historical analytics repair has run in production.
- [ ] **DATA-03:** Review analytics accuracy/access/pagination (#551), large admin overview queries, and demonstration slow-query evidence from TODO.md. Establish measurement before index changes.
- [ ] **DATA-04:** Verify email queue retries/idempotency, outgoing case reply history (#771), background job leadership and external service failure handling (#176). Define redacted audit metadata separately from user message retention.
- [ ] **DATA-05:** Investigate image failure/retry/rate-limit reports (#579/#580/#581) and Socket.IO reconnect behavior (#640). Bound retries and prove failure recovery without request storms.
- [ ] **DATA-06:** Reconcile module TODO issues (#391/#392/#393/#394), user settings/configuration requests (#196/#226), invitation user creation (#387), and other open backend PRs. Inspect their current diff and dependencies before scheduling implementation.

### Product and shared UI

- [ ] **UI-01:** Complete labels, focus and cropper behavior first.
- [ ] **UI-02:** Consolidate homepage/city discovery using the existing shared design language; verify icon centering, content widths, restrained hero hierarchy, themes and mobile.
- [ ] **FORM-01:** Organization details/forms and submission wizard migrate incrementally to shared sections/fields/modals. Preserve current permission and request contracts.
- [ ] **UI-03:** Consolidate detail styles and invite modal, then shared error/status pages. Preserve recurring canonical URLs, cancellation notices, layout preferences and future-event navigation.
- [ ] **UI-04:** Audit remaining public/admin form, list, editor and feedback surfaces against the written product standard, including dropdown clipping (#743), moderation affordances (#552) and #770's visual-quality expectations. Admin #677 is completed work, not a reason to repeat its migration.
- [ ] **UI-05:** Calendar image fallbacks/internal links, accessible legacy-view policy, remaining public tables, no-JS behavior and mobile text stacks.
- [ ] **PRODUCT-01:** Specify broader societal events (#583), tag following (#117), and city/tag subscription email (#121) only after core reliability/UX work. Confirm product requirements before backend schema or scope expansion.

### Localization and documentation

- [ ] **I18N-01:** Inventory active untranslated strings and catalog gaps; deliver by route family with real FI/EN/SV render checks.
- [ ] **I18N-02:** Standardize backend/API/moderation/email messages (#582/#553), avoiding double translation in `flash_message()` and unsafe dynamic string interpolation.
- [ ] **DOC-01:** Update user/moderator guides (#563) and maintained setup/API/design docs against working code. Decide and document any intentionally Finnish-only surfaces.
- [ ] **DOC-02:** Keep this roadmap, detailed issues, release evidence and PMC aligned. Fix historical status conflicts through explicit updates, never by treating old notes as current implementation.

### Operations, performance and continuity

The PMC **Infrastructure and continuity work plan** owns the detailed OPS-001–OPS-010 documentation and subsequent live work. Reuse it; documentation completion does not prove live recovery.

- [ ] **OPS-01:** Verify backup coverage/freshness, failure alert delivery, recovery access and ownership. Prepare measurable acceptance evidence for gaps.
- [ ] **OPS-02:** Conduct authorized isolated application/mail/full-service recovery exercises; record RPO/RTO, dependency order, rollback and reproducible server construction.
- [ ] **OPS-03:** Review released Web Vitals only after minimum sample thresholds; correlate route/device percentiles with controlled measurements. Verify alert routing and job/email latency coverage.
- [ ] **OPS-04:** Maintain exact-build deployment/rollback and CDN dependency contracts. Production, provider, credential, backup-policy, DNS and database mutations follow their established approval scope.

### Privacy and audit architecture

- [ ] **PRIV-01:** Produce a reviewed canonical audit schema and migration plan for every source in TODO.md; UTC, stable identity/correlation, outcomes, field allowlists and centralized redaction.
- [ ] **PRIV-02:** Implement observability for audit delivery, tamper evidence, cross-source investigation permissions and retention/deletion/export rules in separate reviewed batches.
- [ ] **PRIV-03:** Resolve #596 with the responsible privacy/legal owner; data-flow/consent/retention and backup policies need human policy review as well as technical tests.

### Maintenance

- [ ] **CLEAN-01:** Inventory references before removing orphan `list_legacy.html`, template `submit.css` and tracked backups; revalidate against current main.
- [ ] **CLEAN-02:** Consolidate legacy palettes and shared hero geometry incrementally. Do not move all inline CSS into one unstructured stylesheet.
- [ ] **CLEAN-03:** Reconcile open dependency PRs with compatibility/security evidence; retire stale branches/PRs only with the appropriate authority.
- [ ] **CLEAN-04:** Keep a finite exception list for dynamic styles/variables and an enforceable CSS/asset-cache contract.

## Test-by-test review programme

**Every existing test must receive a review entry**, including parametrized variants and tests added while work continues. This is a review of meaningful protection, not a demand to add a test for every function (#174) or to delete inconvenient failures.

The initial [individual review inventory](docs/test-review-inventory.md) lists **994 test definitions across 140 Python test files** at the baseline revision. It is an AST inventory, not pytest collection and not a completed test review. Parameter expansion, generated cases, integration dependencies and skips are verified during collection. Audit `conftest.py`, shared fixtures, pytest configuration, CI, standalone test scripts and browser harnesses as dependencies too.

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

1. **QA-01 — security:** login/MFA/passkeys, fresh step-up, tokens, role/scope/anonymous/banned access, unsafe input/output.
2. **QA-02 — data and workflows:** demo approval/recurrence/pagination, organizations/invites/cases, submissions/drafts/imports, mail/jobs/analytics.
3. **QA-03 — shared UI:** CSS/token/inline-style contracts, public/admin form/list/modal/chrome tests; identify brittle snapshots and missing runtime assertions.
4. **QA-04 — localization/accessibility/browser:** FI/EN/SV, keyboard/focus/no-JS, themes, mobile/desktop/zoom, errors/loading/empty/disabled states.
5. **QA-05 — operations and remaining tests:** deployment/configuration/integrations/retention/performance and all remaining inventory entries.

Run the relevant focused tests after changes. Run the broader required CI suite at integration milestones; do not rerun the whole suite for each documentation or CSS edit. Record unavailable dependencies honestly. Fix substantive gaps in small PRs without weakening valid security or workflow checks.

Test review proceeds beside each delivery batch: review its existing tests before relying on them, record gaps, and strengthen only the evidence the change requires. At each milestone refresh the inventory against current pytest collection, investigate additions/removals and cover tests outside `tests/`. No unchecked test may disappear silently.

## Completion and status ledger

| ID | Status at planning | Next concrete action |
|---|---|---|
| SEC-01 | Open PR #901; lifecycle concerns verified | Update base, inspect current auth hardening, implement challenge lifecycle and focused regressions. |
| QA-01–QA-05 | Planned; inventory created, individual reviews pending | Start security tests and record evidence per definition/parameter group. |
| DATA-01 | Planned; previous audit needs current-code confirmation | Inspect API ordering and listing controller, then implement one shared result contract. |
| OPS-01 | Documentation exists; live acceptance not established by this roadmap | Load the continuity plan and select its first authorized unverified requirement. |
| Other IDs | Planned / verify first | Follow queue and dependency rules above. |

The repository programme is complete only when each in-scope requirement has evidence, the per-test reviews are recorded, relevant checks pass, trackers match merged state, and release claims have actual deployment evidence. Do not equate this roadmap's creation with completion of the work.

