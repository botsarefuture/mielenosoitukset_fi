# Mutation-based test review

Review one behavior group at a time. A green suite or line coverage alone does
not show that assertions detect the intended defect. Mutation testing is an
additional diagnostic, not a replacement for integration tests or human review.

## Decision — test value and maintenance cost

Accepted by the maintainer on 2026-10-24. This is the agreed review policy,
not a claim that the existing suite has already been audited. Recorded on the
isolated test-review branch; not yet merged into main.

Optimize for meaningful regression protection relative to maintenance cost,
not test count, coverage percentage or mutation score.

- Before adding a test, inspect existing coverage. Prefer extending an existing
  test when it protects the same behavior; add a separate test for a distinct,
  meaningful failure mode. Avoid sprawling tests that combine unrelated contracts.
- Test our behavior and our integration contracts with dependencies, including
  relevant failure handling. Do not duplicate external packages' internal tests.
- Assess each test's protected risk, unique coverage, ability to detect the
  intended regression, reliability, runtime, fixture/mock complexity and coupling
  to implementation details. Security-critical protection can justify higher cost.
- Review in coordinated, bounded behavior groups and record a decision of keep,
  improve, consolidate, replace or remove, with evidence and rationale in
  `test-review-inventory.md`. Each batch should consider consolidation as well
  as gaps; it does not need to add or remove tests to meet a quota.
- Do not remove useful coverage merely to reduce numbers. Consolidation must
  retain distinct scenarios. Removal must explain why the requirement is obsolete,
  belongs to a dependency, or is adequately protected by retained coverage.
- Use mutation testing to investigate assertion quality, not to justify brittle
  assertions for equivalent mutations, incidental details or speculative edge cases.

## Batch process

1. Identify the behavior, current implementation and existing tests. Start with
   permission/token boundaries, scoped queries and delivery/retry invariants,
   then ordinary workflow and UI behavior. Do not mutate an active checkout.
2. Run the unmodified tests as a control. Use an existing mutation tool, initially
   `mutmut`, on a bounded source scope. Do not rewrite the tests to make a score.
3. Inspect survivors individually. Distinguish real missing assertions, equivalent
   behavior, irrelevant diagnostic-text changes and harness/infrastructure errors.
4. Fix substantive assertion gaps, rerun controls and the mutants with a clean
   result cache, and record both results. Retain original baseline evidence.
5. Decide keep/strengthen/combine/remove for each reviewed test. Remove only after
   verifying another retained test covers the same requirement and distinguishing
   failure path. A surviving equivalent mutant does not justify deleting a test.

Do not pursue100% by asserting exact error prose, private falsey sentinels or
incidental implementation details. No blanket rule to delete static contracts:
some protect shipped assets or permissions, while others need behavioral tests.
Record the rationale in `test-review-inventory.md`.

## Integration group1 — API-token authority and revocation

Prepared2026-10-25 on main `e3aba1f8b425032cc372812bdf5f14cd1aae1a55`
in a new isolated worktree. Original audit branch remains intact at `ea3a3baa`.
Selected implementation/tests from `451e049d`, `93fb40cd`, `48f93878`; model
review dispositions from `c27604dc`. Only selected paths/sections transferred,
not a whole old-tree replacement or merge of unrelated audit work.

One production change: privileged `admin`/`mcp.admin` issuance now follows
User.has_full_permissions(), so an elevated limited admin cannot mint them.
No existing token revoked. Tests retain current main's authentication/database
integration and extend existing definitions for proof-time boundaries and exact
revocation isolation. No definitions added/removed; no repeated audit rewrite.
Templates/styles/translations and UI input/permission predicates are unchanged;
this is API-policy/test work, not a UI-design readiness claim.

