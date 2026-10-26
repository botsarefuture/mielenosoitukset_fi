# Mutation-based test review

Review one behavior group at a time. A green suite or line coverage alone does
not show that assertions detect the intended defect. Mutation testing is an
additional diagnostic, not a replacement for integration tests or human review.

## Decision — test value and maintenance cost

Accepted by the maintainer on 2026-10-24. This is the agreed review policy,
not a claim that the existing suite has already been audited. Recorded on the
isolated test-review branch and introduced into main with Group1/PR#981.
The earlier batch records retain their original scope and measurements.

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

## Integration Group 2 — OAuth/MCP security contracts

Prepared locally on main `d524fe0b36a1915ed7489f9870b645aae1650b9b` after
Group1/PR#981 merged and its deployment was verified. Selected implementation,
consent template, tests and API documentation from `c96cebac`, `3089fac2`,
`ff20f09b`, `e3ed9d94`; no publication/merge/deployment authorization for Group2.
The full suite-review goal remains incomplete. No new audit batch is opened.

Main independently gained MCP event-editing/image-upload features. Three-way
application required resolving only test imports (retain io/PIL/storage plus
new security helpers). All14 new main test ASTs are unchanged, as are the TOOLS
registry and every implementation function except the intended authentication,
authority, consent, token exchange and RPC error handlers. No stale whole-file
copy, reset/stash or shared-environment cleanup.

Preserve the accepted full-global OAuth consent policy; GET and POST recheck
current authority. Add session-bound CSRF proof to real consent, omit credential
fragments from debug logs, return structured scope403 errors, and conditionally
consume unused/unexpired authorization codes before issuing one token. Existing
signed/PKCE/client/redirect checks remain. New consent input is hidden; no visual
redesign, dependency addition, token revocation or external issuer claim.

Existing tests are extended where they share behavior. Seven distinct negative
security definitions from the audit accompany existing positive controls; no
unrelated new main test is rewritten. **74 focused cases passed in26.88s**:
complete MCP file68 cases/32definitions plus six unchanged moderation helpers.
Of those32 definitions,18 have individual Batch08–11 dispositions; the14 newer
main definitions/32cases are compatibility evidence only, not assessed here.
Private loopback Mongo65372 and local Python3.11; not hosted Python3.12 CI or
whole-suite proof. `git diff --cached --check` passed after import resolution.

Inventory reconciled additively:1,311definitions/175files/458assessed,
853unchecked tests plus two supporting fixtures. All440 previous main assessed
names and every unrelated inventory section are retained. The14 new main MCP
names previously missing from the inventory are now pending, not silently
removed or counted as reviewed. Original batch counts below remain historical.

Visual acceptance: real app before/after consent captures use390/1440px, light/
dark browser preferences, long fixture client name, keyboard-focus control and
restricted-admin403 state. The existing standalone inline template has fixed
light colors and no external resources; dark preference behavior is unchanged,
not claimed as a new full-theme implementation. Independent reviewer `/root/visual_mcp_consent`
opened all14 before/after images and returned **SHIP** for these states. It
acknowledged the existing inline/fixed-light design, subtle focus outline and
plain English403 response rather than certifying full shared-design compliance.
The final handler/template/test/docs source hashes and all image hashes were
reverified unchanged against `outputs/mcp-consent-visual/review-packet.json`;
verdict recorded in `visual-review.md`. No rendering source changed afterward.

Fresh CodeRabbit uncommitted review completed across all seven Group2 files
with zero findings. Included capacity only; no paid credit or credential change.
Both independent visual and code reviews are complete for this local snapshot.
Only documentation records were finalized afterward; no new code/test changes.
Group2 hosted CI remains pending publication. Publication/merge/deployment need separate authorization after local
readiness; Group1-only authorization is not reused for this group.

Evidence: chat `work/mcp-integration-validation.log`, before/after capture logs,
`outputs/mcp-consent-visual/`. Private Mongo service directory:
`/var/folders/h2/kxdl0cpx4tv3956j2s1k0pb40000gn/T/moso-mcp-integration-fa1z6k4a`.

## Batch08 — OAuth MCP discovery and consent

Reviewed 2026-10-25 from `c27604dc`, clean starting worktree. A read-only remote
lookup still found main at `54b02c58`; MCP source/tests matched that snapshot.
The original eleven MCP cases passed in 5.51s on exclusively owned loopback
Mongo. This batch individually assesses only the two discovery/registration-
consent definitions plus two new, distinct consent-security definitions. The
remaining nine existing MCP definitions are compatibility controls for now.

### Policy decision and confirmed request forgery

A real consent POST with no CSRF proof initially returned 302 and created an
authorization code. Added a session token rendered as a hidden consent-form
field and validated with a constant-time byte comparison before accepting
POST data. Missing, wrong, non-ASCII wrong and another browser session's proof
must all deny 403 without creating a code; same-session rendered proof permits an explicit denial without a code and
then a successful approval.
Byte comparison keeps malformed Unicode input on the rejection path rather
than raising an exception. No exact token value or randomness implementation
is asserted.

The legacy OAuth documentation explicitly allowed the admin role, unlike the
newer full-authority model/API-token policy. This was treated as a maintainer
policy conflict rather than silently redefining its tests. The maintainer chose
**require full global authority** on 2026-10-25. Applied the previously tested
proposal: authenticated consent GET and POST now use User.has_full_permissions(),
and docs/admin_mcp.md records the new rule and CSRF requirement. A limited admin
retains no exception. A valid rendered CSRF token from before authority loss
cannot authorize a later grant. The user/admin downgrade cases require both
GET and POST 403 and no authorization-code write. Under the prior role policy,
the limited-admin case reproduced GET 200 instead of 403 (one failure/one pass).
Existing tokens or authorization codes are not revoked by these consent guards.

### Individual dispositions

| Definition | Decision and meaningful protection | Reliability, cost/coupling and limits |
| --- | --- | --- |
| `test_admin_mcp_oauth_metadata_advertises_registration_and_pkce` | Improve fixture cost: retain actual discovery/resource responses, advertised endpoint paths and S256 support; remove unused seeded-data fixture. | Real app/config/routes, no need for full user/demo database seeding. Does not prove PKCE validation, external issuer reachability or all metadata fields. No assertion added merely for count. |
| `test_admin_mcp_dynamic_client_registration_and_oauth_code_flow` | Improve existing: share actual client-registration setup and return the rendered CSRF field in consent; retain state, token and usable MCP catalog checks. | Real registration, session, PKCE derivation/exchange and JWT use; localhost app never follows the external callback. Client name plus real form replaces brittle consent-heading prose. Positive flow alone does not establish replay, wrong-verifier, redirect/client binding or concurrent consumption. |
| `test_admin_mcp_oauth_consent_requires_csrf` (new) | Add/keep: all four invalid/missing proof situations preserve code count; rendered same-session proof supports denial without a code and approval. | One real registered client and two cookie jars for the same global actor. Distinct browser-forgery risk warrants its own definition, rather than conflating authority with CSRF. Not general session theft/logout-token rotation coverage. |
| `test_admin_mcp_oauth_consent_rechecks_global_authority` (new) | Add/keep: after real DB downgrade, user and limited-admin roles cannot view or POST consent, even with a previously valid CSRF proof. | Two parametrized cases, no authorization mock. Prior authorized GET is a positive control and provides genuine proof, preventing CSRF denial from masking broken POST authority. It implements the maintainer's explicit new policy, not a universal OAuth role rule. |

