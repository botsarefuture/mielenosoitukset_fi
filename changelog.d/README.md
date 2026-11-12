# Change notes

For each user-facing pull request, add a uniquely named `.md` file in this directory,
for example `1234-city-search.md` or a descriptive name with a date. Start with a
Markdown bullet describing the change and its impact. Use multiple bullets when
needed. Do not edit another pull request's note. The existing test suite checks that
all notes can be rendered, including the required opening bullet.

To view the combined changelog, run `python scripts/render_changelog.py`. It prints
these notes under `UNRELEASED` followed by the existing `CHANGELOG.md` history. To
save a copy, redirect it to a different file, for example
`python scripts/render_changelog.py > /tmp/changelog.md`. Do not redirect output to
`CHANGELOG.md`: the shell would truncate the source before the script reads it.

GitHub Actions also renders a downloadable `CHANGELOG.md` artifact after each
push to `main`, nightly at 01:20 UTC, and on manual dispatch. Find it under
Actions → Render changelog → the run → Artifacts. The workflow does not commit
or publish the file; artifacts expire after 30 days.

Keep note files after merging. The renderer reads them every time; it does not move,
delete, date, or mark them as released. A future release process can collect them
once the release format is decided. Existing branches may still update the old
changelog; preserve those entries when merging them.

## Reviewing the historical rewrite

The separate `changelog.new.md` rewrite is a draft, not renderer input. Before
replacing `CHANGELOG.md`, review its diff against the then-current history,
reconcile changes made since the draft, and verify all entries and versions.
Keep the `## UNRELEASED` heading required by the renderer and check the combined
output. Review and merge that replacement as a separate change; preserve the old
history in Git for rollback. Do not copy a generated artifact over the source:
that would include note files twice on the next render.
