# Change notes

For each user-facing pull request, add a uniquely named `.md` file in this directory,
for example `1234-city-search.md` or a descriptive name with a date. Start with a
Markdown bullet describing the change and its impact. Use multiple bullets when
needed. Do not edit another pull request's note.

To view the combined changelog, run `python scripts/render_changelog.py`. It prints
these notes under `UNRELEASED` followed by the existing `CHANGELOG.md` history. To
save a copy, redirect it to a different file, for example
`python scripts/render_changelog.py > /tmp/changelog.md`. Do not redirect output to
`CHANGELOG.md`: the shell would truncate the source before the script reads it.

Keep note files after merging. The renderer reads them every time; it does not move,
delete, date, or mark them as released. A future release process can collect them
once the release format is decided. Existing branches may still update the old
changelog; preserve those entries when merging them.
