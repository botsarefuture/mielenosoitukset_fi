# Decisions log

Maintainer decisions and the reasoning behind them, so that people and agents do
not have to rediscover them from chat history or old PRs. Read this before
starting work. When the maintainer decides something new, add it here in the same
PR that implements it, newest first within each section. Keep each entry short:
the decision, why it was made, where it lives, and anything still open.

Related standing rules live in [AGENTS.md](../AGENTS.md),
[the development workflow](development-workflow.md) and
[the design system](design-system/README.md).

## Process and approvals

- **GitHub handles the merge backlog (2026-11-13).** For 20–40 independent PRs,
  agents arm auto-merge as each is ready and continue other work. Do not serialize
  them by watching each merge. GitHub owns waiting and order; agents intervene for
  failed checks, conflicts and review feedback. A lone PR keeps minimum 1 and
  wait 0, with required queue tests intact. Dependent PRs enter only after the
  parent merges and their base is `main`. This avoids an AI traffic-police role
  without weakening protections.

- **Size the merge queue for 40 waiting pull requests (2026-11-13).** Raise both
  `max_entries_to_build` and `max_entries_to_merge` from 3 to 8. Keep MERGE,
  ALLGREEN, minimum 1, wait 0 and the 60-minute timeout. With roughly 13-minute
  checks, 40 ready PRs need about 14 waves at concurrency 3 (over three hours)
  versus 5 waves at concurrency 8 (about 65 minutes), assuming full utilization
  and no failures. These are parallel waves, not five total CI runs: ALLGREEN
  still checks each entry. Merge size is a separate limit. A failed entry
  invalidates later groups that include it, so do not go higher without evidence. The script exposes both limits as
  CLI flags and preserves every other rule, condition and bypass actor. Roll back
  by setting both flags to 3 after reviewing `--dry-run`.

- **Agents arm auto-merge (2026-11-13).** Auto-merge is enabled on the repository, so
  a session should run `gh pr merge --auto --merge` on a pull request whose checks are
  running and end, instead of watching CI and spending tokens on it. It bypasses
  nothing: the required checks, review threads and the merge queue still decide, and an
  armed pull request is enqueued when they pass. Do not arm a draft, or a pull request
  whose conflicts are unresolved.
- **Stack dependent work with `gh stack` (2026-11-13).** When a pull request depends on
  another that has not merged, agents build a stack with the installed `github/gh-stack`
  extension and merge it from the bottom, instead of chaining branches by hand and
  re-targeting them one by one. Merges still go through the queue.
- **Merge queue on `main` (2026-11-13).** Enabled after the move to the organization:
  merge commits, ALLGREEN, at most 3 entries built and merged, minimum 1, no grouping
  wait, 60-minute check timeout; `python-tests` runs on `merge_group`. Auto-merge stays
  allowed, so an armed pull request is enqueued instead of merging directly. The
  green/yellow/red traffic-light routine is retired because the queue serialises merges
  and rebuilds groups. Settings and rollback are in
  [github-organization-migration.md](github-organization-migration.md).
- **Repository ownership moves to the `mielenosoitukset-fi` organization (2026-11-13).**
  The canonical URL is https://github.com/mielenosoitukset-fi/mielenosoitukset_fi/;
  the old `botsarefuture/mielenosoitukset_fi` links and remotes keep working through
  GitHub's redirect. `python-tests` now also runs on `merge_group` so it can stay the
  required check once the merge queue is switched on. Deployment hosts, credentials,
  paths and environment variables are unchanged. The reference audit, the external and
  server-side follow-ups and the post-transfer checks are in
  [github-organization-migration.md](github-organization-migration.md).
  Merge queue: prepared but off. The intended settings (merge commits, ALLGREEN,
  batches of 3) and the script that applies them only after explicit approval are
  in that document.
- **Changelog notes (2026-11-12).** New user-facing changes use separate files in
  `changelog.d/` to avoid pull requests conflicting in `CHANGELOG.md`. Render the
  notes with the existing history using `scripts/render_changelog.py`; release
  numbering and publication remain open.
- **Merging (2026-11-11).** The maintainer approves merging and deploying once the
  required tests pass, plus an independent visual SHIP for UI changes. No separate
  question is needed per PR.
- **Production changes need a revert path (2026-11-11).** Production data,
  permission and operations changes are approved when they can be undone. Before the
  change, take a backup or record the prior state. Report where the backup is and how
  to revert. Anything without a revert path (permanent deletes without an export,
  real emails to real people) still needs an explicit yes.
- **Review threads block merging (historical; auto-merge policy superseded 2026-11-13).** The `main` ruleset requires every review thread
  to be resolved and the `python-tests` check to pass. Auto-merge is turned off.
  Resolve bot review threads by fixing the issue, or by replying with the reason it
  does not apply.
- **CI runner choice.** The repository variable `MOSO_CI_RUNS_ON` decides where
  same-repository CI runs. Pull requests from forks always run on GitHub-hosted
  runners, because the repository is public.