`_registered_oauth_client` factors exactly the pre-existing registration request
for three scenarios; it does not mock registration, persistence, authority or
JWT processing. Existing app_factory disables background jobs and external
side effects. Distinct discovery, positive credential flow, browser proof and
current authority cannot be consolidated without hiding different failures.
No test removed; two definitions/three collected cases added. The file now has
thirteen definitions/fourteen cases; four definitions are individually assessed
in Batch08, not all thirteen.

### Validation, limits and follow-up

The revised complete MCP file passed 14 cases after both guards were applied;
final run including legitimate denial/approval and fixture refinement passed
14 cases in 6.74s. `git diff --check` passed. Local review checked GET/POST ordering, real
current User policy, form token rendering and byte comparison. CodeRabbit was
attempted but the service rejected the review for exhausted included capacity
and an unassigned organization seat; **no external review ran**, and it is not
reported as zero findings. No retry/credit purchase or credential change was made.
Local Python 3.11/private-Mongo evidence is not hosted Python 3.12/full-suite proof.

OAuth code exchange still needs bounded negative PKCE/redirect/replay tests.
Static inspection found separate code lookup/update, so single-use concurrency
must be verified rather than inferred from the happy path. These are explicit
next security work, not completed protection. Remaining bearer and tool scopes
are the next nine-definition group, including required OAuth scope failures
and credential handling in logs. No production traffic or shared data touched.

Branch totals: 1,260 definitions/172 files, 391 checked and 869 unchecked test
entries plus two supporting fixtures. The two existing and two new individual
assessments add four checked entries; prior/source-only main reconciliation is
still outstanding. Goal remains active.

Evidence: chat `work/batch08-before.log`, `work/batch08-csrf-red.log`,
`work/batch08-authority-red.log`, `work/batch08-validation.log`,
`work/batch08-validation-final.log` and the accepted local policy proposal in
`work/mcp-consent-authority-proposal.json`. Private service directory:
`/var/folders/h2/kxdl0cpx4tv3956j2s1k0pb40000gn/T/moso-mcp-batch08-8njlfy7r`.


## Batch09 — MCP bearer failures and read/write workflow contracts

Reviewed 2026-10-25 from `c96cebac`, clean worktree. Remote main remained
`54b02c58`; differences in this module were the accepted Batch08 consent
changes. Read the token authentication adapters, scope gate, RPC dispatcher,
list query and three mutation handlers plus Case.add_action persistence before
reviewing the remaining nine existing MCP definitions. Two distinct negative
definitions were warranted; no new positive workflow definition was added.

### Real failures and bounded controls

The existing fourteen MCP cases had passed on the unchanged implementation.
Before edits, deliberately bypassing only write checks or dropping successful
RPC response IDs still passed all fourteen. Ignoring search passed the selected
search definition; clearing existing case action history passed the selected
note definition. These are four explicit temporary pytest monkeypatch controls,
not mutmut-generated mutants or a module score. Authentication, remaining
scope checks, Flask and private Mongo remained real. Each fault ran in a fresh
process; patches restored on teardown, no tracked implementation mutation.

Extended controls then exposed two actual implementation failures:

- Enabling debug capture on the existing catalog flow found the first twenty
  credential characters in application logs. Removed the value/prefix from that
  authentication diagnostic; no log-format assertion or entropy/timing test added.
- A correctly signed OAuth token missing configured mcp.admin raised an uncaught
  PermissionError before the RPC permission handler. Four other negative JWT
  cases already rejected correctly. Moved authentication into the existing
  PermissionError boundary so a scope denial returns 403 / RPC -32003 with the
  original request ID. Invalid credentials remain 401; no grant was broadened.

The red run had two expected failures/four passes: credential-prefix capture
and missing-required-scope; no setup/collection failure. The added JWT cases
exercise our verification-key/issuer/audience/expiry/scope integration contract,
not PyJWT's cryptographic internals. No extra mutmut run was justified alongside
these concrete failures and bounded fault controls.

| Deliberate fault | Before | After | Meaningful missing assertion |
| --- | --- | --- | --- |
| Bypass only write scope | 14/14 pass | Three read-only cases fail, 22 pass | Valid read access must not mutate case/org/demo targets. |
| Force successful RPC id to None | 14/14 pass | Catalog case fails, 24 pass | Correlation IDs survive initialize and catalog responses. |
| Drop the search argument | Selected search case passes | Selected case fails | A nonmatching seeded demonstration must be excluded; filtered count also checked normally. |
| Replace case logs with only the new action | Selected note case passes | Selected case fails | Append must preserve the prior nonempty audit prefix. |

After-fault nonzero results were inspected as intended test-call failures, not
harness errors/timeouts. The new negative definitions cover different risks
from successful writes and OAuth acceptance; preserving only the positive cases
would leave precisely the observed blind spots.

### Individual dispositions and maintenance cost

Shared helpers keep existing defaults/callers: static tokens still have read+
write unless an explicit scope list is passed; the OAuth helper optionally
changes signed claims/key while server verification config stays fixed. Real
Flask/session/config/Mongo are retained; external mail/upload/jobs use existing
fixture isolation. No authorization/JWT verification/write-result mock is used
in normal controls. Parameter variants share a definition instead of multiplying
fixture-heavy definitions.

