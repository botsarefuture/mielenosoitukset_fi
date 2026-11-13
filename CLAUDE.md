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
"Merging" and "Resolving conflicts" sections in [AGENTS.md](AGENTS.md).

Quote times in Helsinki time (`Europe/Helsinki`) and name the zone; GitHub and CI report
UTC, so convert rather than pasting timestamps.

For user-facing changes, add a uniquely named note in `changelog.d/` as described in
[its README](changelog.d/README.md); do not edit `CHANGELOG.md` for new entries. Run
`python scripts/render_changelog.py` to view the notes with the existing history.