- **Questions to the maintainer** are asked as a numbered list, with a suggested
  answer under each question.

## Authentication and sessions

- **Auth bridge: Go and React ask Flask who is signed in (2026-11-12).** The
  maintainer approved starting the move of authentication towards React and Go,
  keeping login on Flask if possible. Chosen after comparing four options: Go asks
  Flask's read-only `/api/session` (with an optional ≤5 s cache, default off).
  Rejected: validating the cookie in Go and Flask-minted tokens (revocation
  through `auth_epoch`, suspension and password resets would lag or be
  reimplemented), and full auth in Go (no rollback). Two off-by-default flags,
  `AUTH_BRIDGE_SCOPES` (Flask) and `AUTH_BRIDGE_ENABLED` (Go); rollback is removing
  either. Login, MFA and password pages are not moved; that needs a new approval.
  Details and the evidence: [auth-bridge.md](auth-bridge.md).
- **Signing out is a POST with a token (2026-11-13).** Sign-out was a plain GET
  link, so a prefetch, crawler or stray hover could end a session (the Apache log
  showed single and triple `GET /users/auth/logout` requests). Now a GET only shows
  a confirmation page (and answers 204 to prefetch/prerender), and only a POST with a
  stateless signed token tied to the account signs out. The account menu opens on
  click or keyboard, not hover. The token is not single-use and not bound to the
  session cookie (stateless by design; it only needs to be unguessable for an
  attacker page, and the worst case is a forced sign-out); it expires after 12 h and
  an expired or wrong one sends the visitor to the confirmation page. After a
  failed server read is confirmed through the bridge the menu has no token and
  links to that confirmation page. Revert: restore the old route in
  `users/BPs/auth.py`; no data changes.