| Definition | Decision / unique protection | Reliability, fixture cost, coupling and limits |
| --- | --- | --- |
| `test_admin_mcp_requires_bearer_token` | Improve existing: missing, unknown and non-Bearer credentials deny 401 with machine RPC error, matching ID and Bearer challenge. | Three cases; includes the valid configured key in an unsupported header scheme. Real auth adapters; replaces exact English error prose. Not every malformed header or disabled-server configuration. |
| `test_admin_mcp_lists_tools` | Improve existing: non-default IDs correlate initialize/catalog; core tool subset remains available and credential/prefix absent from debug capture. | Same two requests and existing app; built-in caplog only. Stable protocol IDs/tool subset, no exact catalog order or diagnostic wording. Logging check covers this configured-token flow, not every production sink. |
| `test_admin_mcp_accepts_oauth_bearer_tokens` | Keep: configured external issuer/key/audience and required scope allow real signed bearer catalog access. | Synthetic locally signed HS256 JWT, real decoder/adapter; not external issuer/TLS/key rotation or a mandatory-claims policy. Negative failures are separate below. |
| `test_admin_mcp_accepts_existing_api_tokens` | Keep: actual persisted/hash-checked API credential with mcp.admin reaches catalog. | Real application token creation/storage, no auth stub. Does not retest entropy or cover issuer authorization, expiry boundaries or revocation policy. |
| `test_admin_mcp_rejects_api_token_without_mcp_scope` (renamed) | Improve existing ordinary-token denial: read/write and admin-only API scopes both deny 403/-32003 without mcp.admin. | Two cases, actual records via internal helper intentionally construct scopes; not a claim ordinary users can mint privileged scopes through the public issuer. Removes exact diagnostic text coupling. Static legacy admin scope remains a different documented auth source. |
| `test_admin_mcp_can_search_demos` | Improve existing: retained matching ID, explicit nonmatching seeded ID exclusion and filtered total 1. | Reuses existing three-record fixture, no new insert or query mock. Catches ignored filter; not all search fields, regex/resource bounds, ordering or visibility combinations. |
| `test_admin_mcp_can_add_case_note` | Improve existing: exact note/actor, internal_note type and preserved prior action prefix. | One additional pre-read, real Case persistence; exact retained audit data is meaningful history integrity. No timestamp equality to now, trusted-actor-provenance or concurrency claim. |
| `test_admin_mcp_can_update_organization` | Keep: successful write persists requested website on target org. | Small actual patch/query; pairs with read-only denial. Not every allowed field, malformed patch or side-effect/transaction matrix. |
| `test_admin_mcp_can_create_demo` | Keep: valid content creates real record found through returned ID with title/city intact. | Real model/save, fixed date remains legitimate historical content. Moderation/pending-state coverage is retained separately; no extra identical creation test. |
| `test_admin_mcp_rejects_invalid_oauth_bearer` (new) | Add/keep: wrong signature/issuer/audience/expired claim deny 401; missing required scope denies403; errors correlate and no result leaks. | Five cases, shared signed-token helper and live route. Expiry uses epoch 1, no sleep/boundary race. Tests our dependency options/error integration, not JWT internals or exhaustive algorithms/claim types. |
| `test_admin_mcp_read_only_token_cannot_mutate` (new) | Add/keep: authenticated read succeeds, valid case/org/demo writes deny 403 and target documents/count stay unchanged. | Three parametrized tool families; no permission/mock write answers. Whole-target equality deliberately protects forbidden content/timestamp writes, not incidental success formatting. Does not imply every MCP tool has been individually permission-tested. |

Consolidation considered: protocol authentication, delegated scope, filtered
reads, audit append and two creation/update workflows protect different failures.
Combining positives and permission negatives would obscure masking, as earlier
batches demonstrated. Reused fixtures/scenario helpers; no definition removed.
Existing plain denial renamed to describe the actual missing MCP scope. The
file now has 15 definitions/25 collected cases; Batch09 assesses eleven
definitions (nine existing plus two new), not twenty-five definitions.

### Validation and remaining work

Normal current-head control: **31 cases passed in 12.73s** — 25 in the complete
MCP file and six unchanged creation/content-moderation helper-compatibility
cases. The six were not newly individually assessed; they verify shared helper
defaults retain pending creation and moderation exclusion. All data used an
exclusively owned loopback Mongo; teardown could not affect another test task.
`git diff --check` passed. Local Python 3.11 is not the supported Python 3.12
hosted/full-suite gate, and synthetic JWTs are not external provider acceptance.

CodeRabbit included capacity returned after the Batch08 quota rejection. One
combined review from `c27604dc` completed across the seven changed files for
Batch08 and Batch09. It reported one **minor** inventory finding: the reviewed
documentation snapshot lacked the two new definitions and still showed the
historical 13/14 counts. Current Batch09 entries already listed both definitions;
the section now leads with 15 definitions/25 cases and labels Batch08 as history.
An AST/checklist comparison verified all fifteen current names and full branch
counts after that correction. No code findings were reported; this is not a
whole-repository security review, and no paid credit or credential change occurred.

Branch inventory becomes 1,262 definitions/172 files, 402 checked and 860 unchecked
test entries plus two supporting fixtures. All fifteen current MCP definitions
now have individual dispositions, with explicit limits. OAuth authorization-code
PKCE/redirect/client binding, expiry, sequential replay and atomic consumption
remain next bounded security work; the happy-path consent flow does not prove
those. Do not treat this module's dispositions as suite completion.

Evidence: chat `work/mcp_scope_fault.py`, `work/run_mcp_scope_faults.py`, before/
after write_bypass and wrong_response_id logs/JSON, selected ignored_search and
drop_case_history logs, `work/batch09-red.log` and `work/batch09-validation.log`.
Private service directory:
`/var/folders/h2/kxdl0cpx4tv3956j2s1k0pb40000gn/T/moso-mcp-batch09-hzbtkvs_`.


## Batch10 — OAuth authorization-code binding and single consumption

Reviewed 2026-10-25 from `3089fac2`, initially clean. Remote main advanced to
`e3aba1f8` during this batch; fetched that exact object without updating another
checkout/ref. Relative to `54b02c58`, changes concern case reply history and
visual QA, not MCP implementation/tests. Its new test/inventory assessments are
not silently added to this branch's totals; main reconciliation remains work.
Read client authentication, code storage, consent, token issuance and existing
happy flow. This batch reviews that existing flow again and two new distinct
negative definitions; it does not reopen all previously assessed MCP cases.

### Evidence and implementation

Factored the existing actual registration/login/CSRF/approval path into one
helper reused by the positive and new negatives. It retains state echo,
registered-name rendering, successful bearer use and real Mongo. Sequential
replay extends the existing happy flow rather than adding another definition.
Six negative cases cover wrong/missing S256 verifier, redirect mismatch, another
registered public client, expired and unknown code. Each rejects without an
access token or consumed stored code; all except the deliberately expired code
then exchange legitimately. The second client is really registered, so an
invalid-client rejection cannot mask a missing code/client binding check.

The concurrency control uses two independent Flask clients in two threads. A
bounded barrier releases only after both actual Mongo lookups have returned
the same unused code. Only scheduling of this narrow Collection.find_one query
is instrumented; results and writes are real, with the patch restored by pytest.
Original implementation: seven selected cases passed, concurrency failed with
**[200, 200] instead of [200, 400]**. This was an assertion failure, not a timeout
or setup error. Existing positive coverage therefore missed a real replay race.

Consumption now conditionally updates only an unused, still-valid code and
checks matched_count before issuing the JWT. The earlier client/redirect/PKCE
checks remain; a failed conditional consume returns invalid_grant. The expiry
condition retains legacy missing-expiry behavior; new codes always carry expiry.
This is one-document atomic consumption, not a cross-service transaction or
revocation of previously issued tokens. Failure after consumption may require
starting a fresh authorization; this batch does not claim crash-safe delivery.

| Definition | Disposition / regression | Cost, reliability and coupling |
| --- | --- | --- |
| `test_admin_mcp_dynamic_client_registration_and_oauth_code_flow` | Improve existing: preserve registration → approval → exchange → bearer use; add sequential replay denial with no access token. | One extra request; helper extraction retains original assertions. Real private Mongo and JWT. No duplicate positive test, no exact English error text. |
| `test_admin_mcp_oauth_code_rejects_invalid_exchange` | Add/keep six parametrized cases for code proof, client/redirect binding, expiry and unknown code, including nonconsumption after denial. | Shared real consent setup; one real extra client only in that case. Fixed past expiry, no sleeps or wall-clock equality. Distinct security risks justify setup cost; not all confidential-client credentials, plain PKCE, mandatory-PKCE policy or malformed input types. |
| `test_admin_mcp_oauth_code_consumption_is_atomic` | Add/keep deterministic overlapping exchanges: exactly one token response and one invalid_grant. | Two real clients/threads, one narrow scheduling patch and a ten-second barrier timeout. Higher implementation coupling to the lookup is justified by reproduced security failure; a future lookup redesign must adapt the orchestration. Does not mock write acknowledgements, prove multi-region/crash behavior or rely on lucky thread timing. |

