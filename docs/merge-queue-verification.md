# Checking merge queue throughput

Use this runbook after an approved queue sizing change. The canonical repository
is `mielenosoitukset-fi/mielenosoitukset_fi`; `main` is protected by ruleset 1440033.
No protection bypass, admin merge, artificial batching delay or CI change is needed.

1. Inspect the settings with:

   ```sh
   gh api repos/mielenosoitukset-fi/mielenosoitukset_fi/rulesets/1440033 \
     --jq '{rules:[.rules[].type], queue:([.rules[]|select(.type=="merge_queue")][0].parameters)}'
   ```

   Keep deletion, creation, pull_request, copilot_code_review,
   required_status_checks and merge_queue. For the approved 20–40 PR backlog
   configuration, expect build 8, merge 8, MERGE, ALLGREEN, minimum 1, wait 0,
   timeout 60 minutes.

2. Choose two small, independent, reviewed PRs with green required checks and
   resolved review threads. Verify both target `main`; never queue a child against
   its parent's branch. Arm both close together with `gh pr merge --auto --merge`.
   Do not push queued branches. If a fix is needed, dequeue, push, then re-arm.

3. Observe queue entries and `merge_group` Actions runs. Compare the temporary
   head SHAs and commit ancestry to establish whether the second entry includes
   both PRs. Two green PR checks alone do not establish a shared queue build.

4. Record the Actions run link, queue head SHA, `python-tests` start and completion,
   elapsed build duration, resulting merge commit SHA(s), and PR numbers. Convert
   timestamps to `Europe/Helsinki` and name EET or EEST. If entries merge separately,
   report that result; do not claim a shared group or alter minimum/wait to force it.

5. Put evidence in the sizing PR. Use a background monitor only for this explicit
   verification; routine agents arm auto-merge and continue other work. GitHub
   handles the backlog. Return for failures, conflicts or review feedback.

Build concurrency controls concurrent queue checks, while maximum merge entries
controls the size of a merge batch. Neither guarantees one CI run per batch.
A lone eligible PR has no batching delay with minimum 1 and wait 0, but still runs
required checks. Measure throughput and invalidated work before raising limits.

Rollback: review the queue script's `--dry-run` with both
`--max-entries-to-build 3 --max-entries-to-merge 3`, then run `--confirm` with the
same flags. Keep every other protection unchanged. See
[the queue configuration](github-organization-migration.md#merge-queue-enablement).