- **A failed session read is "unknown", not "signed out" (2026-11-13).** The React
  host marks a visitor whose cookie it could not read as `unverified`; the page asks
  the bridge and shows an error with retry instead of a sign-in prompt. Known edges:
  `unverified` is set for any failed read with a cookie, and the campaign and
  fundraising pages still treat an unverified visitor as a guest and redirect
  (reviewer findings 3 and 4 on #1145); fix them if they show up in practice.
- **Anonymous organization flash message (2026-11-12).** Shown through the bridge:
  an anonymous visitor only learns that a message is waiting, nothing about
  memberships.

## Public site

- **React plus Go only (1 November 2026).** See AGENTS.md: there is no new Flask
  public surface, and the target is a standalone React app by January 2027.
- **Copy is Finnish-only.** New strings go in the TypeScript catalog
  (`frontend/src/app/i18n.ts`) and URLs in `config.urls`. English and Swedish are
  left to human translators; the catalog falls back to Finnish until then.
- **No icons in page headings.** Icons go beside labels, tiles and cards. Cancel
  buttons use the danger style.
- **`/developer` waits for a session scope (2026-11-12).** The pages are per-user and
  private, so React needs a new signed-in read; proposal in
  [developer-react-proposal.md](developer-react-proposal.md). `/download_material/<id>`
  stays in Flask as a download redirect.
- **Home page continuation (2026-11-12).** The Pride banner after the event grid was
  mistaken for "more events", so it now follows a continuation of the listing (#1098).
  Open: research suggests replacing the scroll auto-load with "Tänään" and
  "Viikonloppuna" shortcut chips and one clear button into `/demonstrations`.

## City admins

- **Target of at least two city admins per city, never enforced (2026-11-11).**
  Coverage counts distinct active accounts whose unrevoked city grant includes
  `ACCEPT_DEMO`, the same rule as `active_city_admins_for_city`.
- **Helsinki is moderated by the national admin team (2026-11-11).** Helsinki has a
  very large amount of activism and a small, fragmented scene in which people in
  different organisations may not cooperate because of conflicts. A local admin
  could therefore not review everyone's events neutrally. Helsinki shows
  "Valtakunnallinen tiimi", never recruits, and does not accept applications. The
  list is hardcoded in `admin_city_bp.py`, `go-api/city_admin_status.go` and
  `frontend/src/app/city-admin-route.ts`. Open: make it a `city_settings` flag if
  another city needs the same treatment.
  The public React city page shows the "Valtakunnallinen tiimi" note for the `national`
  band (2026-11-12), with no recruiting link; copy lives in `i18n.ts` `cityAdmin`.
- **The `/cities` list keeps its rule (2026-11-11).** It shows places that have had
  or will have demonstrations, plus enabled cities. Enabling a city used to be a
  workaround for appointing a city admin. The accounts dashboard can create a city
  admin for any of the 309 cities, and saving enables the city.
- **Public recruiting note (2026-11-11).** City pages with no city admin, or only one,
  invite visitors to help. A city without an admin says the national team reviews its
  events. Only a coverage band (`none`, `single`, `team`, `national`) is public, never
  names or counts.
- **Applications cover every city (2026-11-12).** The application form offers all
  catalog cities except Helsinki, whether or not they have demonstrations or are
  enabled; the Go handler already accepted any catalog key. The `/cities` list rule
  is unchanged. The form groups cities by coverage band under "Tarvitsemme adminia"
  (`none`), "Tarvitsemme lisää admineja" (`single`) and "Admintiimi on jo olemassa"
  (`team`), so applicants see where help is needed. Go serves all bands in one
  cached read, `GET /api/cities/admin-status`; still only the band, never names or
  counts.
  Cities with a full team stay selectable: backups are needed and admins rotate.
- **Applications (2026-11-11, #1091).** Signed-in users with a confirmed account
  apply at `/kaupunkiadmin`.
  - Go stores the application. A Flask job turns it into a `city_admin_application`
    case and notifies the national team in the inbox.
  - Local admins of the same cities can read and comment, but only global admins
    decide. Approving never grants rights; the role is granted in the accounts
    dashboard.
  - A user can have only one open application.
  - Retention and privacy notice: see the entry after this one.
  - **Unique index against simultaneous submissions (proposed, awaiting maintainer
    approval).** Partial unique index on `user_id` for open applications; a
    duplicate key returns 409 `APPLY_OPEN_EXISTS`. Not created yet. Details, the
    pre-check script and rollback are in
    [city-admin-applications.md](city-admin-applications.md#duplicate-submissions-proposed-awaiting-maintainer-approval).
- **Application retention and privacy notice (2026-11-12, approved by the
  maintainer 2026-11-12).** Open applications are kept until decided. After a
  decision, the free text (`about`, `activism`, `references`, `consent_at`) is erased
  from declined and withdrawn applications after 90 days and from approved ones after
  365 days. The row stays with user, cities, status and dates, so the one-open-
  application rule and the applicant's status list keep working. The erasing job
  `purge_city_admin_applications` (daily) does nothing unless
  `CITY_ADMIN_APPLICATION_RETENTION_ENABLED` is set; it ships off. The Finnish
  notice is shown on the form (`cityAdminApplyCopy.privacy*` in `i18n.ts`), and the
  numbers there must match `RETENTION_DAYS`. The flag may be switched on after a
  backup of `city_admin_applications`, with the dry-run count checked first. The
  same numbers are stated in `PrivacyContent.tsx` (`/privacy`, data list and
  retention section); change all three places together.
- **Case access (2026-11-11).** City admins' grants include `LIST_CASES`,
  `VIEW_CASE` and `EDIT_CASE`. The 2026-11-11 update is tagged
  `case_access_granted_for: issue-778`, so it can be reverted in one update.

## Preview images

- **New generated design (2026-11-11, #1090).** Generated previews are 1200×630 and
  use the site's brand style. An organizer's own uploaded picture is preferred over
  the generated one (#1092). All existing previews were regenerated, with a backup
  and a restore script kept on the production host. Old CDN objects are never
  overwritten.
- **Organizer design templates (PREVIEW-02, backlog).** Organizers can upload their
  own templates, saved in the organization panel and reused for recurring
  demonstrations. Admins can upload them for a specific series. See `TODO.md`.

## Operations

- **Backups (2026-11-11).** A nightly core dump skips `super_audit_logs` and
  `admin_logs`, which are most of the database. A weekly full dump includes them.
  The Mongo tools authenticate the same way PyMongo does. Restoring from a backup
  is still unproven until the recovery drill (OPS-02) is done. Open: an off-site
  copy and its encryption key holder, and the alert channel. See
  [backups.md](backups.md).
- **Heavy database jobs make the Go API's startup fragile (2026-11-11).** A full
  dump loaded the database enough that a Go API restart failed its startup database
  check, causing about 35 seconds of 503s. Do not restart the public services while
  a full dump or another heavy database job runs.
- **Analytics beacons (2026-11-11).** `POST /api/analytics/event` is served by Go,
  with `SITE_ANALYTICS_ENABLED=true` matching Flask. Pageviews and vitals stay in
  Flask. Roll back by removing the routing rule.

- **Hash developer app `client_secret` last (2026-11-13).** Flask and Go both store
  `client_secret` in plaintext; token secrets are already hashed. The maintainer
  pre-approved hashing it (a `client_secret_hash` marker, Flask and Go changed together,
  existing apps rotate) but only after everything else has moved to React and the Flask
  templates are retired. Needs a backup and an independent reviewer SHIP at that time.

## Fundraising page

- **Pre-launch mode (2026-11-13).** `/keräys` is public without login or campaign publication and is not linked from anywhere (no nav, footer, sitemap or front page; the existing link on `/kampanja/` shows only once the campaign is published). Until Helsinki's date reaches `start_date` it shows "Pienkeräys aukeaa", hides IBAN/BIC and payment links (in the page, the embedded bootstrap and `GET /api/fundraising/details`) and is `noindex, follow`. The opening day is the existing `start_date`, so no extra hardcoded instant. The account block needs `details_confirmed`, `publication_state: active`, organiser and recipient to be filled in; nothing is invented.
