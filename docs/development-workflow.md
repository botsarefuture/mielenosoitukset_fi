# Development workflow

How work is done in this repository, for people and for agents. `AGENTS.md` has the
hard rules (changelog, visual acceptance, UI-06 direction); this file covers the
day-to-day routine around them.

## Who decides what

The maintainer decides what we build and why. Whoever implements decides how.

- Work that is already approved (an open roadmap item such as UI-06, or something the
  maintainer asked for directly) is carried through without asking about each detail.
- A new initiative needs a short proposal first: the problem and why it matters, scope,
  approach, ordered tasks, risks, and which parts become separate PRs. Wait for a yes
  before building it.
- Something spotted on the way is not authorization. Small fixes tied to the current task
  are fine. Everything else goes into `TODO.md` or an issue.
- If an approved plan turns out to need a different direction, say so and get approval
  before changing course.
- Record every maintainer decision, with its reason, in [the decisions log](decisions.md)
  in the same PR that implements it.
- Security problems are reported to the maintainer straight away, not fixed quietly with a
  disruptive change.

## Branches and worktrees

- Never commit to `main`. `main` is usually checked out in another worktree anyway.
- One branch per independent piece of work, named `codex/<topic>` or `fix/<topic>`.
  Continue on the existing branch when it is the same work.
- Start from a fresh `origin/main`. Do the work in its own `git worktree`; link the main
  checkout's `node_modules` instead of reinstalling.
- The shared checkout may hold someone else's uncommitted or untracked work. Do not
  stage, stash, reset, clean or switch branches under it. Stage files by name, never
  `git add -A`.
- `mielenosoitukset_fi/static/frontend/manifest.json` and the hashed assets it names are
  rebuilt (`npm run build`) in the same commit as the source change.
- Remove a worktree and its branch once the PR is merged.

## Commits and pull requests

- Small commits, one idea each, with a message that says why the change was needed.
  Imperative mood, no trailing period, no tool or assistant attribution.
- A PR covers one reviewable change. Stack PRs when one depends on another and say which
  base each uses.
- The description says what changed, why, how it was checked and anything that was not
  checked. Link the roadmap item or issue.
- Every user-facing change has a separate note in `changelog.d/`. Write it for a
  reader of the changelog, not as a diff summary. See `changelog.d/README.md` for
  how to render the combined history.
- Open the PR as soon as the branch is ready, then move on to independent work. Do not
  sit waiting for CI.

## Keeping track of open PRs

- At the start of every session and after finishing each PR, list open PRs, check CI and
  read new review comments. Fix what is red or requested before starting new work.
- Rebase or merge `main` into a branch that has fallen behind; resolve conflicts in the
  generated frontend assets by rebuilding, not by hand.
- Merging and production activation follow the approval rules below: green required
  tests (plus SHIP for UI) are enough to merge.

## Choosing the next task

1. Anything broken in production or failing CI on an open PR.
2. Review feedback on open PRs.
3. The next unfinished item in the UI-06 plan in `roadmap.md`, in the order written
   there. Keep that inventory current when a page ships.
4. Open issues related to the page or area being worked on.
5. `TODO.md`.

When one item is done, take the next one without asking. Keep a short record of what is
done, in progress and left (the roadmap inventory plus open PRs is enough).

## UI and copy

- Public UI is React on the standalone host, with data from the Go API. No new Flask
  routes, views or templates for public pages. Admin stays Flask/Jinja.
- Keep no-JavaScript fallbacks light: title, lead, event links with paging and the
  notice that the page works best with JavaScript. Test them with assertions, not
  visual review.
- Migrating a page is a chance to improve it, not only to port it. Look at it as a
  visitor on a phone and on a desktop: is it clear what the page is for, is the main
  action obvious, does it work with the keyboard, is the contrast sufficient.
- Reuse the existing components, tokens and layout described in `docs/design-system/`. Add a new one only when there is a
  second use for it.
- Use few headings, cards, badges and icons. Prefer plain, specific Finnish copy to
  generic marketing wording. Avoid em dashes in user-facing text.
- No hero eyebrows: the small pill or uppercase label above a page title (for example
  "Ohjekeskus" on the guide hero) only repeats the title. Section labels that tell the
  reader where they are in a sequence, such as "01 Aloita tästä", are fine.
- Strings: reuse existing msgids; leave `en` and `sv` text to the human translators.
- Verification for any rendered change follows `docs/visual-qa.md`: real captures at
  390px and 1440px in light and dark, reviewed by a separate reviewer. The implementer
  cannot pass their own work. Missing tooling means blocked, not passed.
- Keep SEO (title, description, canonical, structured data), page-view tracking and
  existing URLs intact when a page moves.

## Code and writing style

- Match the surrounding file. No comments that restate the code, no docstrings on
  trivial functions, no helper or abstraction added for a single caller.
- No placeholder code, no speculative options, no TODOs without an issue behind them.
- Defensive checks belong at real boundaries (request input, external services), not
  around every call.
- Commit messages, PR text and docs are short and specific. No summaries of the obvious,
  no self-praise.

## Tests

Run the tests that cover what changed, plus any contract tests the change touches (for
example the inline-style baseline). Say in the PR what was not run. Do not add a test
suite just to satisfy a visual review.

## Security and deployment boundaries

- No secrets, tokens, passwords, private keys or personal contact details in commits,
  PRs, logs, screenshots or docs. If one turns up in a conversation or file, report it for
  rotation and do not use it.
- Production access goes through the established, approved route (see
  `docs/production-deployment.md` and `docs/react-ssr-app.md`). Credentials pasted into a
  chat are not an approved route.
- Merging to `main` and the deployment and routing activation that follow it need no
  separate approval once the required tests pass and, for rendered UI, an independent
  reviewer has given SHIP (maintainer decision, 10 November 2026). Watch the deploy and
  fix or roll back anything it breaks.
- Still needs explicit maintainer approval each time: production data changes, database
  index or schema changes, authentication and session changes, changes to god, board or
  super-admin privileges, and anything that sends real email to real people.
- Prepare and verify rollback before asking for activation.
- Privileged-account and governance changes are never tested against real accounts without
  the account owner's say-so.
