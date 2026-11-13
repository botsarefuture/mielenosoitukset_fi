# TODO

Everything still to do, in one list. Updated 13 November 2026.

This refresh checks current main, GitHub issue/PR states, the latest coordinator
conversation and handover, and recorded production evidence. Checked means the
specific item is done; it does not close its wider workstream. In-flight PRs are
a dated snapshot: check their live state before acting.

- **Sources:** `roadmap.md` (IDs like UI-06), `docs/decisions.md`, current GitHub issues and PRs, deployment evidence and coordinator notes. The old `BLOCKERS.md` on `claude/vibrant-gates-syjhk4` is historical context, not a current status source.
- **Where status lives:** priorities, owners and acceptance evidence stay in `roadmap.md`; this file is the checklist. When an item lands, tick it here and update the roadmap entry.
- **Approval:** merging and deploying need no separate approval once tests pass (plus a visual SHIP for UI). Items marked *(approval)* touch data, authentication, sessions, privileges or real email and need the maintainer's go-ahead (see `docs/development-workflow.md`).

## Now

- [x] **Production virtual environment and security dependencies:** production runs `/opt/mielenosoitukset-fi/venv`; Pillow 13.0.0, PyJWT 2.15.1 and PyMongo 4.19.0 are verified (#1118). The earlier system-Python blocker is resolved; see `docs/production-deployment.md`.
- [x] **#778 city admins and cases (P0):** fixed and live; issue closed 11 November 2026. All eight active city grants received the case capabilities, tagged `case_access_granted_for: issue-778` for rollback. Broader role/audit acceptance remains SEC-03.
- [x] **#1029 far-future events:** generation capped (#1064); on 10 November 2026 the cleanup removed 68,642 generated occurrences after 2028-11-10 from three series, backed up on the production host first. Helsinki showed 238 upcoming events after that cleanup.
- [x] **#984 support replies:** acknowledge queue persistence before recording the queued reply and audit receipt; redact unconfirmed outcomes (DATA-04).

## In flight (13 November snapshot)

- [ ] **Safe sign-out (#1154):** POST with an account-bound token, harmless GET confirmation/prefetch handling, and click-open account menus. Coordinator records auth and visual reviews; finish final-head checks/queue, then verify on production that a plain GET does not sign anyone out. This is in progress, not a new account-migration task.
- [ ] **Campaign redesign v2.2:** approved mockup build is under way. Deliver the page/date-driven states, revised volunteer form (roles/area, no phone; API/privacy update), party-interest UI, then its backend after #1146. Preserve publication/donation gates; use independent visual review and security/privacy review for data/email work. No implementation PR was open at this refresh.
- [ ] **Pride banner carriers (#1155):** UI-only form is in review, `volunteer_form=false`, submission stubbed. The Go/storage/mail double-opt-in, unsubscribe, retention and privacy work remains a separate second part using the now-merged #1146, with security/privacy and visual acceptance before activation.
- [ ] **Fundraising opening reminder (#1146 / FUND-02):** implementation is merged and off by default. Confirm final security/privacy and visual acceptance, then separately approve/provision the unique index and activation. First real bulk send still needs the maintainer's go; optional results-message delivery remains undecided. See [docs/fundraising-reminder.md](docs/fundraising-reminder.md).

## Public site in React (UI-06, due January 2027)

Already on the React host: home, listings (all, city, tag, today), detail and series, calendar, cities, submit, organization profile, information pages, Pride, campaign, fundraising and contact.

- [ ] `/report` error report form. It needs a session-scope token like `/contact`. *(approval: session change)*
- [x] `/status`: React SSR with read-only Go `/api/status`, bounded cached database check and HTTP 200 on dependency/API failure. React routing is active (production Apache include checked 13 November). Keep outstanding real-data visual acceptance in the page-by-page review below; the original sandbox limitation is not a current activation blocker.
- [x] Token pages, `/cancel_demonstration/<token>`: React page with a read-only Go `/api/cancellation-links/<token>`; routing active since 12 Nov 2026.
- [ ] Token pages that write on GET: `/kampanja/confirm/<token>`, `/auth/confirm_email/<token>` and `/orgs/accept_invite` confirm or join in the GET itself and redirect (login needed for the invite). Moving them needs a decision: split into a React page plus a POST, or keep Flask.
- [ ] Account pages: login, register and next steps, settings, password reset, forced password and identity change, MFA verification, public profile `/<username>`. *(approval: authentication flows)*
- [x] `/api-docs/`: build-time Markdown on the React host; OpenAPI YAML stays in Flask (#1068).
- [x] `/developer` overview and app detail: React screens, Go reads/write controls and Apache routing are live (#1130, #1134, #1138, #1139, #1143, #1145; verified 13 November). Session-read failures no longer look like sign-out. Scope/access requests and the `/download_material/<id>` redirect remain Flask. See [developer controls](docs/developer-react-write-controls.md).
- [ ] Hash `client_secret` for developer apps (Flask and Go both store it plaintext today). **Pre-approved by the maintainer on 13 November 2026; do it last, after every other page has moved to React and the Flask templates are retired (so after January 2027), as one planned change.** Plan: add a `client_secret_hash` schema marker, change `developer_bp.py` (create and rotate) and the Go write routes together to store only the hash, run a one-off migration, and tell owners of existing apps to rotate, since plaintext cannot be hashed back into a shown secret. Needs a backup, an independent security reviewer SHIP and a revert note first. Not urgent: tokens are already hashed, and the risk is only a database or backup leak.
- [x] City-admin coverage/recruiting notes, Helsinki's national-team label and `/kaupunkiadmin` application/status flow are implemented (#1091, #1106, #1110); all Finnish cities except Helsinki are selectable, grouped by coverage. Duplicate-application index approval remains below.
- [ ] Retire the Flask templates each migrated page leaves behind as rollback, once its React page has been stable for a while.
- [ ] Final page-by-page review of copy and generic UI patterns (#960, #770, #833).
  - Done (12 November 2026): submit headings without icons, red conflict cancel, one `…` character, no exclamation marks, mielenosoitus instead of tapahtuma in the submit form.
  - Retry buttons (12 November 2026): calendar notices now use `detail-button`. Kept as is with reason: the chat widget's compact buttons, Pride's `button-secondary` and the home page's `home-button`, which belong to their own page styles.
  - Brand name written "Mielenosoitukset.fi" in page texts (#1135). Decision (12 November 2026): the demonstration detail page keeps "tapahtuma" in places, because its catalog must match the Flask msgids (`tests/test_public_detail_copy_parity.py`); changing it needs new msgids and human en/sv translation, to be done when `/demonstration/<id>` leaves Flask.
  - Open: a detailed visual walk of the city, organization, status, privacy and cancel pages with real data (only grep checks so far); `scripts/submit_visual_capture.py` captures the legacy Flask page, not the React host, so React reviews need `frontend/server.mjs` captures.

## Move APIs to Go

Proposal: [Public write API migration contracts, approval questions and rollout order](docs/go-write-api-proposal.md).

- [ ] Status checks omitted from `/api/status`: Flask's configured cache `set("_status_ping", True, timeout=5)` and initialized S3 client's `list_buckets()`. Go has no equivalent Flask-owned cache/storage client; do not call Flask during rendering or substitute Go response-cache health. Migrate their ownership before restoring these checks.

Maintainer direction, 10 November 2026: when a page is redesigned or moved to React, its Flask endpoints move to the Go API too, in the same work or later. Still on Flask:

- [ ] `/api/session` and its scopes (`organization_id`, `translation_join`, `contact_form`). *(approval: session)* The read-only Go bridge and scopes were activated and verified 12 November ([auth-bridge.md](docs/auth-bridge.md)); the underlying session endpoint still lives in Flask.
- [ ] `POST /contact`: rate limits, one-time token, honeypot, validation and email.
- [ ] `POST /organization/<id>/save_suggestion`: stores the suggestion, opens a case and notifies moderators.
- [ ] `POST /suggest_change/<demo_id>`: compares proposed fields and Markdown, stores a demonstration suggestion, opens a case and notifies moderators; GET/HEAD now belongs to the React host.
- [ ] `POST /kampanja/api/volunteers` and `/kampanja/confirm/<token>`.
- [ ] `POST /upcoming/translations/join`. *(approval: permissions)*
- [x] Analytics event `POST /api/analytics/event`: Go activated 11 November; the Flask-equivalent counter cross-check and POST routing are complete (`SITE_ANALYTICS_ENABLED=true`; `docs/go-public-api.md`). Production routing rechecked 13 November.
- [ ] Analytics pageview `/api/analytics/pageview`: still Flask; visitor-secret/locale decisions remain prerequisites.
- [x] Fundraising details: `GET /api/fundraising/details` serves a file-backed copy, the host falls back to the bundled `fundraising.json` ([docs/go-fundraising-details.md](docs/go-fundraising-details.md)). Open: database collection plus admin editing.

## UI follow-ups from reviews

From the maintainer, 10 November 2026:

- [x] Front page: center the search bar.
- [x] `/demonstrations` (Tulevat mielenosoitukset): the search area is too heavy. Make it lighter and simpler. Secondary filters fold behind "Suodattimet" on phones.
- [x] `/cities`: sorted alphabetically in letter groups with an A–Ö jump row, compact enough for every city in Finland.

From the visual reviews:

- [x] Shared inline success message: more space above than below (`.flash-message--inline`).
- [x] Charcoal "Poista suodattimet" secondary button and the pale grey light secondary button.
- [x] Underline next to the invite "+" on event cards.
- [x] Organizer guide: step titles are centred at 390 px.
- [x] Campaign page: on phones the form's error message is below the fold after an empty submit.
- [x] Fundraising, open state: the MobilePay links sit far apart.
- [x] Card times use `12:00 – 14:00` instead of `12.00–14.00` (reuse the detail clock helper; keep raw API clocks unchanged).
- [x] The PRIDE badge text has weak contrast; map markers cover city labels.
- [x] Mobile "Suodattimet" toggle: show an open/closed chevron tied to `aria-expanded`.
- [x] Listing buttons and links: use `:focus-visible`; text inputs retain `:focus`.

The checked visual follow-ups above record implementation, not a blanket visual SHIP. Items without final-source captures and independent review remain in the page-by-page visual backlog; do not treat an old sandbox limitation as evidence about today's environment.

- [x] Keep action menus outside the scroll viewport (#743); issue closed. The per-snapshot visual acceptance rule above still applies.
- [x] Anonymous organization suggestion feedback: the auth-bridge scopes were activated and verified in production 12 November, so the pending-message notice can reach anonymous visitors without exposing memberships (`docs/auth-bridge.md`).

## Security and permissions

- [ ] **SEC-01:** release acceptance evidence for the MFA challenge (#901).
- [ ] **SEC-03:** broader role and audit acceptance after #917/#918/#919.
- [x] **SEC-04:** token and approval lifecycle: revocation, expiry, replay, idempotent decisions. Inventory and open questions in [docs/token-lifecycle.md](docs/token-lifecycle.md).
- [ ] **SEC-05:** review incident #912/#913 protections before touching related code.
- [ ] Harden privileged admin user actions (#547), organization membership and invites (#550, #342), and the organization admin panel (#549).
- [ ] **QA-01:** finish the individual review of authentication and permission tests. QA-01j (#966), QA-01k (#973 via #964) and QA-01m (#1114, superseding #979) are merged. Remaining: other authentication and permission test files, see the roadmap.

## Data, jobs and integrations

- [ ] **DATA-01:** public pagination and totals, verified with the API and the browser together.
- [ ] **DATA-02:** fence analytics workers and coordinate rebuild pruning (#908).
- [ ] **DATA-03:** analytics correctness, access and pagination (#551); `demonstrations` COLLSCAN slow queries; the admin overview rendering 28,604 rows.
- [ ] **DATA-04:** email queue retries and idempotency, queue/history crash consistency, job leadership and database error handling (#176).
  - [x] #955/#956: bounded failed/abandoned email claims and per-message recovery receipts are implemented. Real SMTP/scheduler acceptance and ambiguous-delivery reconciliation remain open.
  - [x] #984: acknowledged support reply enqueue and correlated case receipt, without strict-mode retries.
  - [x] #771: dedicated outgoing-reply history merged in #977; the issue is closed. Canonical audit references/content retention and queue/history crash consistency remain separate follow-ups.
- [ ] **DATA-05:** preview images failing (#579), Cloudflare rate limiting on normal use (#580), Socket.IO reconnect storm (#640).
- [ ] **DATA-06:** module TODO issues (#391–#394) and creating users from invites (#387).
  - [x] Settings/configuration issues #196 and #226 are closed as completed; do not list them as new implementation work.
- [ ] **DATA-07:** multi-day demonstrations as their own duration, separate from recurring series.
- [x] **CITY-01 dashboard/countdown:** #968 is merged; #967 was closed as implemented/deployed on 11 November.
- [x] **CITY-01 in-app notices:** #975 is merged; stored deadlines/reset policy are implemented in #958.
- [ ] **CITY-01 remaining:** live inbox/email/scheduler acceptance, deployed deadline configuration and any separately agreed reassignment follow-up. Do not rebuild the existing notices or countdown.
- [x] **CITY-02 outbox implementation:** #964 is merged; #963 is closed. Bounded discovery/claims, same-message updates, backoff and unknown-send handling are implemented.
- [ ] **CITY-02 release evidence:** verify provider staging send/edit, target permissions, sweep/query plans and production enablement. The issue-closing deployment note alone does not establish these earlier acceptance gates.
- [ ] **CASE-01/02:** let submitters answer case questions and follow progress (#976).
- [x] Recurring demonstration cancellation breaks: #620 redone on current main with inclusive date ranges, validation and frozen-child protection.
- [ ] Production performance and hosting review (#859).

## Privacy and audit logging

- [x] City-admin application retention: #1109 merged, privacy copy implemented, and the retention job enabled after backup/dry run on 12 November (coordinator rollout record). No application text was erased at enablement. Preserve the documented retention periods and backup-based recovery limits.
- [ ] City-admin applications: proposed partial unique index for one open application per user still needs explicit approval and backup/rollback preparation; see `docs/city-admin-applications.md`.

- [ ] **PRIV-03 / #596:** GDPR retention and consent review with the privacy owner. #597 (user deletion cleanup) is far behind and overlaps later deletion work (#887); redo it fresh.
- [ ] **PRIV-01:** one versioned audit event schema for `admin_logs`, `super_audit_logs`, `demo_audit_logs`, `login_logs`, `board_audit_logs` and future sources, with stable event, actor, subject, time, outcome, source, request and correlation fields, plus adapters for legacy entries.
- [ ] **PRIV-02:** audit every security- or privacy-relevant read and write, including log access. Make writes failure-aware (retries or a durable queue, metrics, alerts), UTC and tamper-evident.
- [ ] One investigation UI with cross-source search and correlation, behind the right permissions.
- [ ] Field allowlists and central redaction before storage; never store passwords, credentials, authorization headers, cookies or raw tokens.
- [ ] Per-log retention, deletion, anonymization and backup rules; documented access, export and incident procedures.
- [ ] Tests for completeness, authorization, redaction, retention, migration and correlation, plus periodic production sampling.
- [ ] A recorded GDPR review with the responsible privacy or legal owner. Tests alone are not proof of compliance.

## Operations

- [ ] **OPS-01 remaining:** off-site copy/encryption ownership, failure alert channel, recovery ownership and evidence from the first weekly full run. Update the obsolete “no backups” status in `docs/backups.md`.
  - [x] Nightly core and weekly full backup timers are installed and active; core archives exist (read-only production check, 13 November). This is not proof of restoration.
- [ ] **OPS-02:** authorized recovery exercises with recorded RPO and RTO.
- [ ] **OPS-03:** review Web Vitals once there are enough samples.
- [ ] **OPS-04:** keep exact-build deployment, rollback and CDN contracts; measure burst/coalescing behavior and rehearse held-admission recovery in isolation.
  - [x] #1153 merged and deployed: native pending coalescing, immutable release reuse, exact-SHA test evidence, one locked deployment/routing transaction, migration readiness and successful-release receipt. Flask/Go/React health and receipt match `ecd86476…` on 13 November.
- [ ] Watch the next deploys that change routing: confirm the new probe retries (#1050) and that no 503 appears after restarts.

## Localization and docs

- [x] **I18N-01:** inventory untranslated strings and catalog gaps per route family in `docs/i18n-inventory.md` (regenerate with `scripts/i18n_inventory.py`); English and Swedish translation itself stays with human translators.
- [ ] **I18N-02:** standardize backend, API, moderation and email messages (#582, #553).
- [ ] **DOC-01:** user and moderator guides (#563).
- [ ] **DOC-02:** keep `roadmap.md`, this file, issues and release evidence aligned. Refresh `BLOCKERS.md`.

## Product ideas (after core work)

- [ ] Front page as a full list of upcoming demonstrations remains a product decision; #1100 already delivered the separate scroll-to-continue action and Today/Weekend shortcuts.
- [ ] Demonstration categories with preset options (for example Palestiina, ilmasto, ihmisoikeudet) so people can filter by topic. Decide how they relate to the existing free-form tags first.
- [ ] **ENGAGE-01:** optional newsletter of relevant upcoming events.
- [ ] **ENGAGE-02:** optional email digest of a user's own notifications.
- [ ] **PRODUCT-01:** broader societal events (#583), following tags (#117), city and tag email subscriptions (#121).
- [ ] Count visitors who browse without JavaScript (a `<noscript>` pixel; filter bots) to decide how much the no-JS fallback matters.
- [ ] **FUND-02:** reminder signup is merged in #1146 and off; see [docs/fundraising-reminder.md](docs/fundraising-reminder.md) and the activation checklist above. Do not reopen the old “calendar only or email?” design question. Activation, the first real send and optional results delivery remain separate gates.
- [ ] **FUND-01:** confirm complete official/payment details and explicitly activate donations for the valid period. The page/purpose text (#1141/#1142) and optional header bar (#1147) are merged; `details_confirmed`, `show_bar` and `show_header_link` remain false in main. Merging UI does not authorize payments or opening the campaign.
- [ ] **PREVIEW-02: organizer design templates for preview images.** Let organizations upload their own template for a demo's preview image:
  - Formats: InDesign, Photoshop and Illustrator, or the open-source alternatives the maintainer named ("design craft, photo craft, vector craft"). Decide which formats can be rendered server-side and how much of the file to support, for example named text layers for title, date and place.
  - Save templates in the organization panel. Organizers pick one when they submit a new demonstration, and it applies automatically to that organization's recurring demonstrations.
  - Global admins can upload templates for a specific recurring series, for example a weekly "Loppu kansanmurhalle" demonstration.
  - Open questions: file size limits and malware scanning for uploads, a fallback to the default generated preview, and who may edit a shared template.

## Maintenance

- [x] **CLEAN-01:** removed the orphaned `list_legacy.html`, template `submit.css` and eleven tracked `.bak` stylesheets after checking every reference (intentional Flask rollback templates kept).
- [x] Retire the legacy card renderer `static/js/demo-card-render.js` and `_modals/_demo-card-template.html`: no template loaded them since CLEAN-01; their renderer-only tests were removed.
- [ ] Check that the React listing tests cover what the removed legacy loader tests checked: slow attendance requests surviving append and cancelled on eviction or search; stale search responses ignored; HTTP failure offering retry without erasing appended results; delayed append keeping keyboard focus and not restoring old filter pages.
- [ ] **CLEAN-02:** consolidate legacy palettes and hero geometry.
- [ ] **CLEAN-04:** keep a finite exception list for dynamic styles and a CSS cache contract.
- [ ] Admin dashboard workflow: pagination, previews and clearer edit fields (#552); organization form UI (#178).
- [ ] Unit tests for remaining routes and functions (#174).

### Open pull requests to close or decide (CLEAN-03)

- [ ] Close after the security update: #948, #527, #457, #445.
- [x] Closed as already done on main (10 November 2026): #351, #293, #477, #570, #585.
- [x] Closed as outdated (10 November 2026): #911, #598 (thanked the contributor).
- [ ] Decide: #440 (flask-limiter 4.0, a major version), #849 (project memory guidance), #617 (preview teardown; are previews still used?), #599 (`Config.reload` path, external contributor), #1011 (submit migration check; most of it is on main).

## Done recently

- [x] Organization repository migration and merge queue (#1148–#1151): live 8/8, ALLGREEN, minimum 1, wait 0; agents arm auto-merge, use `gh stack` for dependencies and dequeue before pushing fixes.
- [x] #1100 home continuation/Today/Weekend shortcuts; #1115/#1133 cancellation-link React page and active routing.
- [x] Developer panel Go writes/routing/resilient session reads (#1139/#1143/#1145), with client-secret hashing deliberately deferred until last.
- [x] Fundraising prelaunch, purpose copy and optional header-bar implementation (#1141/#1142/#1147); publication and donation switches remain separate.

- [x] Information pages, Pride, campaign, fundraising and contact moved to React (#1040, #1043, #1046, #1047, #1048).
- [x] Contrast and shared listing states (#1045); richer `/info` layout (#1049).
- [x] No-JavaScript fallbacks kept light and out of visual review (#1044).
- [x] Deploys no longer briefly close the site (#1050).
- [x] Overflow fixes, hero consistency, translator welcome email, role-based admin dashboard, follow button rules, MFA in settings.
- [x] `analytics` COLLSCAN, `d_analytics` overcount repair and in-place `prepped_analytics` (see `docs/mongodb-analytics-performance.md`).