Current combined validation: **39 cases passed in13.72s** across all four files:
security regressions12, step-up13, super-admin model4 and public-token manager10.
The three public-token UI/static/JS definitions are compatibility controls only;
their dispositions remain pending. Actual Flask/password/TOTP/signed WebAuthn
and exclusively owned Mongo52269; external services use normal test isolation.
Local Python3.11 does not establish supported Python3.12 hosted/full-suite CI.
`git diff --check` passed. CodeRabbit included capacity was exhausted at this
checkpoint; no new external review ran for this current-main integration.
Prior completed reviews below are historical, not a fresh zero-finding claim.

All424 main assessments preserved and sixteen existing unchecked definitions
assessed here: eight security, four authority-model and four token-manager.
Step-up's eleven prior assessments remain, with two follow-up dispositions and
the same13cases. Inventory:1,290definitions/175files/440checked,850unchecked tests
plus two supporting fixtures. No other branch's unmerged review is counted.

The remaining groups (OAuth/MCP, then Mongo/pagination/decorator controls) remain
only on the audit branch. Prepare those after this group is integrated, starting
from then-current main. Reviewed tests are reopened only for meaningful behavior
changes, integration conflicts or new evidence; keep decisions remain valid.
Do not start another independent audit batch while integration is outstanding.
No push, merge or deployment authorized. Hosted checks require publication.

Evidence: chat `work/token-integration-validation.log`; private Mongo directory
`/var/folders/h2/kxdl0cpx4tv3956j2s1k0pb40000gn/T/moso-token-integration-hrx5trt9`.
The selected reports below retain original dates/base hashes and branch counts
as historical evidence. They do not assert the other audit batches are merged
or transfer their tests/assessments into this integration head.

## Batch05 — settings privilege fields and API-token authority

Reviewed 2026-10-25 from `f901ee99`, with a clean starting worktree. The eight
existing definitions in `tests/test_security_regressions.py` and their auth
implementation matched remote main `35fd6def`; all eight remained unchecked
there. Their original real-Flask/private-Mongo control passed eight cases in
4.36s. Session fixtures authenticate a seeded user; email/upload/network effects
are stubbed by shared fixtures, so this is not actual login, mail or deployment
acceptance. These tests do not establish CSRF coverage.

### Confirmed security defect and regression improvement

The ordinary-user denial test requested a privileged token without elevation.
Its 403 could therefore come from the later step-up guard even when role checks
were absent. Inspection also found that `generate_api_token` treated every
`role='admin'` as global authority, contrary to `User.has_full_permissions()`,
`docs/api.md` and `docs/admin_mcp.md`. Limited admin access intentionally does
not imply global permission bypass.

Extended and renamed that existing definition to
`test_non_global_user_cannot_issue_privileged_token`: actual successful password
step-up and elevated-status control precede a user/admin-role × admin/mcp.admin
scope matrix. Each request must deny 403 for authority (not step_up_required)
and preserve token count. The new test reproduced the implementation defect:
**two failures/two passes** before the fix, with both limited-admin variants
receiving 200 rather than 403 and issuing real records in private test Mongo.

Fixed the route to use `current_user.has_full_permissions()` instead of its
independent role-name allowlist. Existing global-admin issuance remains covered.
No production service, previously issued token or shared data was changed;
existing tokens are not revoked by this new-issuance guard.

The malformed-scope definition now has two parametrized cases: a string instead
of a list, and a mixed string/integer list. The latter exercises item validation
rather than accidentally getting 400 from a later unknown-scope check. No new
definition was added: eight definitions now collect twelve cases (previously
eight); the renamed ordinary-denial scenario retains ordinary-user protection.

### Targeted failure evidence, not a mutation score

The decorated route is outside mutmut 3.8.0's useful scope established in Batch04,
so no further generated-mutant score was pursued. Two explicit AST faults were
applied only to the actual registered token handler in temporary pytest runs.
The login wrapper was reapplied and original view restored by monkeypatch;
request processing, session elevation, persistence and dependencies remained
real. An unchanged-handler bridge control passed before and after.