Consolidation: replay extends the successful flow; negatives share one definition
with six cases. Concurrency remains separate because coordinating interleaving
has different fixture cost and failure diagnosis. No tests removed. No extra
mutmut run: the directly reproduced race and explicit normal controls give
useful evidence without a broad generated-module score. Batch01/02 mutation
environment still exists, but no tooling added to production dependencies.

### Validation and limits

Complete MCP file: **32 cases passed in 14.52s**, now **17 definitions**. Two
additional fresh-process repetitions of the atomic-consumption case also passed;
these are reliability checks, not extra definitions or cases in that file total.
All used the exclusively owned loopback Mongo at 127.0.0.1:58653; no shared DB
cleanup. Local Python 3.11 evidence is not hosted Python 3.12/full-suite proof.
`git diff --check` passed. CodeRabbit uncommitted review completed across all
five changed files with zero findings; no paid credit or credential change.
This focused review is not a whole-repository security or integration audit.

Branch inventory: **1,264 definitions /172 files /404 checked**, with **860
unchecked tests plus two unchecked supporting fixtures**. Two new definitions
are assessed; revisiting the existing flow does not double-count it. Current
main's additional tests/assessments still need integration reconciliation. Next
bounded security work: confidential client authentication and registration /
authorization request validation, followed by resource bounds and permission-
scoped reads. No claim all OAuth/MCP security or suite quality is complete.

Evidence: chat `work/batch10-red.log`, `work/batch10-validation.log`,
`work/batch10-race-repeat-1.log`, `work/batch10-race-repeat-2.log`. Private Mongo
service retained from Batch09 for these sequential runs, not shared with agents.


## Batch11 — OAuth confidential-client secret contract

Reviewed 2026-10-25 from clean `ff20f09b`; remote main unchanged at `e3aba1f8`.
Read registration secret generation/hash storage, client resolution and secret
verification, metadata and current tests. This group follows Batch10 without
claiming a complete OAuth protocol or registration-input audit.

A temporary pytest fixture bypassed only confidential-client secret checking
for actual known clients; unknown-client and public-client handling remained
real. All **32 prior MCP cases passed** under that fault (13.38s). After the
changes the same fault caused exactly the two new negative cases to fail
(34 other cases passed, 14.89s): missing secret yielded200 instead of401.
No timeout/setup failure was counted. This is one explicit hand-seeded fault,
not a generated mutmut score. A preliminary wrong-path plugin startup was
corrected before these results and contributes no behavioral evidence.

| Definition | Disposition and unique risk | Maintenance cost / limits |
| --- | --- | --- |
| `test_admin_mcp_dynamic_client_registration_and_oauth_code_flow` | Improve existing: same positive registration/consent/exchange/bearer/replay flow now parametrized for public, POST-secret and Basic-secret clients. | Three cases in one definition. Shared helper sends actual secret form/header; Basic positive removes form client_id to require parsing the real header identity. Preserves all original flow assertions; no three copied workflows. |
| `test_admin_mcp_oauth_confidential_client_requires_secret` | Add/keep: two confidential methods reject missing and wrong secret with401/invalid_client, no token or code consumption; correct secret then exchanges that same code. | Two collected cases, each missing → wrong → valid sequence reuses setup/code to prove nonconsumption, avoiding six fixture-heavy copies. Actual stored client/code and real hash comparison, no auth mock normally. Distinct failure from bearer validity and code/PKCE proof. |

Only tests/helpers changed; implementation already enforced this contract. No
separate success definition, removal or production dependency added. Real
Flask/Mongo/JWT controls: **36 cases passed in16.33s**, **18 definitions** in the
MCP file. `git diff --check` passed. Private Mongo65327, local Python3.11; not
hosted Python3.12/full-suite proof, OAuth conformance, secret transport TLS or
key rotation. Exact method-mismatch policy, registration redirect validation
and authorization-input failures remain unreviewed; no speculative stricter
policy introduced. The combined Batch11–12 review recorded below completed
across all five changed files with zero findings.

Branch counts: **1,265 definitions /172 files /405 checked**, with860 unchecked
tests plus two supporting fixtures. One new assessed definition; revisiting the
existing positive definition does not increase checked count again. Next use
existing token-owner/revocation tests to advance the unchecked inventory rather
than expand the OAuth matrix without a demonstrated need.

Evidence: chat `work/mcp_client_auth_fault.py`, `work/batch11-before-fault.log`,
`work/batch11-after-fault.log`, `work/batch11-validation.log`. Owned Mongo:
`/var/folders/h2/kxdl0cpx4tv3956j2s1k0pb40000gn/T/moso-mcp-batch11-5n2ps_lc`.

## Integration Group 3 — Forwarding, bounds and denial regressions

Prepared locally on main `16ade1ecdc57a0b4f8989d3208a1286b765a2132` after
Groups1/2 merged. Select only test changes from `cd83b8d2`, `a875f50a`,
`f901ee99`, plus Batch02 keep-unchanged evidence from `b051f64f`. The policy
already arrived with Group1, so retain it once and correct its stale unmerged
provenance. Preserve every unrelated main inventory section/assessment.

No production implementation, dependency, template, style or browser behavior
changes. Existing owner/parser/metadata/decorator implementations match the
reviewed source bytes. All three changed test files match their completed audit
snapshots. The new checks catch lost Mongo constructor arguments, first-overflow
page-count rounding and incorrect permission/action/resource forwarding; exact
deprecation English prose is no longer a unit-test requirement. Existing parser
cases remain unchanged; no gap was found that justified adding another test.

The only new definition is ordinary authenticated denial with a protected
handler that must never run. It protects a distinct final branch missed by the
old tests. Fixed/dynamic demo forwarding and anonymous admin-flag scenarios
extend existing definitions using inexpensive spies/subtests. No test removed.
Six unittest cases contain eight subtest leaf scenarios; those are not eight
definitions. This group adds no fresh mutation score or coverage target.

Prior bounded mutation evidence is preserved below: owner24/32 killed with
eight individually equivalent/diagnostic survivors; parser26 selected killed,
46 other module mutants unselected; metadata36 selected detected after the
boundary improvement. Nested decorator code was not selected by mutmut; twelve
explicit hand-seeded faults detected after improvements are not a mutmut score.
Relevant source/test identity was checked, so no repeated mutation sweep was
needed solely to move the same completed work onto main.

Current focused integration: **78 cases passed in16.25s** across complete Mongo
lifecycle, both public-pagination files, decorator, wrapper-helper and city-scope
files. This includes unchanged real-Mongo lifecycle/index/cache and actual
city-route compatibility checks, not newly counted assessments. Private Mongo
50323 only; local Python3.11 is not hosted Python3.12/full-suite evidence.
`git diff --check` passed. CodeRabbit review completed across all six changed
files with zero findings. The final documentation comparison restored two newer
main provenance paragraphs and recorded the result; no test or implementation
changed afterward. Included capacity only, no paid credit or credential change.
Group3 hosted CI remains pending publication. No visual gate is asserted for
this tests/docs-only change.

