# Agents Guide

This repository often gets help from external agents (human or AI). Follow these rules every time you touch the codebase:

Before starting, read [the decisions log](docs/decisions.md): it records maintainer decisions and their reasons, so they don't need to be rediscovered from history. When the maintainer decides something new, add it there in the same PR.

1. **Always update the changelog**  
   - Add a unique note file in `changelog.d/` for each user-facing change; see `changelog.d/README.md`.
   - Use concise bullets describing the change and its impact. Run `python scripts/render_changelog.py` to view the combined changelog.
   - Keep the existing `CHANGELOG.md` as history; preserve entries from older branches that still edit it.

2. **Keep user context in mind**  
   - Read the existing code and comments before tweaking anything.  
   - Follow the coding style already used in the file (imports, formatting, docstrings, i18n, etc.).

3. **Prefer incremental commits**  
   - Don’t bundle unrelated fixes.  
   - Explain *why* a change is needed in your commit message (or PR description if that’s where you’re working).

4. **Validate before handing off**  
   - Run relevant tests or lint commands when practical.  
   - If you can’t run something (env not available, command fails, etc.), call that out explicitly for the reviewer.

5. **Communicate limitations clearly**  
   - If you’re unsure about requirements, ask.  
   - If you had to make assumptions, list them in your summary so humans can double-check.

## Mandatory visual acceptance

For changes that can affect rendered UI (including template data, CSS, JS,
translations and shared components), read and use
`.agents/skills/moso-visual-qa/SKILL.md`. Run the review here in the conversation,
not as an extra GitHub test suite. The existing product/admin design standard
wins over generic redesign defaults. Capture the real application and obtain a
separate reviewer agent's **SHIP** for the final source/capture snapshot before
declaring the UI ready. The implementer cannot approve their own output. Every
subsequent UI-affecting fix invalidates SHIP: recapture affected states and get
another independent review. Missing browser/screenshots/reviewer means
**BLOCKED**, never an implied pass. Keep existing relevant tests; do not add a
second CI suite or run the full suite just to perform this visual review.

### No-JavaScript fallbacks

Maintainer decision, 9 November 2026: most visitors use the JavaScript page, so
the `<noscript>` fallback of a public React route stays deliberately light and
is not part of visual acceptance.

- Keep what crawlers, link previews and failed script loads need: the page title
  and lead, the event links with paging, and a link to all demonstrations. Keep
  the canonical URL and metadata on the server-rendered document.
- Start the fallback with the short notice that the page works best with
  JavaScript. Do not add background sections, layout polish or page-specific
  styling to it.
- Check fallbacks with automated assertions such as
  `scripts/verify_public_host.mjs`, not with screenshots or a reviewer SHIP. A
  change that only touches `<noscript>` output needs no visual review.

Branch, PR, review and approval routines are in [docs/development-workflow.md](docs/development-workflow.md); follow it in every session.

Sticking to these steps keeps the project history readable and prevents surprises for maintainers. Thanks! 🚀

## Modernization direction

### Maintainer decision, 1 November 2026

The public UI must become fully React by January 2027. All new public UI work
must advance or remain directly compatible with that target. Do not introduce
temporary Flask/Jinja-specific UI optimizations or new public markup that must
be rewritten for the React host. Reuse portable React routes, components and
API data loaders, and migrate existing mostly-React pages once their behavior,
localization, tracking and SEO are verified. Admin UI is outside this scope.
Preserve existing accounts, authentication, URLs and form/API contracts. Apache
may route explicitly migrated page GETs to the React host while APIs, writes,
authentication and administration retain their existing handlers. Prepare and
verify production routing before asking for its activation approval.