| Fault | Original eight cases | Revised twelve cases | Individual interpretation |
| --- | --- | --- | --- |
| Force privileged-role authorization True | All pass | Four authority cases fail | Real missing negative control: step-up previously masked authority bypass. |
| Skip scope shape/item guard | All pass | Mixed-list case fails | Real request-handling gap: TypeError/500 replaces required 400 for nonstring list members. |

Fresh results had no setup/collection errors or timeouts. The faults were
individually inspected and did not touch tracked source. Unknown-scope rejection
can also be enforced by our token helper; proving which layer rejects a safe
request is not worth a brittle assertion. No score-chasing tests were added.

### Individual dispositions and cost

| Definition | Decision and distinct protection | Reliability, coupling and limits |
| --- | --- | --- |
| `test_legacy_settings_rejects_privilege_fields` | Keep: role/admin/grant mass assignment denied with rejected field names; mixed allowed language also remains unchanged. | One real request/persisted user; exact machine field names are contractual. No email or arbitrary settings-field matrix. |
| `test_legacy_settings_still_updates_allowed_fields` | Keep: language/theme/city survive allowlist hardening and persist. | One small fixture/request; explicit expected fields avoid whole-document brittleness. Actual notification transport remains stubbed. |
| `test_non_global_user_cannot_issue_privileged_token` (renamed) | Improve existing: elevated user and limited-admin roles cannot issue either privileged scope. | Four real password/session/token cases; extra fixture and password-verification cost is justified by demonstrated privilege escalation. No mock role, scope or elevation answers. Does not revoke historical tokens. |
| `test_api_token_rejects_unknown_scopes` | Keep: supported read plus unsupported scope returns 400 and inserts no token. | One cheap real request/count check; does not insist on route-vs-helper rejection or exact error prose. |
| `test_api_token_rejects_malformed_scope_payload` | Improve existing: outer-list shape and member type reject 400 with no inserted token. | Two real API cases; distinct shape/item conditions, no speculative exhaustive JSON fuzzing. Detects a real handler exception when item guard is removed. |
| `test_global_admin_can_issue_mcp_admin_token` | Keep: valid authority + real password step-up permits requested scopes and persists a token for the correct user. | Positive control prevents blanket-denial fixes. No redundant token-generator hashing/entropy or external MCP transport assertions here. |
| `test_privileged_token_without_step_up_is_rejected` | Keep: an authorized admin without elevation gets machine error step_up_required and no write. | Distinct identity-freshness guard; minimal real request. Timed expiry and cross-session binding remain separate tests. |
| `test_auth_security_routes_ignore_stale_module_database_handle` | Keep: stale module handle must not control token enablement or settings persistence. | Purposeful stale-read/write double with real active Mongo confirms fresh handle use in both routes. Some allowed-settings assertions overlap the normal control, but this distinct legacy-state failure is worth retaining; no arbitrary DB outage handling claim. |

Consolidation considered: settings allow/deny, token authority, malformed/unknown
scopes, positive issuance, freshness and stale DB provenance protect different
failure modes. Combining would obscure guard interactions that caused the
observed false positive. No definition was removed or added.

### Validation and continuation

Actual unmodified-import tests for this file, `test_super_admin_permissions.py`
and `test_admin_mcp.py` passed **27 collected cases in 9.27s** against this audit's
exclusive loopback Mongo. The twelve-case unchanged-handler bridge control
passed in 5.53s. The other fifteen compatibility cases were not newly individually
assessed. CodeRabbit reviewed both changed code/test files with zero findings;
`git diff --check` passed. No full-suite, hosted Python 3.12, production rollout
or existing-token revocation claim follows from local validation.

Branch totals remain 1,258 definitions/172 files; checked inventory entries rise
from 375 to 383, leaving 875 unchecked test entries plus two supporting fixtures.
These are branch-tree inventory counts, not mutation-tested totals. Next bounded
security group: session elevation expiry/account binding and sensitive-action
entry guards in `tests/test_step_up_authentication.py`, after checking current
main and active-source overlap.