Counts:1,312definitions/175files/464assessed. Six decorator dispositions are new
to the merged inventory, including one added definition; other prior assessments
are carried forward without duplication. Remaining848 tests plus two supporting
fixtures need individual review. This integration does not complete the suite.
Group3 publication/merge/automatic deployment still needs explicit authorization.
After it is integrated, resume bounded audits from then-current main, retaining
completed dispositions unless meaningful source/contract changes invalidate them.

Evidence: chat `work/regression-integration-validation.log`; private directory
`/var/folders/h2/kxdl0cpx4tv3956j2s1k0pb40000gn/T/moso-regression-integration-k8k3f4c1`.
The following Batch01–04 records retain original dates, base revisions, tool
versions and branch counts; those counts are historical, not current totals.

## Batch01 — test-session Mongo client owner

Reviewed baseline: main `b71f48cd`, 2026-10-24. Source:
`tests/_mongo_clients.py`. Only the three no-fixture unit definitions in
`tests/test_mongo_client_lifecycle.py` were executed in this mutation pilot.
The two real-Mongo definitions and the rest of the repository were **not**
mutation-tested. No actual database, shared application fixture or production
connection was used.

### Isolation and tool

- `mutmut3.8.0`, Python3.11, pytest9.1.1 and PyMongo4.19.0 in a temporary virtual
  environment, not added to application dependencies or CI.
- The copied owner source was byte-identical. The three existing test function
  ASTs were verified identical before strengthening; only the module import path
  changed. Repository `conftest.py` was deliberately not loaded: its teardown can
  clean disposable databases used by another active test process.
- Temporary `pyproject.toml` used `source_paths=["src/"]`,
  `pytest_add_cli_args_test_selection=["tests/"]` under `[tool.mutmut]`, with
  pytest `pythonpath=["src"]`. Command: `mutmut run --max-children 2`.
- After changing the assertion, the original result directory was retained
  separately and a fresh run generated all32 mutants again. No exclusions,
  ignored lines or reused green mutant results were introduced.

### Results

| Run | Existing unit tests | Mutants | Detected | Survived | Timeouts/errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original assertions | 3 passing | 32 | 21 | 11 | 0 |
| Exact constructor-argument assertion added | 3 passing | 32 | 24 | 8 | 0 |

Three substantive survivors changed `factory(uri, **options)` to
`factory(None, **options)`, `factory(**options)` or `factory(uri)`.
The recorder previously checked only how often it was called, not its arguments.
One assertion requiring the exact URI and `maxPoolSize` catches all three.

The remaining eight are reviewed as follows:

- Six add surrounding text or change capitalization in the three exception
  messages. Exception type/relevant reason and fail-closed behavior remain
  checked; exact full wording is not the contract.
- `_options=None` becoming an empty string is overwritten before options are
  consulted on the public call path.
- `_closed=False` becoming None preserves the falsey initial state and later
  True transition. Requiring a private initial representation adds no protection.

These are not eight confirmed production bugs, nor a claim that no other defect
can exist. The tool's raw detection rate is75%; that figure alone is not a test
quality grade or a reason to force brittle assertions.

### Test decisions

| Definition | Decision | Distinct protection |
| --- | --- | --- |
| `test_owner_is_lazy_and_rejects_foreign_endpoint_or_changed_options` | Keep + strengthen | No early/foreign-endpoint creation, exact constructor forwarding, reuse and option rejection |
| `test_owner_constructs_one_client_under_concurrent_requests` | Keep | One constructed client across concurrent callers |
| `test_owner_closes_once_and_cannot_reopen_after_session_end` | Keep | Close ownership and rejection after shutdown |

No test was removed or merged merely to reduce the count. The other two
real-Mongo tests still protect integration behavior these fake factories cannot.


## Batch02 — public page-size argument bounds

Reviewed on 2026-10-24 against the same `b71f48cd` baseline, on the isolated
test-review branch. Source: `mielenosoitukset_fi/utils/public_pagination.py`.
Only `test_public_page_size_is_bounded_and_existing_defaults_survive` from
`tests/test_public_pagination_limits.py` was executed: one definition, nine
parametrized cases, all passing in the isolated control.

The copied source was byte-identical and the test AST, including its decorator,
matched the repository definition. Imports alone were adapted to avoid loading
the application's database fixtures. The same temporary `mutmut 3.8.0`
environment as Batch01 ran `mutmut run '*public_page_args*' --max-children 2`.

All 26 selected parser mutants were killed; none survived or timed out, and
there were no errors. The tool generated 72 mutants across the copied module,
but the other 46, in index creation and metadata helpers, were outside this
selection and were not tested. This is not a whole-module mutation score.
Module-level constants are not mutated by this run. Results remain in the
isolated scratch directory, not production or a shared test database.

Decision: **keep unchanged**. The nine input cases exercise our own resource
bound and default contract without a database, network or complicated mocks.
They are inexpensive and do not re-test dependency internals. The focused run
found no assertion gap warranting another test. It does not establish complete
input coverage, page-number handling or query-level enforcement.

The six other definitions in this test file protect actual endpoint queries,
pagination, render context or cache behavior. They are not duplicates of this
parser test and were not executed or mutation-tested in this batch. No tests,
assertions or production code were added or removed.


## Batch03 — pagination metadata and boundary behavior

Reviewed on 2026-10-24, starting at `b051f64f` (the policy/Batch02 record
commit after `cd83b8d2`). Local `main` was `86466e54`; a read-only remote
lookup confirmed main at `35fd6def`, matching cached `origin/main`. The
pagination helper and both reviewed test files were identical between this
branch and remote main. No rebase, merge, reset or shared-service cleanup ran.

### Control and mutation scope

Four existing definitions / ten collected cases:

- `tests/test_public_demonstrations_api.py::test_public_pages_have_chronological_tie_breaks_and_filtered_counts`
  — two endpoint cases.
- `tests/test_public_demonstrations_api.py::test_public_page_metadata_handles_empty_and_out_of_range`
  — two endpoint cases (each checks both zero matches and beyond-last).
- `tests/test_public_pagination_limits.py::test_demo_apis_cap_the_real_query_and_return_bounded_metadata`
  — two endpoint cases.
- `tests/test_public_pagination_limits.py::test_enormous_out_of_range_pages_never_reach_database_skip`
  — four endpoint cases.

The unmodified control passed all ten cases in 5.44s with Python 3.11.15,
pytest 8.4.1 and PyMongo 4.6.3 from the existing application environment. A
private loopback-only `mongod` with a new temporary data directory was used;
`TEST_MONGO_URI` selected that instance before importing repository conftest.
Its broad test-database teardown therefore touched only this audit's instance.
No shared Mongo service, production data or application dependencies changed.
This local Python 3.11 evidence does not replace the supported Python 3.12 CI gate.

