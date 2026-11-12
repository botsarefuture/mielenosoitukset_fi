# Agents Guide

This repository often gets help from external agents (human or AI). Follow these rules every time you touch the codebase:

Before starting, read [the decisions log](docs/decisions.md): it records maintainer decisions and their reasons, so they don't need to be rediscovered from history. When the maintainer decides something new, add it there in the same PR.

1. **Always update the changelog**  
   - Add an entry to `CHANGELOG.md` for every user-facing change (features, fixes, refactors that matter).  
   - If a change launches immediately, put it under the latest released version. Otherwise, log it under `## UNRELEASED`.  
   - Use concise bullets describing the change and its impact.

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