Evidence: chat `work/security_route_fault.py`, `work/run_security_route_faults.py`,
`work/batch05-before.log`, `work/batch05-red.log`, per-fault before/after logs/JSON
and `work/batch05-validation.log`. The private service is the Batch04-owned
instance; no other test process shares it.


## Batch06 — session-elevation time and actor bounds (follow-up)

Started 2026-10-25 at `451e049d`, clean worktree. Main had advanced from
`35fd6def` to `54b02c58` (city-review inbox notifications). The exact current-main
commit was fetched into the object store without updating refs or checkouts.
The step-up helper, passkey routes and test file matched main; the auth-file
difference was this branch's unmerged Batch05 token-authority fix.

All eleven definitions in `test_step_up_authentication.py` already have
individual dispositions from QA-01a. Those records were read and retained,
not counted again. This batch revisits only `test_elevation_times_out` and
`test_elevation_does_not_leak_across_sessions`: two definitions/four cases.
The prior review explicitly left future timestamps as a follow-up.

### Mutation and control scope

The existing mutmut 3.8.0 library API `mutate_file_contents` generated 34 variants
from the AST-identical `has_elevation` function alone. Original function text
and generated source were retained in scratch. Each variant was extracted and
renamed back to `has_elevation`; a scratch pytest hook compiles it into the
real step-up module's globals immediately before each test call, using
monkeypatch to restore it afterward. Real session/current-user/config/clock
and route behavior remain. Each selected variant runs in a fresh subprocess
with a 60s timeout against exclusively owned loopback Mongo, sequentially;
no cached results, shared service cleanup or tracked source mutation.

An initial harness startup imported application code before conftest configured
the environment. That control failed during startup and was retained separately;
imports were moved into the test hook before any measured run. Only the later
passing unchanged-function control and fresh variant runs are mutation evidence.
This is custom execution of mutmut-generated variants, not a `mutmut run` score
or whole-module/suite claim. No tooling was added to application dependencies.

Original assertions detected 26/34; eight survived, with no measured setup errors
or timeouts. The unmodified bridge control passed all four cases. Every survivor
was inspected individually below; no score target was used.

| Variant suffix | Change | Individual decision |
| --- | --- | --- |
| 7 | Missing user_id defaults to None instead of empty string. | Equivalent for authenticated BSON-ID actors: either missing fallback mismatches and denies/clears. Do not assert a private fallback representation. |
| 9 | Removes explicit user_id fallback, implicitly None. | Same fail-closed argument as 7; valid issued proof always supplies its actor. No new test. |
| 12 | Missing user_id defaults to XXXX. | Same actor-mismatch denial for legitimate account IDs; no new assertion justified. |
| 17 | Ignores explicit timeout_seconds in favor of configured timeout. | Unexercised optional internal branch, not globally equivalent. Source search found no shipped caller supplying an override; all routes use configured policy. Defer extra API-only testing until a real consumer needs it. |
| 23 | Missing authenticated_at defaults None instead of zero. | Would throw for malformed trusted proof rather than reject; not equivalent generally. Issuing code always supplies the timestamp and clients cannot edit signed state. No current producer/contract warrants malformed-internal-schema cases solely for this mutation. |
| 25 | Removes explicit timestamp fallback, implicitly None. | Same unsupported missing-timestamp branch as 23. Keep legitimate proof bounds; no speculative schema fuzzing. |
| 28 | Missing timestamp defaults 1 instead of 0. | Both values expire under actual 10/900-second policy at current epochs; valid issued timestamps are untouched. Not a useful private-sentinel assertion. |
| 30 | Changes age < 0 to age <= 0. | Real missing lower-bound assertion: a proof just created at the same clock reading must remain valid. Improve the existing expiry definition. |

Variant 31 (age < 1) was already detected by the original actor-binding test's
fresh original-session control; subsecond validity was covered, exact-zero
validity was not. The other detected variants changed actual owner, state,
time/configuration calculations or allow/deny results; test-call failures were
checked separately from setup/collection failures.