The existing `mutmut 3.8.0` artifacts still existed. Original source bytes
matched this branch and the recorded Batch01/02 test ASTs/results were verified.
Batch03 used the 36 previously generated, unexecuted `public_page_metadata`
variants from Batch02's 72 module mutants. Each variant function was extracted
with Python AST, renamed to the public helper name and loaded in a scratch
module. A scratch pytest plugin rebound only `public_page_metadata` on loaded
project modules immediately before each test call, requiring both actual route
modules to be present. The repository tests, Flask routes, filtering, database
queries and fixtures ran unchanged against private Mongo. No application source
was mutated in the checkout. A byte-identical source control through the same
bridge also passed all ten cases.

This is a custom sequential execution of **mutmut-generated mutations**, not a
new `mutmut run` score. Every variant used a fresh pytest subprocess, private
Mongo and new result logs, with a 60s timeout; no cached mutant outcomes were
reused. Test selection was the four node IDs above, with `-x --tb=short` and
`-p metadata_bridge`. Parser 26/index 10 mutations were not selected in this batch.

### Results and individual survivor inspection

| Run | Definitions / cases | Selected mutants | Detected | Survived | Harness errors/timeouts |
| --- | --- | ---: | ---: | ---: | ---: |
| Original repository assertions | 4 / 10 | 36 | 35 | 1 | 0 |
| Strengthened existing API bounds definition | 4 / 10 | 36 | 36 | 0 | 0 |

The sole survivor, `x_public_page_metadata__mutmut_25`, changed
`(total + per_page - 1) // per_page` to
`(total + per_page - 2) // per_page`. Individually inspected: **real gap**.
The six-record/two-per-page scenario and 105-record/100-per-page scenario both
retain the same rounded count under this mutation. At 101 records / 100 per page,
the mutant falsely reports one page, hiding the one-record final page from a
client relying on metadata. This is our response contract, not dependency
internals or an equivalent implementation.

Improved the existing API bounds definition: seed 101 instead of 105 records,
retain the 100-record cap and disjoint-page assertions, and check the final
page's status, page/size/total/page-count and exact 101–101 range. Other users of
the shared seed helper keep its 105-record default. No definition or parametrized
case was added or removed; production behavior did not change.

### Validation

The fresh after-change sweep detected all 36 selected variants, with no
survivors, timeouts or setup/collection errors. Each nonzero result was checked
to be a test-call failure. The formerly surviving rounding change now fails the
existing API test at its literal two-page assertion (`1 != 2`). Original and
final sweeps took 115.23s and 118.77s respectively, including their bridge
controls; mutation cost is bounded diagnostic work, not a proposed CI gate.

Both complete pagination test files then passed without the mutation bridge:
**13 definitions / 32 collected cases in 8.40s**. This also checks the seed helper's
unchanged default callers, parser, cache, invalid-argument, index provision and
actual Mongo query-plan cases; the additional nine definitions were compatibility
controls, not newly individually dispositioned by this batch. CodeRabbit's
uncommitted test-file review completed with zero findings. `git diff --check`
passed. No full-suite, hosted Python 3.12 or production performance claim follows.

### Individual dispositions and maintenance cost

| Definition | Decision and regression value | Reliability, cost and coupling |
| --- | --- | --- |
| `test_public_pages_have_chronological_tie_breaks_and_filtered_counts` | Keep: complete page traversal, date/time/ID tie breaks, hidden-row exclusion and filter-preserving next URLs. | Two real endpoints, six reverse-inserted records plus hidden match; exact public ordering is contractual. No network/authorization doubles for these checks; relative future dates avoid stale fixtures. Does not prove concurrent-insert stability. |
| `test_public_page_metadata_handles_empty_and_out_of_range` | Keep: empty arrays, 0–0 range, filtered total and minimum-one page for zero matches. | Two endpoints and two distinct empty reasons per case. Small real fixtures; expected page-count formula is paired with literal expectations in the other retained tests. Not redundant with nonempty traversal. |
| `test_demo_apis_cap_the_real_query_and_return_bounded_metadata` | Improve: resource bound plus first overflow and single-record final-page metadata; kills rounding survivor. | Two endpoints; 101 inserts instead of 105, no extra requests/parametrized cases, only cheap response assertions and one seed-count argument. Real Flask/Mongo integration contract. Page disjointness remains; ordering is covered by the retained traversal test. |
| `test_enormous_out_of_range_pages_never_reach_database_skip` | Keep: four routes must avoid a huge database offset and return empty output. | Deliberate cursor `skip` sentinel protects a resource-operation contract; real counts/route handling remain. Small 105-row fixture and 100-digit page. Coupling to PyMongo cursor API is justified by the explicit no-scan risk; not proof of bounded count cost. |

Consolidation considered: nonempty ordering, empty metadata, capped partial
pages and forbidden huge offsets protect distinct failures. Combining them
would increase branching and obscure failures. Keep the four definitions;
no removal or separate unit arithmetic test is justified.

Scratch evidence: project-chat `work/run_metadata_mutations.py` and
`work/batch03-control.log`; private directory
`/var/folders/h2/kxdl0cpx4tv3956j2s1k0pb40000gn/T/moso-pagination-batch03-dicev1rn`
contains the bridge, all 36 variants and per-run JSON/logs. These are local
scratch artifacts, not permanent CI tooling or deployable application code.


## Batch04 — permission decorators and denial dispatch

Reviewed 2026-10-25 from `a875f50a`. Clean starting worktree; a read-only
remote lookup still found main at `35fd6def`. Source `utils/wrappers.py` and
`tests/test_wrappers_decorators.py` matched main. Main's thirteen individually
reviewed `test_wrappers.py` definitions and their newer assertions were read as
prior work, not repeated or imported over this branch's older tests.

The five existing unittest definitions initially passed in 0.09s. A scratch
module copied the AST-identical `permission_required` and `depracated_endpoint`
functions. Flask/Flask-Login and functools remained real; logger used standard
logging, and patched flash/demo-permission boundaries had failing sentinels for
unexpected calls. Only the test import changed. Repository conftest and any
database were excluded from this diagnostic harness. Baseline test-class ASTs
were checked against the original committed file.

### Tool limitation and bounded fault controls

`mutmut 3.8.0` was attempted with selection `*permission_required*` and
`*depracated_endpoint*`. It skipped the nested decorated dispatch functions and
reported no covered mutants. Its six generated mutants belonged to the harness
sentinel functions and were not selected. This is a tool/harness limitation,
not six survivors or evidence of good assertion quality. No mutation score is
reported for these decorators, and mutation tooling was not added to dependencies.

Twelve explicit AST fault injections then exercised security/forwarding risks
in the copied functions, one fresh subprocess per fault. The source was restored
in a finally block; scratch bytecode was removed before every subprocess and
bytecode writing disabled to prevent stale-code reuse. The table records every
fault; these are deliberate controls, not mutmut-generated mutants.

