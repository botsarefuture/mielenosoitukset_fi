# Repository instructions

Read and follow [AGENTS.md](AGENTS.md), including the decisions log and development
workflow it references.

Merges go through the GitHub merge queue on `main`. Finish a pull request by arming
auto-merge (`gh pr merge --auto --merge`) rather than watching its checks: it is
enabled on the repository, and the queue merges when the required checks and review
threads pass. A queued branch cannot be pushed to or updated, so a "cannot be updated" message means
the pull request is in the queue: remove it from the queue before changing it. Use
`gh stack` for work that depends on an unmerged pull request. The green/yellow/red
traffic-light routine is retired; see the
"Merging", "Backlogs of 20–40 pull requests" and "Resolving conflicts" sections in [AGENTS.md](AGENTS.md).

Quote times in Helsinki time (`Europe/Helsinki`) and name the zone; GitHub and CI report
UTC, so convert rather than pasting timestamps.

For user-facing changes, add a uniquely named note in `changelog.d/` as described in
[its README](changelog.d/README.md); do not edit `CHANGELOG.md` for new entries. Run
`python scripts/render_changelog.py` to view the notes with the existing history.

Use `gh stack` for useful dependent layers (`init`, `add`, `submit`, `sync`,
`view`); merge from the bottom and verify the next layer targets `main` before
arming it. Independent changes target `main` directly and need no stack.

For backlogs of 20–40 independent pull requests, arm each ready PR's auto-merge
without waiting for the previous merge. GitHub runs up to 8 queue builds
concurrently and merges up to 8 ready entries together. ALLGREEN, minimum 1,
wait 0 and the 60-minute timeout remain. A lone PR has no batching delay but
still runs required queue checks. Do not promise one CI run per eight PRs, bypass
protections, or use agents to poll and direct every merge. Return for failures,
conflicts or review feedback. Dependent PRs must target `main` after their parent
merges before entering the queue; retained branches are not retargeted for you.

Production deployments identify verified commits, not individual PRs. A multi-PR
update to `main` needs no artificial per-PR deployments. Native concurrency keeps
one active deployment and replaces pending runs; `cancel-in-progress: false` does
not queue every revision. Do not cancel active deployments or add custom timers.
See `AGENTS.md` for the approved backlog and deployment separation rules.