The existing expiry definition now requires a successful protected request at
age 0, retains the inclusive 10/900 upper boundary and just-after expiry checks,
and re-elevates before a 0.001s backwards clock adjustment. That future-dated proof
must deny/clear sudo while retaining the authenticated user. No extra definition
or parametrized case was added. Only the step-up module clock is replaced;
cookie signing/TOTP clocks remain real. Production behavior did not change.

A separate deliberate fault removes only the negative-age guard. The original
four-case selection passed under that fault, confirming the documented gap.
It is a manually chosen control, not one of the 34 generated variants.

### Fresh validation results

| Run | Selected definitions / control cases | Generated variants | Detected | Survived | Measured harness errors/timeouts |
| --- | --- | ---: | ---: | ---: | ---: |
| Original assertions | 2 / 4 | 34 | 26 | 8 | 0 |
| Improved expiry definition | 2 / 4 | 34 | 27 | 7 | 0 |

All seven remaining suffixes (7, 9, 12, 17, 23, 25, 28) retain the individual rationale
above. Exact-zero mutant 30 now fails the immediate-success assertion (403 rather
than 200). The separate removed-future-guard fault now fails the negative-age
assertion (200 rather than 403), after passing the original tests. Selected runs
use `-x`: four cases is the passing control/selection count, not a claim that all
four execute after an earlier killing failure. Measured nonzero runs were all
test-call failures, not setup errors. Original/final sweeps including controls
took 116.05s/115.39s; the four-case pytest controls were 3.30s/3.50s (single-run
observations, not a performance benchmark).

Real-import validation without the bridge ran the complete step-up file and
`test_super_admin_permissions.py`: 17 cases passed in 6.07s. That comprises the
same eleven-definition/thirteen-case step-up inventory plus four global
model controls; only two step-up definitions are revisited in Batch06. CodeRabbit
completed review of the changed test file with zero findings. `git diff --check`
passed. No new assessment count, definition or collected case is added; no
production source changed. Shared fixture cleanup was confined to private Mongo.
Local Python 3.11 validation does not replace supported Python 3.12 hosted CI.

### Dispositions and maintenance rationale

- `test_elevation_times_out`: improve existing. Inclusive lower/upper bounds,
  immediate usability and fail-closed backwards-clock behavior are one temporal
  contract. Three additional local requests per configured window add no fixture,
  sleep or dependency mock. Preserve real login across invalidation. Config
  parsing and malformed trusted proof remain separate, not exhaustive coverage.
- `test_elevation_does_not_leak_across_sessions`: keep unchanged. Same-account
  separate cookie jar plus foreign-account copied proof protect distinct session
  and owner boundaries. Real owner checks and active original-session positive
  control detect over-denial. No claim that copied cookies for the same account
  are safe. Existing fixture cost is justified by authentication isolation.

No consolidation/removal: time invalidation and session/actor isolation protect
different risks. The other nine existing step-up dispositions are retained as
prior evidence, not re-reviewed in this bounded mutation selection.

Evidence: chat `work/generate_stepup_mutants.py`, `work/run_stepup_mutations.py`,
`work/stepup_mutation_bridge.py`; private directory
`/var/folders/h2/kxdl0cpx4tv3956j2s1k0pb40000gn/T/moso-stepup-batch06-qkz66q9j`
contains original/generator/variant sources, per-run logs and JSON. Initial
startup error is separate from measured results.


## Batch07 — global-authority model contracts

Reviewed 2026-10-25 after `93fb40cd`. Four definitions in
`tests/test_super_admin_permissions.py` remained unchecked on this branch and
current remote-main snapshot `54b02c58`. Tests and `users/models.py` matched that
snapshot. Read `has_full_permissions`, `_perm_in`, `has_permission`,
`has_scoped_permission`, User construction/loading and lazy membership/grant
queries before dispositioning these cases. No test or production edit justified.

