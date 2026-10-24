# Bounded test Mongo clients (#969)

## Problem and scope

`ensure_test_config` resets DatabaseManager before and after every test. In
TESTING mode the manager retains old instances until session teardown because
legacy imports keep database handles. Previously each fresh manager opened
another client: a bounded reproduction retained eight clients and 24 PyMongo
threads across eight resets. Hosted CI also stalled with many Mongo monitor
threads, but that does not prove resource exhaustion was its sole cause.

Only the test harness changes. Production DatabaseManager and connection options
are unchanged. Conftest installs a lazy, locked session factory before test
collection. It returns one real PyMongo client for the configured test endpoint
and the same constructor options; unexpected endpoints/options fail closed.
Managers/configuration snapshots and database names still refresh on reset.
Existing fixture database clearing/seeding and unique session names are retained.
Do not share this client across processes or install this factory in production.

Teardown closes deferred managers and the owner, restoring the original factory
even if owner cleanup raises. Existing manager cleanup can call PyMongo.close
more than once; PyMongo close is idempotent. This does not remove all retained
manager objects or pool other modules' independently constructed clients.

## Evidence and acceptance

- Real Mongo regression: 100 manager resets retain one client and all 100 old
  handles still ping; PyMongo thread growth is bounded rather than proportional
  to resets. A separate real case changes database name without invalidating the
  old handle. No documents are written by these cases.
- Isolated factory cases prove lazy creation, endpoint/options rejection, one
  construction across concurrent callers, and one owner close/no reopening.
- Existing config tests retain fake-manager close and actual config reloads.
- Local validation: eight lifecycle/config cases plus48 status, UI-translation,
  translation-join and CI-contract cases pass. The latter batch completed in
  170.22 seconds; local Python3.11 is not the hosted Python3.12 environment.
- CodeRabbit completed the five-code-file uncommitted review with zero findings;
  documentation/evidence updates followed that review. AST inventory confirms
  1,234 definitions across169 test files,345 individually assessed.
- Required CI still executes the whole test set with the existing 30-minute
  limit. Explicit empty addopts overrides pytest.ini's quiet flag; verbose test
  IDs and a 120-second faulthandler dump improve stalled-run evidence.

Focused success is not proof that the full hosted suite finishes. Require an
actual terminal result on the PR head before treating the CI incident as fixed.
Do not increase the timeout, skip tests or repeatedly rerun an unchanged failed
head instead of investigating its current per-test output.
