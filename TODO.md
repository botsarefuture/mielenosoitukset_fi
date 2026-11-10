# TODO

Everything still to do, in one list. Updated 10 November 2026.

- **Sources:** `roadmap.md` (IDs like UI-06), open GitHub issues (`#123`), open pull requests, review follow-ups and `BLOCKERS.md` on `claude/vibrant-gates-syjhk4`.
- **Where status lives:** priorities, owners and acceptance evidence stay in `roadmap.md`; this file is the checklist. When an item lands, tick it here and update the roadmap entry.
- **Approval:** merging and deploying need no separate approval once tests pass (plus a visual SHIP for UI). Items marked *(approval)* touch data, authentication, sessions, privileges or real email and need the maintainer's go-ahead (see `docs/development-workflow.md`).

## Now

- [ ] **Production virtual environment, then the security dependency update.** Pillow 11.0.0 → 13.0.0, PyJWT 2.10.1 → 2.15.1 and PyMongo 4.6.3 → 4.19.0 (#1053) merged but could not deploy: Flask runs on the read-only system Python, and `deploy/install_dependencies.py` only installs into an app-owned venv (see `docs/production-deployment.md`). The pins were reverted to unblock deploys. Next: create the venv, point Gunicorn and `PRODUCTION_PYTHON` at it, verify, then re-apply #1053. Pillow decodes uploaded images and has a critical advisory. *(approval: production infrastructure)*
- [ ] **#778 city admins and cases (P0):** #917 is merged and the issue says it was revalidated. Confirm on production that a city admin can open and act on their city's cases, then close the issue.
- [ ] **#1029 far-future events:** the database holds events dated 2094–3100, so Helsinki shows 60,884 upcoming events. Find where they come from (recurring generation is the likely source), clean them up *(approval: data change)* and stop new ones.
- [ ] **#984 support replies:** a reply is recorded as sent before the email is safely queued. Fix the order and error handling (DATA-04).
- [ ] **Panel host root password:** it was pasted in a Codex thread on 3 November. Rotate it; never use it.

## Public site in React (UI-06, due January 2027)

Already on the React host: home, listings (all, city, tag, today), detail and series, calendar, cities, submit, organization profile, information pages, Pride, campaign, fundraising and contact.

- [ ] `/report` error report form. It needs a session-scope token like `/contact`. *(approval: session change)*
- [ ] `/status` service status page. It needs a JSON endpoint for the health checks.
- [ ] Token pages: `/cancel_demonstration/<token>`, `/confirm/<token>`, `/confirm_email/<token>`, `/accept_invite`.
- [ ] Account pages: login, register and next steps, settings, password reset, forced password and identity change, MFA verification, public profile `/<username>`. *(approval: authentication flows)*
- [ ] Secondary tools: `/developer`, `/api-docs/`, demo material download.
- [ ] Retire the Flask templates each migrated page leaves behind as rollback, once its React page has been stable for a while.
- [ ] Final page-by-page review of copy and generic UI patterns (#960, #770, #833).

## Move APIs to Go

Maintainer direction, 10 November 2026: when a page is redesigned or moved to React, its Flask endpoints move to the Go API too, in the same work or later. Still on Flask:

- [ ] `/api/session` and its scopes (`organization_id`, `translation_join`, `contact_form`). *(approval: session)*
- [ ] `POST /contact`: rate limits, one-time token, honeypot, validation and email.
- [ ] `POST /organization/<id>/save_suggestion`: stores the suggestion, opens a case and notifies moderators.
- [ ] `POST /kampanja/api/volunteers` and `/kampanja/confirm/<token>`.
- [ ] `POST /upcoming/translations/join`. *(approval: permissions)*
- [ ] Analytics beacons `/api/analytics/pageview` and `/api/analytics/event`.
- [ ] Fundraising details: today bundled from `fundraising.json` into the host; a Go endpoint would let it change without a host deploy.

## UI follow-ups from reviews

From the maintainer, 10 November 2026:

- [ ] Profile page: the red notification count sits under the bell instead of on top of it. Other pages look right.
- [ ] Front page: center the search bar.
- [ ] `/demonstrations` (Tulevat mielenosoitukset): the search area is too heavy. Make it lighter and simpler.
- [ ] `/cities`: the city list is too much. Sort it alphabetically and make it scale to every city in Finland (for example grouped by first letter, with search).

From the visual reviews:

- [ ] `/contact`: hide the "Yhteydenottolomake" card while the form is switched off.
- [ ] Shared inline success message: more space above than below (`.flash-message--inline`).
- [ ] Charcoal "Poista suodattimet" secondary button and the pale grey light secondary button.
- [ ] Underline next to the invite "+" on event cards.
- [ ] Organizer guide: step titles are centred at 390 px.
- [ ] Campaign page: on phones the form's error message is below the fold after an empty submit.
- [ ] Contact form: the subject select is 6 px shorter than the text fields.
- [ ] Fundraising, open state: the MobilePay links sit far apart.
- [ ] Card times use `12:00 – 14:00` instead of `12.00–14.00`; the PRIDE badge text has weak contrast; map markers cover city labels.
- [ ] Keep action menus outside the scroll viewport (#743).
- [ ] Organization page: an anonymous visitor who sends a fill-in suggestion never sees the "Kiitos! Ehdotuksesi on tallennettu" message, because the React page only fetches flash messages for signed-in members of that organization. Needs the session endpoint to report pending messages for everyone (session change: maintainer approval).

## Security and permissions

- [ ] **SEC-01:** release acceptance evidence for the MFA challenge (#901).
- [ ] **SEC-03:** broader role and audit acceptance after #917/#918/#919.
- [ ] **SEC-04:** token and approval lifecycle: revocation, expiry, replay, idempotent decisions.
- [ ] **SEC-05:** review incident #912/#913 protections before touching related code.
- [ ] Harden privileged admin user actions (#547), organization membership and invites (#550, #342), and the organization admin panel (#549).
- [ ] **QA-01:** finish the individual review of authentication and permission tests. Open: #979 identity test audit (rebase on `CHANGELOG.md`, then merge), QA-01j, QA-01k.

## Data, jobs and integrations

- [ ] **DATA-01:** public pagination and totals, verified with the API and the browser together.
- [ ] **DATA-02:** fence analytics workers and coordinate rebuild pruning (#908).
- [ ] **DATA-03:** analytics correctness, access and pagination (#551); `demonstrations` COLLSCAN slow queries; the admin overview rendering 28,604 rows.
- [ ] **DATA-04:** email queue retries and idempotency, case reply history (#771), job leadership, database error handling (#176).
- [ ] **DATA-05:** preview images failing (#579), Cloudflare rate limiting on normal use (#580), Socket.IO reconnect storm (#640).
- [ ] **DATA-06:** module TODO issues (#391–#394), settings and configuration (#196, #226), creating users from invites (#387).
- [ ] **DATA-07:** multi-day demonstrations as their own duration, separate from recurring series.
- [ ] **CITY-01:** city review dashboard with an authoritative deadline countdown (#967).
- [ ] **CITY-02:** urgent pending-event alerts to Telegram through a durable outbox (#963).
- [ ] **CASE-01/02:** let submitters answer case questions and follow progress (#976).
- [ ] Recurring demonstration cancellation breaks: #620 is useful but over 1,000 commits behind; rebase or redo it.
- [ ] Production performance and hosting review (#859).

## Privacy and audit logging

- [ ] **PRIV-03 / #596:** GDPR retention and consent review with the privacy owner. #597 (user deletion cleanup) is far behind and overlaps later deletion work (#887); redo it fresh.
- [ ] **PRIV-01:** one versioned audit event schema for `admin_logs`, `super_audit_logs`, `demo_audit_logs`, `login_logs`, `board_audit_logs` and future sources, with stable event, actor, subject, time, outcome, source, request and correlation fields, plus adapters for legacy entries.
- [ ] **PRIV-02:** audit every security- or privacy-relevant read and write, including log access. Make writes failure-aware (retries or a durable queue, metrics, alerts), UTC and tamper-evident.
- [ ] One investigation UI with cross-source search and correlation, behind the right permissions.
- [ ] Field allowlists and central redaction before storage; never store passwords, credentials, authorization headers, cookies or raw tokens.
- [ ] Per-log retention, deletion, anonymization and backup rules; documented access, export and incident procedures.
- [ ] Tests for completeness, authorization, redaction, retention, migration and correlation, plus periodic production sampling.
- [ ] A recorded GDPR review with the responsible privacy or legal owner. Tests alone are not proof of compliance.

## Operations

- [ ] **OPS-01:** backup coverage and freshness, failure alerts, recovery access and ownership.
- [ ] **OPS-02:** authorized recovery exercises with recorded RPO and RTO.
- [ ] **OPS-03:** review Web Vitals once there are enough samples.
- [ ] **OPS-04:** keep exact-build deployment, rollback and CDN contracts.
- [ ] Watch the next deploys that change routing: confirm the new probe retries (#1050) and that no 503 appears after restarts.

## Localization and docs

- [ ] **I18N-01:** inventory untranslated strings and catalog gaps per route family; English and Swedish copy comes from human translators.
- [ ] **I18N-02:** standardize backend, API, moderation and email messages (#582, #553).
- [ ] **DOC-01:** user and moderator guides (#563).
- [ ] **DOC-02:** keep `roadmap.md`, this file, issues and release evidence aligned. Refresh `BLOCKERS.md`.

## Product ideas (after core work)

- [ ] Front page as a list of upcoming demonstrations.
- [ ] Demonstration categories with preset options (for example Palestiina, ilmasto, ihmisoikeudet) so people can filter by topic. Decide how they relate to the existing free-form tags first.
- [ ] **ENGAGE-01:** optional newsletter of relevant upcoming events.
- [ ] **ENGAGE-02:** optional email digest of a user's own notifications.
- [ ] **PRODUCT-01:** broader societal events (#583), following tags (#117), city and tag email subscriptions (#121).
- [ ] Count visitors who browse without JavaScript (a `<noscript>` pixel; filter bots) to decide how much the no-JS fallback matters.
- [ ] **FUND-01:** fill in the official fundraising details when they are confirmed, then open donations.

## Maintenance

- [ ] **CLEAN-01:** remove orphaned `list_legacy.html`, template `submit.css` and tracked backups after checking references.
- [ ] **CLEAN-02:** consolidate legacy palettes and hero geometry.
- [ ] **CLEAN-04:** keep a finite exception list for dynamic styles and a CSS cache contract.
- [ ] Admin dashboard workflow: pagination, previews and clearer edit fields (#552); organization form UI (#178).
- [ ] Unit tests for remaining routes and functions (#174).

### Open pull requests to close or decide (CLEAN-03)

- [ ] Close after the security update: #948, #527, #457, #445.
- [ ] Close as already done on main: #351 (flask-cors 6.0.0), #293 (python-dateutil 2.9.0.post0), #477 (Docker setup, see #537), #570 (board approval, landed in other PRs), #585 (agent workflow hooks, now in `AGENTS.md`).
- [ ] Close as outdated: #911 (CodeRabbit docs), #598 (email without TLS, testing only; thank the contributor).
- [ ] Decide: #440 (flask-limiter 4.0, a major version), #849 (project memory guidance), #617 (preview teardown; are previews still used?), #599 (`Config.reload` path, external contributor), #1011 (submit migration check; most of it is on main).

## Done recently

- [x] Information pages, Pride, campaign, fundraising and contact moved to React (#1040, #1043, #1046, #1047, #1048).
- [x] Contrast and shared listing states (#1045); richer `/info` layout (#1049).
- [x] No-JavaScript fallbacks kept light and out of visual review (#1044).
- [x] Deploys no longer briefly close the site (#1050).
- [x] Overflow fixes, hero consistency, translator welcome email, role-based admin dashboard, follow button rules, MFA in settings.
- [x] `analytics` COLLSCAN, `d_analytics` overcount repair and in-place `prepped_analytics` (see `docs/mongodb-analytics-performance.md`).