| Injected fault | Existing five tests | Revised six tests | Individual interpretation |
| --- | --- | --- | --- |
| Demo helper gets VIEW_DEMO instead of requested EDIT_DEMO | Missed | Detected | Real permission-forwarding gap; constant answer hid wrong action. |
| Demo helper gets no resource ID | Missed | Detected | Real target-forwarding gap, not equivalent. |
| Demo helper gets no user | Missed | Detected | Real identity-forwarding gap, not equivalent. |
| Role check gets VIEW_DEMO | Missed | Detected | Real action-forwarding gap. |
| Role check gets foreign organization instead of configured scope | Missed | Detected | Real scope-forwarding gap; expected None is an intentional unscoped call. |
| Authentication guard skipped | Detected | Detected | Retained redirect scenario protects authentication. |
| Demo permission result inverted | Detected | Detected | Distinct positive and negative demo controls already detect it. |
| URL builder receives wrong login endpoint | Missed | Detected | Real navigation integration gap masked by stubbed URL result. |
| Global-admin bypass runs before authentication | Missed | Detected | Auth guard must precede privilege bypass, including objects retaining an admin flag. |
| Demo denial calls protected handler | Detected | Detected | Existing Forbidden expectation detects access fail-open. |
| Ordinary denial calls protected handler | Missed | Detected | Separate untested denial branch; meaningful new negative scenario. |
| Deprecated endpoint aborts 403 instead of 410 | Detected | Detected | Retained Gone expectation protects public endpoint status. |

All original/revised controls passed without faults. Results: four of twelve
faults detected before, all twelve after, with no setup/collection errors or
timeouts. This limited risk selection is not exhaustive authorization, dependency
integration, whole-module mutation coverage or proof against all bypasses.

### Individual dispositions

Supporting setup: each unittest creates a tiny Flask app/request context; fake
user answers and targeted patches isolate dispatch from membership/session/DB
policy. No network, scheduling, random data or time dependency. Both isolated
controls took 0.09s, so added maintenance is assertion/setup complexity rather
than material execution time.

| Definition | Decision, uniqueness and maintenance reasoning |
| --- | --- |
| `test_permission_required_redirects_unauthenticated_users` | Improve existing: two subtests retain ordinary anonymous redirect and require auth before an admin flag. Require the correct login endpoint, response location/status and one notification; no exact translated copy assertion. Real request context, mocked URL builder/current user; not actual login/session loading. |
| `test_permission_required_allows_users_with_permission` | Improve existing: require exact EDIT_DEMO/None call plus successful return. A single method spy tests our dependency contract, not permission-backend internals. The fake still does not prove actual membership lookup. |
| `test_permission_required_aborts_when_demo_permission_is_missing` | Improve existing: retain Forbidden/notification and require exact user/resource/action on the helper. Distinct deny branch from ordinary dispatch; cheap patch, no database. |
| `test_permission_required_allows_demonstration_access_when_granted` | Improve existing: fixed-ID and dynamic demo_id subtests require exact helper arguments; dynamic handler receives its route keyword. Actual decorator/Flask context, helper patched; the same public dispatch contract, so extend this definition instead of adding another forwarding test. Other keyword aliases/global-grant/city fallback combinations remain outside this batch. |
| `test_deprecated_endpoint_aborts_with_gone` | Improve maintenance: retain actual Gone/one notification, relax exact English text. HTTP 410 and notification are the behavior; editorial copy changes need not break this unit. Not localization or response-rendering acceptance. |
| `test_permission_required_denies_users_without_permission` (new) | Add/keep: authenticated ordinary user with no grant must raise Forbidden and never invoke the protected Mock handler; notify once. Separate final denial branch warranted a distinct failure scenario rather than branching an allow test or a demo-specific test. |

Five definitions became six collected unittest cases. The two subtest groups
are two scenarios each, for eight leaf scenarios across the six definitions;
subtests are not separately collected pytest cases. No parametrization was
added, and no test was removed. Consolidation considered: anonymous redirect,
ordinary grant/denial, demo grant/denial and endpoint retirement protect distinct
branches/outcomes; merging would add conditionals and obscure failures.

### Real-import validation

The actual repository `test_wrappers_decorators.py`, `test_wrappers.py` and
`test_city_scoped_admin.py` passed **41 collected cases in 12.46s**, with real
project imports. A new exclusively owned loopback Mongo instance was selected
before repository conftest; broad teardown could only affect this audit's data.
The additional 35 cases are compatibility controls, not new individual reviews
or the newer main-only helper assertions. No production auth code changed.
CodeRabbit completed the uncommitted test-file review with zero findings, and
`git diff --check` passed. Local Python 3.11 does not replace supported Python
3.12 hosted CI; no full-suite or production acceptance is claimed.

Evidence: chat `work/run_decorator_faults.py`, `work/batch04-before-mutmut.log`
and `work/batch04-validation.log`; scratch
`/var/folders/h2/kxdl0cpx4tv3956j2s1k0pb40000gn/T/moso-decorators-batch04-gkmy6igs`
contains original/revised per-fault logs, JSON results and source variants.


## Batch13 — admin magic-token collection and revocation

2026-10-26; based on merged main `7cadeedf`. Four existing definitions/four
collected cases became five definitions/10 cases. No tests removed. The four
individual improvements and new CSRF disposition are in the inventory. These
are distinct sorting, filtering, authority/audit, architecture and request-
authenticity contracts; consolidation would obscure meaningful failure modes.

### Evidence and changes

The unchanged focused control passed four cases (2.76s). Five scoped hand-seeded
faults then passed all original assertions: replacing primary timestamp order
with ID order; bypassing the route authority guard only for POST; dropping our
audit call; additionally revoking neighbours; dropping the active expiry
predicate. All five were detected after assertion improvements, each at the
intended test call (one failure/seven passes). These are selected diagnostic
faults, not generated mutmut mutants or a module mutation score. Real Mongo
query/write behavior was retained; only the selected contract was changed.

Scratch harness errors were excluded: premature app import caused collection
failure in the capture plugin, and an earlier fault fixture initialized app
before config/seed restoration, producing an unrelated first-request redirect.
Moving the plugin import into fixture execution and explicitly ordering
ensure_test_config/seeded_data/app restored neutral controls. No speculative
repository conftest rewrite was made.

The audit also found that both destructive POST branches accepted no CSRF
proof. Two new negative cases failed with302 instead of403 on the unchanged
handler. The fix renders a session-bound hidden proof and validates it before
any single/bulk write, after authority checking. Byte comparison rejects Unicode
input safely. Focused green: **10 passed in4.83s**. Tests verify missing, wrong,
Unicode and foreign-session rejection with no token/audit writes, plus valid
single/bulk behavior. This proves server validation, not cross-site browser
cookie delivery or a production exploit. The existing session SameSite policy
is not treated as a substitute for a request proof.

Static architecture checks retain legacy-hook prohibitions but accept harmless
class reordering/additions. Running that check from outside the repository
previously failed to locate its template; anchoring to __file__ fixes that cost.
Real route/Mongo checks cost seconds and use common fixtures; added assertions
justify their cost for stable paging and privileged destructive actions. No
external package internals, exact translated editorial messages, clock sleeps
or new production dependencies were introduced. Related browser checks remain
individually pending; compatibility passing does not assess them.

Evidence is stored in the chat workspace under work/batch13-* and
outputs/magic-token-visual/. Final review and validation checkpoint follows.


### Final local validation

Final selected-fault sweep on the protected handler detects all five at the
intended assertions: primary_sort, post_authority, audit and active_expiry each
one failure/nine passes; overbroad_revoke two failures/eight passes (the new
positive CSRF case also detects unintended neighbouring revocation). No harness
errors or timeouts count as detections. Original/revised controls are separate
from these deliberately failing diagnostics.

