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
- **Review threads block merging.** The `main` ruleset requires every review thread
  to be resolved and the `python-tests` check to pass. Auto-merge is turned off.
  Resolve bot review threads by fixing the issue, or by replying with the reason it
  does not apply.
- **CI runner choice.** The repository variable `MOSO_CI_RUNS_ON` decides where
  same-repository CI runs. Pull requests from forks always run on GitHub-hosted
  runners, because the repository is public.
- **Questions to the maintainer** are asked as a numbered list, with a suggested
  answer under each question.

## Public site

- **React plus Go only (1 November 2026).** See AGENTS.md: there is no new Flask
  public surface, and the target is a standalone React app by January 2027.
- **Copy is Finnish-only.** New strings go in the TypeScript catalog
  (`frontend/src/app/i18n.ts`) and URLs in `config.urls`. English and Swedish are
  left to human translators; the catalog falls back to Finnish until then.
- **No icons in page headings.** Icons go beside labels, tiles and cards. Cancel
  buttons use the danger style.
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
  - Open: retention periods and the privacy notice wording, and whether to add a
    unique index against simultaneous submissions.
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