Supporting `_user` constructs a real User with empty explicit permissions,
a valid fresh BSON ID and an unused password hash. These are permission-model
contracts, not primary-login/password-hashing tests or tests of BSON internals.
Full-authority paths short-circuit backend lookups; the ordinary negative can
read an empty membership collection via the current private database. There is
no permission-method mock or network provider. Random ID identity itself is
not asserted, and no wall clock, scheduler, sleeps or broad shared fixture is
needed beyond existing test configuration/client ownership.

| Definition | Decision and unique regression value | Cost/coupling and limits |
| --- | --- | --- |
| `test_global_admin_flag_grants_every_permission_scope` | Keep: full flag on ordinary base role grants arbitrary future, organization and city permissions; scope enumeration returns global. | One real model, four semantic checks. `_perm_in` result is an application integration contract used by approval/scope consumers, not an incidental private representation. No actual HTTP route, membership write or every possible scoped backend. |
| `test_super_admin_roles_grant_every_permission` | Keep: each global_admin/god/superuser role works without the explicit full flag. | One collected case iterates three roles; cheap constructors and early policy return. Distinct role-based alternative from flag test. Not an exhaustive deny-role matrix. |
| `test_god_role_also_enables_legacy_global_admin_checks_when_loaded` | Keep: persisted legacy god role loads with a true global flag and arbitrary permission succeeds. | Real loader/constructor, no Mongo write. Flag assertion catches a compatibility loss that role-based modern permission checks alone would hide. Does not prove migrations or all legacy roles. |
| `test_regular_user_still_needs_an_explicit_permission` | Keep: an ordinary user with no grants does not receive arbitrary permission. | Small real empty-membership lookup, complementary negative control. Does not demonstrate granted permissions or denial of every limited-admin role. Those are separate application tests, not implied by this name. |

No consolidation: explicit flag, role allowlist, legacy loader adaptation and
ordinary denial fail independently. Combining would need heterogeneous setup
and hide the loader-specific flag check; no removal warranted. No extra
assertions or parameter cases are needed merely to expand a per-file score.

### Evidence and limits

The unmodified four model cases passed as part of the current-head 17-case
step-up/model run in 6.07s (Batch06 validation log). One scoped runtime fault then
broadened `User.has_full_permissions` to include the limited admin role. The
four model cases still passed; of the four retained Batch05 non-global token
cases, exactly the two limited-admin cases failed with 200 rather than 403.
Result: two intended failures/six passes in 3.40s, no setup/collection errors.
This verifies cross-file regression protection while explicitly documenting the
model file's limited negative selection. It does not establish that every
current/future authorization consumer is safe.

The fault used a temporary pytest monkeypatch in a fresh process, with actual
Flask/Mongo for the route cases; no tracked source changed. This is one explicit
risk control, not a mutmut-generated score. Repeating the API denial matrix in
each model consumer would add maintenance without a new failure signal in this
batch. Evidence: chat `work/global_role_fault.py`, `work/batch07-role-fault.log`
and `work/batch06-07-validation.log`. Only exclusively owned Mongo was touched.
`git diff --check` passed. No code changed, so no additional code review or
hosted/full-suite claim is made from this documentation-only batch.

Branch inventory now has 387 checked test definitions and 871 unchecked, plus
two unchecked supporting fixtures; total 1,258 definitions/172 files unchanged.
Prior records and newer main-only assessments still require reconciliation
before suite completion. Next unchecked security group: the eleven Admin MCP
protocol/tool definitions, using their existing local transport and scope
fixtures. Recheck current main before editing. Goal remains active.


## Batch12 — Public token authentication and revocation isolation

Reviewed 2026-10-25 from `e3ed9d94`; main still `e3aba1f8`. Read actual token
routes/login wrappers, creation scope validation, owner-filtered delete, stored
credential creation/verification and four existing selected tests. The other
three UI/source/JavaScript definitions in this file remain individually pending.
No production implementation or rendered UI changed.