The complete magic-token file plus existing edit-link lifecycle compatibility
checks passed **38 cases in14.73s**. Compatibility cases are not new individual
dispositions. The static architecture check also passed from scratch cwd. Local
CodeRabbit review completed with zero findings across all six changed files;
this is local review, not hosted CI. `git diff --check` passed. Private Mongo
was used throughout; no shared database was cleaned. Supported Python3.12
hosted CI remains outstanding; local Python3.11 evidence is bounded.

Canonical inventory: **1,313 definitions /175 files /469 assessed /844 pending**,
plus two separately pending supporting fixtures. Prior464 assessments are
preserved; four existing plus one new magic-token definition are assessed.
The full goal remains unfinished.


Independent visual acceptance: **SHIP**, separate read-only reviewer
`/root/visual_magic_tokens`; all28 unique before/final screenshots opened and
compared at390/1440 in both themes, FI, page/single/bulk/actual403 states.
Source hashes and captures matched packet SHA256
`359843fa3a0d2a96566013d9802a1eafb5dc4ae798f072c15573257d062f4cdd`.
No new visual regression. Existing translucent/dim confirmation rendering and
null addEventListener error occur before and after and remain separate defects;
no failed resources. This does not certify uncaptured states or the whole UI.
Exact source/image hashes and review are in the chat artifact
`outputs/magic-token-visual/visual-review.md`.


## Batch14 — organization-search query bounds and public fields

2026-10-26, new clean branch from merged main `ccc2eb0f`. Batch13 has been
published asPR#985, merged, deployed with exact SHA verified through trusted
origin and a separate public HTTPS probe. Its post-merge CI also passed.

Scope is two existing backend definitions in
`tests/test_submit_organization_search_security.py`, both previously pending.
Read the actual nested search handler, published API contract and all six tests
in that file for overlap. The four frontend definitions remain pending; no
browser/visual disposition is inferred from backend evidence. No production,
template, style, translation, dependency or changelog change is justified here.

### Controls and mutation harness

Unchanged real-project control: **two passed/four deselected in2.53s**, against
an exclusively owned loopback Mongo60141. Improved actual-route control:
**12 passed/four deselected in5.85s**. Two definitions remain two; eight query
cases and four normalization cases replace the original two collected cases.

Reused verified temporary mutmut3.8.0 environment; no production dependency
added. Since the route is nested inside the large route-registration function,
the mutation harness extracts its exact dedented body without decorators into
one scratch module. Function-body/source hashes and line range are preserved
in projection.json. The fixture binds real Flask/Babel and private Mongo;
DatabaseManager is replaced only by a provider of that actual database. This
isolates handler assertions and does not prove the application's singleton or
registration integration. Separate unchanged/improved full-project route
controls use the actual manager/registration. Mutation-harness neutral controls
passed two cases in0.08s and12 in0.32s. One mutation worker prevents shared
scratch DB interference. Original cache/logs were preserved; the improved sweep
started with a fresh generated directory and identical source body.

All **112 selected generated mutants** ran in each sweep: initially72 killed,
40 survived; after improvement98 killed,14 survived. No timeout, suspicious,
untested or harness error was counted as a detection. Every original and final
survivor diff was inspected. Twenty-nine old survivors now fail; three editorial
message variants intentionally survive after removing exact-copy coupling.
These are projection results, not a whole-module or whole-suite score.

### Survivor decisions (all14 final survivors)

| Mutmut suffix | Individual inspected change and decision |
| --- | --- |
|19|Adds XX around the error text. Ignore diagnostic-copy sensitivity; status/error envelope remain checked.|
|20|Lowercases the error text. Same editorial decision.|
|21|Uppercases the error text. Same editorial decision.|
|27|Replaces query projection withNone. Public serialization remains an explicit whitelist; result contract unchanged. Database fetch cost could differ; no claim of operational equivalence or extra mock assertion merely to kill it.|
|29|Omits projection argument. Same public-output result and consciously untested fetch-cost concern as27.|
|42|Renames projection _id key toXX_idXX. Mongo still includes _id; explicit public serialization ignores the extra key. No package-internals test warranted.|
|43|Renames projection _id key to_ID. Same default-ID inclusion reasoning.|
|44|Changes _id inclusion1 to2. Both are truthy inclusion values on real Mongo; equivalent result.|
|47|Changes name inclusion1 to2. Equivalent inclusion/result.|
|50|Changes email inclusion1 to2. Equivalent inclusion/result.|
|53|Changes website inclusion1 to2. Equivalent inclusion/result.|
|56|Changes description inclusion1 to2. Equivalent inclusion/result.|
|63|UsesNone instead of101 for initial description slice. Final100-character trim/ellipsis still yields the same string output, including malformed/missing paths. No internal intermediate-length assertion.|
|69|Uses102 instead of101 for initial description slice. Same final output; one extra intermediate character is not a meaningful protected contract.|

Detected meaningful old gaps include minimum/maximum acceptance, ten-result
cap, valid email/website forwarding, public ID and length/ellipsis boundaries.
The original invalid-value scenario was retained; valid values distinguish a
correct normalizer from silently dropping legitimate data. Query assertions
require membership/distinct results but not Mongo's unspecified result order.
Exact translated error prose was relaxed to a nonempty error string with400.

Mutmut does not mutate the nested normalized_text helper body. A separate
single scoped helper-guard fault and neutral control are checked on the actual
project route; that diagnostic is not included in the112 generated mutants.

### Individual value and cost

Keep/improve both existing definitions; no new/removal/consolidation justified.
Query validation/bounded literal search and public serialization have distinct
risks, inputs and useful failure diagnoses. Their cases belong within their
existing behavior definitions. The added fixture runtime (about3.3s here) buys
observable acceptance/rejection and output safety rather than package behavior.
Common real DB/session setup, fixed text, no network dependencies, sleeps,
random ordering or time-sensitive assertions. Exact output keys are deliberate
public-whitelist protection; harmless ordering and editorial copy are flexible.
Published limits and existing implementation bound this selection; no new
speculative URL validation, field formats, regex stress cases or frontend tests.
Full test-suite quality and production resource consumption remain unproven.

Evidence: chat work/batch14-*.log, survivor diffs and setup_search_mutation.py;
owned scratch moso-search-batch14-x8aep_th/mutation contains source/test projection,
original/fresh generated caches and projection.json. Final review follows.


Final local checkpoint: the actual-route helper neutral control passed12 cases
in5.67s; removing only its non-string guard produces six intended request-call
failures/six passes (6.35s), with None/dict slicing TypeErrors from the handler.
These are not setup/collection failures, and are not added to mutmut totals.
CodeRabbit completed review of the three changed files with zero findings.
`git diff --check` passed. Canonical inventory reconciliation found no missing,
stale or duplicate test entries after excluding the two named supporting
fixtures:1,313 definitions/175 files/471 assessed/842 pending, plus two fixtures.
No full-suite or hosted CI has run for this new branch, and Python3.11 local
controls do not replace supported Python3.12 CI. No source/UI change means no
new visual acceptance gate for this tests/docs-only batch.