For architecture and migration work, read [the maintainer's modernization context](docs/modernization-context.txt)
and [the initial assessment](docs/modernization-assessment.md) before proposing changes.
The context is guidance, not an approved replacement specification.

- Preserve existing functionality, public URLs where practical, MongoDB data,
  accounts, administrative workflows, accessibility, localization and SEO.
- Inspect the relevant implementation and frontend consumers first. Separate
  verified facts, maintainer decisions, recommendations, open questions and risks.
- Migrate incrementally. Measure performance before attributing limitations to
  Flask or choosing a backend replacement. Go is preferred for evaluation, not
  an approved requirement; React + API + Flask admin is a direction to assess.
- Reuse the existing React foundation. React work also exists in other worktrees:
  see the assessment for the campaign implementation. Absence in this checkout
  does not establish that the project has no React implementation. Check its
  current integration status before creating a competing frontend setup.
- Derive API proposals from real routes, consumers, validation and database
  operations. Document purpose, request/response, authentication, authorization,
  database operations, performance concerns and replaced behavior before
  implementing significant API functionality.
- Verify actual password formats and session behavior; do not assume bcrypt or
  introduce JWT/session sharing by default. Keep current authentication working.
- Significant authentication, database schema, infrastructure, repository
  restructuring and production deployment changes require explicit maintainer
  approval. Examples in the context do not supply that approval. Routine work
  within an already approved scope can proceed.
- Test compatibility and establish rollback before replacing working behavior;
  retire old paths only when safe. Update relevant documentation and changelog.


## Working in this checkout

- The canonical repository is
  <https://github.com/mielenosoitukset-fi/mielenosoitukset_fi/>. Every local clone's
  `origin` points there; the old `botsarefuture/...` URL only redirects.
- `main` is checked out in another worktree, so `git checkout main` fails here. Branch from `origin/main` or add a `git worktree`; symlink the existing `node_modules` into it instead of reinstalling.
- The shared working tree can contain another agent's uncommitted work. Never stage, stash or revert files you did not edit; do your own work in a separate worktree.
- Run Python tests from a worktree with the main checkout's `.venv/bin/python`; pytest imports the package from the current directory, so no venv copy is needed.
- `mielenosoitukset_fi/static/frontend/manifest.json` and the hashed `assets/*` it names must be regenerated (`npm run build`) in the same commit as their source. A bot's conflict resolution can leave stale hashes behind.
- A `codex://threads/<uuid>` reference maps to `~/.codex/sessions/<date>/rollout-*-<uuid>.jsonl`; read that file when a Codex conversation is needed but not available as a thread reference.

## Public UI ownership and copy

- Before building or changing a public screen, read [the design system](docs/design-system/README.md): tokens, component guidelines, copy rules and the *Consistency* table that settles where existing pages differ. Reuse its components and tokens; if a rule changes, update that folder in the same PR.
- Maintainer instruction (1 November 2026): no new Flask surface for public UI. New behaviour goes into the Go API plus React; reusing an existing Flask page or endpoint is fine, adding a route, view or template is not.
- The target is a standalone React app that does not need Flask at runtime, not Flask-hosted islands. Treat island props (`react_detail.py` and similar) as a bridge to keep correct, not as the contract to extend; new copy and URLs belong in the TypeScript catalog/config the host will use.
- The public site is Finnish-only today. Keep the localization plumbing, prefer existing msgids, and when a new string is required leave `en`/`sv` copy to human translators rather than machine-guessing it.
- The catalogs already fail `msgfmt` on duplicate msgids and the compiled `.mo` files are committed, so a new msgid stays untranslated until a human edits and recompiles. `msgid "Takaisin"` currently maps to `"Starts at "` in `en`.

## Production host

- `ssh lc-main-root` reaches production as root; the React host is `mielenosoitukset-public.service`, released under `/opt/mielenosoitukset-public`, routed by `/etc/apache2/mielenosoitukset-react-ssr.conf`. Paths and rollback are in `docs/react-ssr-app.md`.
- Production Flask config is `/var/www/mielenosoitukset_fi/config.yaml` with `MONGO_URI`/`MONGO_DBNAME` (not `MONGODB_URI`); Gunicorn listens on `/var/www/mielenosoitukset_fi/mielenosoitus.sock`.

## Repeatable listing verification

For changes to the shared React listings, use
`python3.12 scripts/verify_react_listings.py all --output-dir /tmp/moso-listing-qa`
with the project development dependencies and Node 22.12+. The `check` and
`capture` modes support focused reruns without ad hoc duplicate commands.
Keep visual output outside the repository. Passing this script is technical
verification, not the independent visual SHIP required above.

## Keeping sessions cheap

Most of a session's cost is not what it writes but what it re-reads: the
instructions and tool list on every turn, and the whole conversation so far.
A session that grew from 74k to 213k tokens per turn paid for every earlier
command output many times over.

- One task per session. Start a fresh session for a new task with a self-contained
  brief instead of continuing a long one.
- Never print unbounded output. Pipe `curl`, `gh run view --log-failed`, `gh api`
  and `journalctl` through `head`, `tail`, `grep` or `jq`, or write to a file. The
  hook in `.claude/hooks/quiet-commands.py` blocks the common cases and says how
  to retry.
- Arm auto-merge (`gh pr merge --auto --merge`) rather than waiting at all; it is
  enabled on the repository and the queue does the waiting. Use a background loop on
  `gh pr checks` only when you need to see the result in this session, never a poll in
  chat.
- Read only the lines of a file you need.
- Add user-facing notes under `changelog.d/`, never to `CHANGELOG.md`, so pull
  requests do not conflict and need no repeat CI runs.

## Times and dates

GitHub, CI, the servers and `date -u` report UTC, while the maintainer reads Helsinki
time. Convert before quoting anything: `TZ=Europe/Helsinki date -jf '%Y-%m-%dT%H:%M:%SZ'
'2026-11-13T13:05:06Z'` on macOS, or `TZ=Europe/Helsinki date -d '2026-11-13 13:05 UTC'`
elsewhere. Name the zone (`15:05 EET`, or `16:05 EEST` in summer), and read a bare time
in a note, report or commit message as Helsinki time.

## Coordinating sessions

The maintainer drops ideas into one conversation, the coordinator, which knows the
project. The coordinator stays thin so it stays cheap:

- It does not implement. Each idea becomes a fresh session with a complete brief
  (task, files, what done looks like, the model and caveman rules from the user's
  instructions). Small answers and one-line edits stay in the coordinator.
- It writes the queue and open decisions to the shared notes folder and to
  `docs/decisions.md`, not only to chat, so a new coordinator can take over by reading them.
- It arms auto-merge (`gh pr merge --auto --merge`) on pull requests whose required
  checks and review threads pass, instead of watching them, and lets the queue validate
  each against the current tip. If one needs a change while it is queued, it takes the
  entry out first. It stops and asks for anything that changes data, authentication,
  privileges or sends email.
- Hand over by context size, not turn count. When a turn needs more than about 120k
  tokens of context, or when the queue is empty and a new topic starts, write a
  hand-over note (queue, sessions in flight with their ids, open decisions, what was
  verified) in the shared notes folder and let the maintainer start a fresh coordinator
  from it. A long conversation costs context size times turns, so size is the signal.
- A session reports to whoever started it, and that link does not move. So every brief
  says: put the result in the pull request and in the notes file, and message the
  coordinator only when blocked. Before handing over, the old coordinator sends each
  session in flight the new coordinator's id (or the notes file path) and tells it to
  report there. The hand-over note lists those ids so the new coordinator can check
  each one.

The coordinator also always uses the caveman style in chat, and gives every session the
cheapest model that can do the job (read-only work on the smallest model, routine work
on a mid-size one, only hard design or security work on the largest) with a lower
reasoning effort for mechanical work.

### Merging

Every change reaches `main` through the GitHub merge queue: `gh pr merge`,
`gh pr merge --merge-queue` and the UI Merge button all enqueue, and nothing is picked up
on its own, so a green pull request waits until someone queues or arms it. Do not bypass
the queue with `--admin`.

The queue merges with merge commits, builds and merges at most eight entries at once and
merges a single entry without waiting. It re-runs `python-tests` on the tip the change
will land on, so a branch that has only fallen behind needs no rebase; a real conflict is
different, because the queue drops the entry, so resolve it in the branch. Settings and
the script that applied them are in
[docs/github-organization-migration.md](docs/github-organization-migration.md).

- Queue a pull request when its required checks are green and its review threads are
  resolved. The queue then validates it against `main` plus the entries ahead of it.
- Arm auto-merge instead of watching it: `gh pr merge --auto --merge` merges, or
  enqueues when the queue is required, as soon as the checks and threads pass. A
  session can then end. It does not bypass anything, but it does merge without a
  further look, so do not arm a draft or a pull request whose conflicts you have not
  resolved.
- Keep the merge commit. Squash only a single-commit cleanup, and rebase only a branch
  that is already linear.
- The green/yellow/red traffic-light routine is retired. The queue serialises merges and
  rebuilds a group after dropping a failing entry, so the retry loop across pull
  requests no longer exists. A repeated failure still means stopping and fixing the
  cause, as any failing check does.

### Backlogs of 20–40 pull requests

- Finish independent pull requests and arm auto-merge as each is ready. Do not hold
  the next pull request until the previous one merges, poll CI in chat, or use an
  agent as a serial merge coordinator. GitHub handles eligibility, checks and order.
- The limits are 8 concurrent queue builds and 8 entries per merge, with ALLGREEN,
  minimum 1, wait 0 and a 60-minute check timeout. Later entries can build while
  earlier ones run, including the changes ahead of them. Eight entries is a cap,
  not a promise of eight-entry batches or one CI run per batch.
- A lone eligible pull request has no batching delay; it still needs the required
  queue checks. Do not bypass protection or add a five-minute wait for it.
- Intervene for failed checks, unresolved review threads or actual conflicts. Fix
  the cause, dequeue before pushing if needed, then re-arm auto-merge. Do not
  reorder the queue casually: moving an entry ahead can invalidate later builds.
- Dependent pull requests wait for their parent to merge and must target `main`
  before they are queued. Retarget manually when kept branches prevent GitHub
  doing it. Never enqueue a child against its parent's branch.
- Raising concurrency beyond 8 needs measured throughput and failure evidence:
  larger groups increase the work invalidated by a failure.

### While a pull request is in the queue

A queued branch is frozen. GitHub refuses pushes to it and says "Merging is blocked: a
pull request for this branch has been added to a merge queue … cannot be updated". That
is the queue working, not a failed update:

- Do not merge `main` into a queued branch or press "Update branch". The queue rebuilds
  the entry on the current tip, so a branch that is only behind needs nothing.
- If the pull request needs a change while it is queued, take it out first, push, then
  arm auto-merge again. `gh pr view <n> --json id` gives the node id for
  `gh api graphql -f query='mutation { dequeuePullRequest(input:{id:"<node id>"}) { pullRequest { number } } }'`,
  or use "Remove from queue" in the UI.
- A queue build costs about one test run. If it fails, the entry leaves the queue with
  the reason in the timeline and the next entry is rebuilt without it.
- Enqueuing consumes an armed auto-merge request, so a pull request that was dequeued and
  pushed again has to be armed again.

### Stacked pull requests

When a change depends on another pull request that has not merged, stack it instead of
basing a branch on another branch by hand. The `gh stack` command (the `github/gh-stack`
extension) is installed:

- `gh stack init` starts a stack on the default branch, `gh stack add <branch>` puts
  another layer on top, and `gh stack init b1 b2 b3` adopts branches you already made.
- `gh stack submit` pushes every layer, opens or updates the pull requests and links
  them as a stack; `gh stack sync` brings the local stack up to date and `gh stack view`
  shows it.
- Merge from the bottom: each layer lands on `main` in turn and the ones above are
  retargeted, so do not re-base them by hand. `gh stack rebase` replays a stack when its
  trunk has moved.
- Link the chain before its bottom layer is queued: `gh stack link 1149 1150` refuses a
  pull request that is already in the queue ("it is queued for merge"), and
  `gh stack submit` links only what is not queued yet.
- A branch based on another pull request's branch by hand is not retargeted here, because
  the repository keeps merged branches (`delete_branch_on_merge` is off) and GitHub only
  moves children when the base branch is deleted. Do not queue the child while the parent
  is open, because its entry would carry the parent's commits; after the parent merges,
  move it with `gh pr edit <child> --base main`.

### Resolving conflicts in files that usually conflict

- `mielenosoitukset_fi/static/frontend/**` and
  `mielenosoitukset_fi/templates/kampanja/_*_fallback.html` are build output. Never
  hand-merge them: take either side, run `npm run build`, and commit the rebuild.
- `package-lock.json` is regenerated, not merged: take either side and run
  `npm install` so the lockfile matches `package.json`.
- `changelog.d/` entries are separate files, so they do not conflict. Never resolve a
  conflict by editing `CHANGELOG.md`.
- `docs/decisions.md`, `roadmap.md` and `TODO.md` are append-only in practice: keep both
  sides' entries instead of choosing one.
- Anything else is ordinary source: rebase on `main` and resolve by hand.