Before edits a temporary narrow Collection.delete_one wrapper performed the
real requested deletion, additionally deleted that owner's other tokens, then
returned the original real acknowledgment. No invented result or auth stub;
patch restored by pytest. **All four selected original cases passed in2.94s**.
With strengthened tests the same fault fails both revocation definitions at
exact unchanged-neighbour snapshot assertions; five other selected cases pass,
three UI cases deselected (4.14s). The failure is assertion evidence, not setup
or timeout. This explicit over-deletion fault is not a mutmut-generated score.
Existing foreign-token denial already guarded removal of the owner predicate;
the gap was collateral deletion despite the expected status/target result.

| Existing definition | Decision / meaningful protection | Uniqueness, cost and coupling |
| --- | --- | --- |
| `test_token_manager_requires_authentication` | Improve/keep: anonymous UI, credential list, create and revoke requests all redirect to the internal login route without changing any credential. | Four route cases share one definition. Valid revoke target and create payload avoid malformed input masking auth; real Flask-Login and seeded data. Parsed path/authority replaces substring redirect match. More setup justified by independently registered read/write guards. Does not prove all account routes or primary login security. |
| `test_token_creation_rejects_malformed_scopes_with_localized_error` | Improve/keep: malformed string scopes deny400 with localized Finnish error and leave tokens unchanged. | One case; existing exact copy is intentionally a localized response contract, distinct from Batch05's broader shape/authority checks. Snapshot adds one small read pair, catches credential creation before denial. No extra shape matrix copied here; if editorial copy changes this assertion must change. |
| `test_token_revoke_rejects_invalid_and_foreign_ids` | Improve/keep: invalid identifier denies400, another user's real token denies404, all records unchanged. | Both existing requests share one app. Existing localized error expectations retained, foreign nonexistence semantics hide ownership. Whole snapshot protects caller's credentials too; not only the foreign target. Not every ID shape, unknown ID or CSRF policy. |
| `test_token_revoke_deletes_only_the_current_users_token` | Improve/keep: a real usable target is revoked, its raw credential becomes401/token_invalid, all other records unchanged and a same-owner spare remains usable. | Two actual create/check helper calls replace reliance on unusable seeded token strings. Real persisted hashes/deletion/verification; no entropy/hash internals asserted. Same-owner and foreign neighbours coexist. Whole retained-record equality is meaningful forbidden mutation protection; removes exact success-message prose while retaining machine status. |

No definitions added or removed. Consolidation considered: login, malformed
creation, owner denial and successful revocation have different failure modes;
combining them would mask authorization or positive credential validity. Reuse
existing scenarios instead. Two real new credentials in the positive setup are
worth the small cost to distinguish usability from deletion of a dummy record.
No timing/sleep, exact expiration-time or callback count assertions added.

Normal **46 cases passed in18.91s**: complete public-token manager10 cases
(seven definitions) plus MCP36 cases (eighteen definitions). Three unchanged UI
compatibility cases passed but are not newly assessed. All data used owned
Mongo65327; Python3.11 is not supported Python3.12 hosted/full-suite proof.
`git diff --check` passed. Combined CodeRabbit review from `ff20f09b`
completed across the five Batch11–12 files with zero findings. Included
capacity only; no paid credit or credential changes. Focused review is not
a whole-repository security or hosted integration gate.

Branch counts: **1,265 definitions /172 files /409 checked**; **856 unchecked
tests plus two unchecked supporting fixtures**. Four previously unchecked
definitions gain dispositions; new route variants are cases, not definitions.
Main integration/count reconciliation remains pending. Next priorities include
permission-scoped admin magic-token listing/revocation, pagination bounds and
core workflows; remaining OAuth request-validation gaps are explicit backlog,
not evidence for a complete protocol audit.

Evidence: chat `work/token_revoke_fault.py`, `work/batch12-before-fault.log`,
`work/batch12-after-fault.log`, `work/batch12-validation.log`; private service
continued sequentially from Batch11, never shared with another task.
