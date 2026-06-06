# Changelog

**Note:** This changelog is **not fully up-to-date**. Some recent features, fixes, or changes may not be reflected here.

## UNRELEASED

### Fixed
* The project now requires Python 3.12 across local metadata, CI, and Docker; deprecated `datetime.utcnow()` calls now use a shared modern UTC helper without changing the existing naive-UTC database format, and `python-dateutil` was updated to remove its Python 3.12 UTC deprecation warning.
* Demonstration detail galleries now avoid aggressively upscaling undersized event photos, presenting them sharply over a softened backdrop instead; new uploads keep more JPEG detail and respect camera orientation, and public image guidance now recommends dimensions that match the wide gallery layout.
* Streamlined `_path_value` logic in test route smoke tests and enhanced payload generation for better test coverage and maintainability.

### Added
* Added paikkakunta-scoped admin grants so national admins can assign users demonstration review permissions for one or more Finnish municipalities while keeping national/global admins above local reviewers.
* Added an automatic MongoDB migration runner and registered the city-key backfill so future app starts apply safe, tracked data migrations without manual script execution.
* Pinned the Docker Compose development LocalStack image to a community release so local S3 startup no longer depends on a floating image that may require a commercial auth token.
* Docker Compose development now points the app at `config.compose.dev.yaml` through `CONFIG_YAML_PATH`, avoiding a nested bind mount that can prevent the backend container from starting on Docker Desktop.
* Added a token-protected admin MCP endpoint at `/api/admin/mcp` with foundation tools for listing, reading, creating, and updating demonstrations, organizations, and support cases so AI agents can begin driving core admin dashboard work without browser automation.
* Added `scripts/hash_admin_mcp_token.py` and `docs/admin_mcp.md` to help provision hashed MCP bearer tokens safely instead of storing raw admin-control tokens in config.
* Admin MCP now also accepts OAuth-style bearer tokens validated from configured JWT claims (`iss`, `aud`, scopes), making it compatible with the OpenAI MCP bearer-token pattern instead of requiring only project-specific static tokens.
* Admin MCP now also accepts the repository's existing API tokens directly, so the easiest supported login path is to create a normal user/app API token and pass it to OpenAI as the MCP bearer token.
* Admin MCP now exposes OAuth discovery, dynamic client registration, an admin consent screen, and PKCE-backed authorization-code token exchange, so ChatGPT developer mode can connect with the OpenAI-supported OAuth login flow instead of requiring only manual bearer token provisioning.
* Public demo submission now asks for explicit confirmation when a possible duplicate is detected, instead of silently retrying the submission and making successful sends look broken.
* Public demo submission duplicate warnings are now less trigger-happy on weak title similarity, so real users are less likely to get blocked by false duplicate alarms.
* `/ohjeet/` now includes clearer submission troubleshooting advice, including when to retry and what details to send to support, and the public submit form now links directly to that help.
* Added `scripts/setup_preview_environment.sh` so preview repository variables and secrets can be printed or written through `gh` after the preview server is provisioned.
* Added automated PR preview environments that build same-repository branches in isolated Docker containers on a dedicated preview server, post a sticky preview URL comment on the PR, and tear the preview down when the PR closes.
* Preview Caddy snippets now use per-PR matcher names, so multiple active previews no longer collide when Caddy reloads the imported routes.
* Added `docs/roadmap_2026.md`, a project roadmap that groups the April 27, 2026 backlog into admin UX, multilinguality, reliability, and cleanup workstreams with milestones for closing the 2026 baseline issues.
* Added regression coverage for duplicate demo submissions, duplicate-submission merge handling, and background-job demo audit/history recording so CI catches duplicate creation and demo ID drift earlier.
* Added a source-driven surface manifest for Flask routes, background jobs, and Socket.IO events so CI fails when the application surface changes without an explicit test coverage update.
* Route-surface manifest now includes blueprint URL prefixes so changes to `url_prefix` in blueprint registration (e.g., `/users/`, `/api/`, `/api/admin/demo/`) are detected by CI and block merge unless tests are explicitly updated.
* Added `pytest`-based test infrastructure, dev dependencies, and API contract checks that keep `mielenosoitukset_fi/api/api.yaml` aligned with the implemented `/api` routes.
* Added comprehensive dependency validation tests via `test_dependencies.py` that check for missing imports, conflicting dependencies, and unpinned versions, preventing unnoticed dependency hell.
* Added `pip-audit` and `pipdeptree` to dev dependencies for auditing security vulnerabilities and analyzing dependency trees.
* Added a `unittest`-based regression suite for core helpers, flashing, error handlers, and access-control decorators, plus a GitHub Actions workflow that runs the suite automatically on pull requests and pushes to `main`.
* CI/CD reliability improvements: added healthcheck to LocalStack in `compose.test.yml`, increased test job timeout to 30 minutes, increased service startup wait from 120s to 240s, and added progress/debug output for easier troubleshooting.
* Added `TESTING_WORKFLOWS_LOCALLY.md` guide with instructions for running GitHub Actions workflows locally via `act` or manual testing.
* Added broad seeded smoke coverage for registered Flask routes, Socket.IO chat events, and background job execution so CI now catches breakage across more of the application surface.
* Added headless Chromium end-to-end smoke coverage for public browsing plus authenticated user, developer, and admin flows, and wired GitHub Actions to install Playwright before running the suite.
* `start-dev.sh` now gracefully shuts down and reopens Firefox when importing the development certificate, removing the need for manual browser closure during setup.
* `AGENTS.md` guide describing expectations for external contributors (always update changelog, validate work, etc.) so every agent follows the same workflow.
* Expanded production-level codebase documentation in `docs/codebase.md` covering architecture, data flows, and ops.
* Public API documentation at `/api-docs/` with downloadable OpenAPI spec and expanded `docs/api.md` coverage.
* API docs now render Markdown with dark-mode styling on `/api-docs/`.
* API docs layout refreshed with clearer typography and section styling for readability.
* API docs now explicitly state authentication requirements per endpoint.
* Added a table-of-contents sidebar to the public API docs page.
* Footer now links to developer docs and API docs include contact info.
* API docs now explain how to create, list, and revoke API tokens.
* API docs include a step-by-step token usage example.
* Token access now requires admin approval; settings page gained an API keys tab with request + list/revoke UI, plus admin can approve/deny requests.
* Developer panel added for managing apps and app tokens; token model updated (48h short, 90d long via exchange, categories for user/app/system/session).
* Developer dashboard and app pages now clarify scopes (incl. submit_demonstrations), show secrets inline, and footer link points to /developer/.
* Scope request flow added: app owners can request extra scopes with reasons; admins can approve/deny in a new Kehittäjähallinta view (includes dev-panel access requests and user app listing).
* Token usage is logged for auditing when tokens are validated.
* Multi-image demo galleries (admin URL list + detail-page carousel) that default cards/previews to the first image.
* Central admin timeline at `/admin/demo/audit/logs` showing the latest demonstration audit entries, with filters (including auto/manual actions) and quick links back to per-demo history/diffs.
* Admin sidebar now includes a one-click link to the audit timeline for faster access.
* Added `/admin/demo/tokens` view for superusers to inspect and revoke approve/reject/preview/edit links (with creator + expiry info and a sidebar shortcut).
* Introduced a `super_audit_logs` stream that records every demo audit event with full request metadata for ultimate traceability.
* Admin log writes are now enriched with actor/request/process metadata and mirrored into the `super_audit_logs` stream so every privileged action is captured centrally.
* Admin dashboard quick links now surface the Super Audit log so superusers can jump directly into the high-fidelity event stream.
* Super Audit UI can safely render entries containing raw `ObjectId`/datetime values thanks to automatic JSON-safe serialization.
* Pride näkyväksi sivu löytyy nyt myös polusta `/pride` ja sisältää kartan, joka piirtää kaikki Pride-mielenosoitukset.
* Added a reusable `showToast` helper and updated the register next steps page to show resend-confirmation feedback with the same inline toasts as the rest of auth.
* Pride näkyväksi sivu hyödyntää nyt samaa listatyylien kokonaisuutta kuin päälistaus, jotta tapahtumakortit piirtyvät oikein.
* Pride-kortit näyttävät oikein tyylitettyinä (tagit, ikonit, värit) lisäämällä puuttuvan `css/demo.css`-tyylin kampanjasivulle.
* Pride-kartan merkinnät ja legendan värit vastaavat toisiaan (yhtenäinen violetin/rubiinin sävy) selkeyttääkseen mitä pisteet kuvaavat.
* Pride-kampanjasivun tapahtumakortit on sovitettu lähemmäs peruslistan ulkoasua (värit, tagit, ikonit), säilyttäen Pride-teeman.

### Fixed
* City-scoped admin grants no longer satisfy unscoped demo route permission checks, and user edits now revoke existing ObjectId-backed city grants correctly.
* Runtime models and user/profile helpers now resolve the active MongoDB database per operation, preventing stale database handles after app/test database resets.
* Admin and suggestion route editors now allow the same street or route point to be added multiple times, so march routes can loop through a road more than once.
* User settings change notifications now have the missing `auth/settings_changed.html` email template, preventing settings updates from reporting a template lookup error.
* New demonstration admin notification emails are now sent directly during the background notification job instead of being re-queued into a second email worker queue, so failed admin alert deliveries are surfaced as job errors instead of being silently marked complete.
* PR preview workflow now posts an immediate spinning-up comment before building the preview, then edits the same comment into the final live URL once deploy completes.
* PR preview workflow now stages the deploy script under the dedicated preview user's home directory instead of `/tmp`, avoiding permission failures on the server-side copy step.
* Recurring demo admin create/edit now preserve organizer data even if organizer cards are removed and re-added out of sequence, and the shared recurring description editor now loads its real CKEditor initializer.
* Admin recurring demonstration creation now accepts the current create-form recurrence fields and city selection without crashing the dashboard redirect after save.
* Organizer contact cards on demonstration detail pages now wrap long website and email links on mobile instead of overflowing the layout.
* PR preview workflow now sources `deploy/preview_deploy.sh` from the default branch instead of the PR checkout, so older branches can still trigger preview deployments successfully.
* Preview environments now connect to their own MongoDB container by container name and start a dedicated mail container, so PR previews can resolve their services reliably and finish seeding instead of stalling on startup.
* Preview deploys now print explicit progress markers during setup, seeding, app startup, and Caddy reload so long-running previews remain observable in GitHub Actions.
* Preview database seeding now reads the correct argument positions in `deploy/preview_deploy.sh` and normalizes the source URI with `authSource=admin` when needed, preventing previews from failing after Mongo startup.
* Preview Caddy snippets now write directive-only config fragments, matching the host `import` layout so reloads no longer fail on invalid site-block syntax.
* Preview deploys now restart Caddy through passwordless sudo, which lets the preview user publish routes without broad server access while keeping the host route publication step working.
* Preview Caddy snippets now live in the shared `caddy` group so the host service can actually read them during reload while the preview user still writes the files.
* PR preview URLs now use `pr-<id>.mielenosoitukset.fi` instead of the deeper `previews.*` nesting, which keeps them within Cloudflare's normal first-level subdomain coverage.
* Preview config files are now written world-readable inside the container mount, so the app process can load its per-PR config instead of crashing on permission denied.
* Preview Caddy routing now points directly at each app container's Docker IP, avoiding the flaky localhost publish path on the preview host.
* Public guides at `/ohjeet` are now accessible without login, and the public footer links to them directly so the documentation is easier to find.
* Admin user list now paginates server-side and searches display names in addition to usernames and emails, making the user control panel easier to scan at larger scale.
* Fixed the config loader so the Flask session secret stays separate from the S3 secret key; preview login pages no longer 500 because `session` is unavailable.
* Added a branch-sync helper script that rebases the current branch onto `origin/main` before PR creation, so future feature branches stay closer to the base branch and conflict-prone drift is caught earlier.
* Developer app detail now shows the actual global rate-limit defaults instead of placeholder `N/A` values, making the permissions and requests panel easier to read.
* Developer app detail now hides rate-limit policy text in environments where limiter enforcement is disabled, so the preview/admin UI no longer implies limits are active when they are not.
* Developer permissions/request panel now separates current rights, current limits, and new-scope requests into clearer sections with better spacing and helper copy.
* Admin dashboard theme switching now applies explicit `light`/`dark` modes consistently in the shared admin shell, aligning Bootstrap theme variables with the custom theme classes and improving sidebar/footer readability.
* Admin dashboard reporter info popups now use theme-aware body text colors, fixing unreadable white-on-white submitter details in the modal.
* Demo cards keep cover images centered without stretching, preventing warped previews across list views.
* Tag normalization now strips leading `#` in public submit and demo change suggestion flows, preventing accidental `##tag` rendering.
* Aligned `botocore` pin with `boto3==1.42.74` in `requirements.txt` to keep pip dependency resolution valid.
* Test teardown now explicitly stops background job helpers, closes deferred MongoDB clients, avoids initializing the rate limiter when disabled, and marks email retry timers as daemon threads so CI no longer risks hanging after `pytest` finishes.
* Re-enabled S3 integration tests in CI by including LocalStack in test services with corrected health check logic that properly updates service readiness state, eliminating the previous race condition.
* Health check script for test services now uses per-service timeouts, giving LocalStack 10 seconds (vs. 2) to respond to the health endpoint, preventing premature CI failures on slower runners.
* Fixed `pipdeptree==3.0.10` not being available on PyPI; updated to `2.33.0` (the latest available version).
* CI workflow now passes `CreateBucketConfiguration` with `LocationConstraint` when initializing the LocalStack S3 bucket, fixing `IllegalLocationConstraintException` for non-`us-east-1` regions.
* Admin analytics overview and profile message APIs now serialize Mongo `ObjectId` values safely, preventing 500s in templates and JSON responses.
* Admin organization suggestion review now tolerates legacy suggestion documents that stored edited values outside the `fields` payload.
* Calendar, admin analytics, organization suggestion review, recurring-child listing, and admin media pages no longer fail under the expanded integration smoke suite.
* Admin action link generation in background jobs now avoids request-only locale lookups, preventing “working outside of request context” errors during notification processing.
* Recurring demo processor now uses the configured MongoDB database name instead of forcing `mielenosoitukset`.
* Analytics rollup now reads MongoDB connection settings from the app config, avoiding hardcoded localhost defaults that broke rollups in dev/compose setups.
* Approval/rejection token flows now only mark single-use links as used after the database update is verified, preventing silent failures from consuming links without persisting the decision.
* Approval/rejection token flows now handle read failures during persistence verification, preventing transient errors from causing unexpected 500s.
* On-demand analytics rollups now mark demo events as handled so background aggregation won't double-count them later.
* Token approval/rejection flows now handle post-update read errors gracefully, prompting a retry instead of raising a 500 on transient lookup failures.
* Approving or rejecting via token now updates the demonstration `last_modified` timestamp so audit views reflect the latest change.
* Approving or rejecting via token now records the decision in the demo audit log for better traceability.
* Admin reminder job now skips demonstrations that are already rejected or whose event date is in the past, preventing stale approval emails.
* Pending submission processing now merges duplicate demonstrations (including linked submitter data), reducing duplicate demos created per submission.
* Duplicate submission merges now emit demo audit log entries so the merge history is visible to admins.
* Duplicate submission merges now repoint cancellation tokens so organizer links always target the primary demo.
* Demo cover selection now uses a shared helper across index/list/card rendering to avoid mismatched cover images.
* Screenshot generation now skips demos that already have a preview image, preventing redundant auto previews.
* Demo preview token route now renders even when `follow_meta` isn’t provided (detail template supplies a safe default).
* Background job audit logging no longer crashes when the automatic flag is provided, so scheduled reminder runs complete successfully.
* Audit timeline’s manual/automatic filter now hides background-job entries when you opt to see only manual actions.
* Per-demo analytics view now reads the zero-padded rollup keys correctly, so demonstration analytics charts and counters render real data again.
* Per-demo analytics page now builds rollups on demand when missing, so demos without precomputed analytics still show their view counts.
* Analytics ingestion now records UTC-aware timestamps and normalizes naive events during rollup, preventing aggregation from breaking on missing timezone info.
* Demonstration view logging now uses a client beacon endpoint, ensuring cache hits (e.g., Cloudflare) are recorded once without double-counting.
* Background job auditing now skips entries when no fields changed, reducing noise in the global audit log.
* Token management view gained a “revoke all unused links” action for superusers.
* Token revocations (single or bulk) now emit per-demo audit entries to capture who revoked which link.
* Admin analytics summary now computes total and average views across all matching demos instead of the paginated slice, keeping stats consistent across pages.
* Login now clearly instructs unverified users to confirm their email before signing in, including a reminder that a fresh link was sent.
* Token validation no longer double-logs API usage when the `token_required` decorator already records usage per request.
* Pride näkyväksi sivun tilastot laskevat kaupungit oikein ja käyttävät samaa korttinäkymää kuin päälistaus, jotta tapahtumat näkyvät yhtenäisesti.
* Pride näkyväksi -sivun sydänanimaatio on rajattu hero-osioon, jotta koristeet eivät leiju sisällön reunoilla.
* Added `scripts/setup_preview_environment.sh` so preview repository variables and secrets can be printed or written through `gh` after the preview server is provisioned.
* Added automated PR preview environments that build same-repository branches in isolated Docker containers on a dedicated preview server, post a sticky preview URL comment on the PR, and tear the preview down when the PR closes.
* Added `docs/roadmap_2026.md`, a project roadmap that groups the April 27, 2026 backlog into admin UX, multilinguality, reliability, and cleanup workstreams with milestones for closing the 2026 baseline issues.

### Changed
* Removed the in-repository Mastobot runtime and Mastobot-specific admin counters from the main repo now that standalone cutover is handled in `mielenosoitukset-fi/mastobot`.

* Recurring demonstration create and edit now use the same admin form path, reducing duplicate UI behavior and making the recurring-demo admin clearer to maintain.
* Admin demonstration create pages no longer show edit-link or duplication controls before a demo exists, reducing dead functionality in the admin UI.
* Demo edit suggestion form now has a pill-based march route editor (Enter/comma to add points) so users can propose route changes without wrestling with a single text field.
* Demo edit suggestion form now uses the same pill-style add/remove flow for tags and clarifies that tags should be entered without `#`.
* Demo edit suggestion form now uses a rich-text description editor, matching the public submit flow for easier content fixes.
* Demo edit suggestion preview now shows the same Finnish-formatted event date as the detail page instead of the raw ISO date.
* Front page now highlights the Pride näkyväksi campaign with direct links to the campaign page and demo submission flow.
* Pride-tagged demo cards now get a rainbow border treatment across shared card views so Pride events stand out visually.
* Browser demo cards now render through the shared JS renderer on homepage, list, and city views instead of maintaining separate Jinja/card-markup implementations.
* Browser demo cards now rely on the shared card CSS across city, organization, siblings, tag, and Pride views so the same demo renders with the same visual treatment everywhere.
* Application boot now forces the process timezone (and exposes `LOCAL_TIMEZONE`) to Europe/Helsinki so all naive `datetime.now()` calls align with Finnish local time.
* Admin token links that were previously consumed now render a friendly confirmation page instead of returning HTTP 409, making it clear the link has already been used.
* Reuse attempts of admin approve/reject/preview tokens are now logged (including demo audit entries) with IP + metadata so the audit trail captures every invalid link use.
* Approving or rejecting via token now automatically revokes the opposite link, preventing stale approve/reject URLs from being reused after a decision.
* Magic token lifecycle is fully audited: creation now stores actor/request fingerprints, every bind/use/revoke/reuse attempt emits demo + super audit entries, and single/bulk revocations produce structured log payloads.
* Admin stats dashboard rebuilt with a futuristic telemetry layout (live Matomo badges, neon cards, sortable analytics table) for `admin/stats`.
* Admin stats now loads via API, defaults to future demonstrations only, and can optionally fetch Matomo Live data when configured.
* Case list now auto-closes resolved demo cases (approved/rejected/cancelled), shows live counts, and features a redesigned filtering UI for faster support triage.
* Case detail for organization edit suggestions now shows clear before/after diffs, and a background job auto-closes cases when linked demos are accepted/rejected/cancelled.
* Added a scheduled background job to auto-close resolved cases hourly, so stale “open” cases are cleaned up without manual intervention.
* All admin notification emails now use a shared template without emojis, so demo approvals, organization edits, and suggestion alerts present a consistent, professional layout.
* Demonstration detail pages now open a “What do you want to do?” modal before reporting issues so visitors discover the structured edit suggestion form before falling back to a generic error report.
* Demo detail report modal was rebuilt with vanilla JavaScript: the guidance modal, preview, and submission flow now run without jQuery and feel noticeably faster.
* When browsing demo detail pages from `127.0.0.1`/`localhost`, caching is disabled automatically (both response caching and client meta/fetch overrides) so developers always see the latest content.
* Admin dashboard now offers a “clear cache” control for global admins, making it easy to purge stale responses after deployments.
* Admin dashboard routes now emit structured audit logs (matching the new `admin_demo_bp` style) so every panic toggle, cache purge, job action, and analytics query is captured consistently.
* Organization admin routes now emit structured audit logs for every invite, edit, deletion, suggestion review, and membership change, aligning them with the new admin logging standard.
* Login now uses a resend-verification popup so users can request a fresh email without leaving the sign-in page.

## v4.0.0-beta.3 – *Cache & Follow Polish* ✨

### Changed
* **Cache safety improvements**:
  * Added smarter skip logic so authenticated users get isolated cache entries (or bypass when flashes occur) without leaving public endpoints uncached.
  * Demonstration detail, RSS feed, API `/demonstrations`, and debug `/ping` now use the new helpers with per-viewer cache keys, preventing stale/admin-only content from leaking to guests.
* **Follow UI polish**:
  * Demo detail organizer cards now show a compact pill in the top-right corner that toggles between `SEURAA` / `SEURATAAN` with animated star icons.
  * Organization detail pages moved the follow CTA out of the hero banner into a dedicated “Pysy ajan tasalla” card, reusing the same pill interaction for a consistent experience.

## v4.0.0-beta.2 – *Follower Delight Edition* 🌟

### Added
* **Demonstration Cancellation Workflow**:
  * New `/cancel_demonstration/<token>` route for organizers to securely cancel events via email links.
  * Demonstration cancellation request system with admin approval workflow.
  * Auto-generated cancellation tokens sent to all organizers (90-day expiry).
  * Cancellation notifications to attendees and reminder subscribers via email.
  * Admin case management for cancellation requests with approval/rejection actions.
  * Cancelled demonstrations display warning badge on detail pages.

* **Suggestion System for Demonstrations**:
  * New `/suggest_change/<demo_id>` route allowing users to suggest edits to demonstrations.
  * Admin interface for reviewing and applying suggestions (`/admin/demo/suggestions/`).
  * Per-field suggestion tracking with original vs. suggested value comparison.
  * Admin suggestion list with filtering by status (new, applied, rejected).
  * Email notifications to admins when new suggestions arrive.

* **Demonstration Conflict Detection**:
  * New `/api/v1/check_demo_conflict` endpoint for detecting similar demonstrations on same date/city.
  * Real-time conflict checking in submission form with debouncing.
  * Conflict alert box with auto-scroll when matches found.
  * Links to view/edit/suggest changes for conflicting demonstrations.

* **Organization Search in Submission Form**:
  * New `/api/v1/search_organizations` API endpoint for searching existing organizations.
  * Real-time search dropdown in demo submission form for quick organizer lookup.
  * Auto-fill organizer details when selecting from search results.
  * Fallback to manual organizer entry if organization not found.

* **Test Mode for Demo Submission**:
  * `?mode=test` URL parameter autofills form with test data for admin/staff testing.
  * Test banner with clear visual indication of test mode.
  * Automatic data cleanup on successful test submission.

* **Demo Suggestions Admin Templates**:
  * New `admin/suggestions_list.html` for viewing all incoming suggestions with status badges.
  * New `admin/suggestion_view.html` for detailed suggestion review with field-by-field comparison.
  * Selectable fields for partial application of suggestions.

* **Cancellation Email Templates**:
  * `emails/demo_cancellation_link.html` - Email sent to organizers with cancellation link.
  * `emails/demo_cancelled_notification.html` - Notification to attendees about cancellation.

* **Admin Sidebar Navigation**:
  * Dark/Light mode toggle button in admin sidebar with localStorage persistence.
  * Suggestions menu link for admin suggestion review.

* `/robots.txt` route to control web crawler access.

* **Organizer Branding & Privacy Controls**:
  * Admin organization forms now upload or link `logo` assets and expose them via the public API/templates.
  * Demonstration detail cards render organizer logos, badges, and privacy-respecting labels/message for individuals.
  * Submission and admin demo forms gain explicit “yksityishenkilö” toggles plus name/email visibility checkboxes, preventing unconsented sharing in both self-service and staff workflows.
* `/ohjeet` user guide that explains image sizes, preview usage on mobile/desktop, and organisaation luontiaskelmat.
* **Background job control center**:
  * APScheduler integration refactored into a dedicated manager that logs every run (status, duration, tracebacks) to MongoDB.
  * New `/admin/background-jobs` dashboard lists all recurring tasks, shows next/last runs, and lets global admins trigger jobs manually or toggle them on/off.
  * Interval editor allows adjusting run cadence from the UI and saving overrides per job.
  * Dedicated `VIEW_BACKGROUND_JOBS` and `MANAGE_BACKGROUND_JOBS` permissions restrict who can inspect vs. manipulate schedules.
  * Per-job log view exposes detailed metadata, JSON payloads, and stack traces directly in the admin UI.
  * Background jobs now capture every demo mutation in the audit log + edit history (with per-run references), enabling the new UI to list exact demonstrations/fields touched.

* **Submission Reliability Enhancements**:
  * Structured submission error logging stored in `demo_submission_errors` with request/form metadata.
  * Admin dashboard at `/admin/demo/submission_errors` lists the latest errors with date/status filters, keyword search, and top error-code stats.
* **Notification Pipeline**:
  * New background job (`process_submission_notifications`) dequeues submitter/admin emails, enforces 24h admin reminders, and updates `admin_notification_last_sent_at`.
* **End-User Upgrades**:
  * Demo detail pages now expose “Add to calendar (.ics)” downloads plus show “Similar demonstrations” suggestions.
  * Logged-in visitors can follow organizers and recurring demo series directly from detail cards, organization pages, and the sibling (recurring) overview.
  * User profiles gained “Seuraamani organisaatiot” and “Seuraamani toistuvat mielenosoitukset” sections summarizing all follows with quick links.

### Changed
* Moved all migrations to a dedicated `utils/migrations/` folder.
* Improved analytics rollup function to support single execution via `run_once` parameter.
* Now running analytics rollups via an external systemd service for better reliability.
* Introduced a new `Case` class for managing admin support cases with action logs and running numbers.
* New admin template for displaying all cases with improved UI/UX.
* Added `merge_fields` method in `Demonstration` class for future enhancements.
* Updated `Demonstration` class with cancellation-related fields (reason, request status, timestamps, etc).
* Enhanced DEMO_FILTER in database.py to exclude cancelled demonstrations from listings.
* Refactored form submission to support AJAX requests with JSON responses.
* Improved error handling for demonstration insertion with proper case creation.
* Rate limiting storage URI simplified in Flask-Limiter configuration.
* Report modal enhanced with cancellation checkbox and reporter email field.
* Demonstration detail pages now show "Cancelled" status with disabled participation/reminder buttons.
* Suggestion templates (`suggestions_list.html`, `suggestion_view.html`) updated with dark/light mode support using CSS custom properties.
* Demo cards now display "Peruttu" (Cancelled) badge for cancelled events.
* Preview image template redesigned to improve contrast and theme-neutral appearance for automatically generated promo cards.

* Admin merge workflow expanded to guided/manual modes with submitter awareness, case log updates, and recommendation handling.
* Demo submission form enforces stricter required-field validation, idempotent fingerprints, and consistent AJAX error messaging (with error codes surfaced to users).
* Recurring follow APIs now normalize the canonical parent id via `recu_demos`, ensuring child occurrences map to the same follow record in every view.
* Organization detail, siblings listing, and profile follow sections now reflect the actual follow state for authenticated viewers and gracefully degrade when logged out.

### Fixed
* Docker builds now override broken container DNS with public IPv4 resolvers and force `apt-get` to use IPv4, preventing the Debian package step from hanging during image builds.
* Skip link in base template now properly anchors to `#main-content`.
* Checkbox value handling in form submission improved for reliable AJAX detection.
* Organizer invitation links endpoint fixed for Azure DevOps support.
* Conflict detection query now properly filters out cancelled and hidden demonstrations.
* Demonstration detail route now gracefully handles merged/alias IDs, preventing 500 errors and returning 404 when appropriate.
* Admin merge flow updates Mastobot metadata so merged demonstrations are not reposted.
* Admin command center now normalizes editor identifiers (string/OID/dict) and lists organization editors with member details, fixing missing or incomplete muokkausoikeus data.

## v4.0.0-beta.1 – *Robots Control Edition* 🌟

### Added

* `/robots.txt` route implemented to control web crawlers.
* Disallows access to sensitive paths:
  `/admin/`, `/users/auth/login/`, `/users/auth/register/`, `/users/auth/forgot/`.

### Purpose

* Prevents automated bots from indexing or interacting with admin and authentication routes.
* Ensures normal users can access the site without restrictions.

### Notes

* Returns proper `text/plain` content for compatibility with all crawlers.


## v4.0.0-beta – *Campaign & Admin Revolution Edition* 🌟

### Security & Access
- Adds safe redirect and temporary superuser access for Emilia to prevent system hijacking.
- Plans v4.1.0: Introduce proper access levels; Emilia will be assigned highest access via the system.

### Features
- Admin UI major update for improved usability and layout.
- API support for cancelling and force-accepting organization invitations.
- Demonstration enhancements: recommendations, badges, edit history, and diff views.
- Campaign volunteer signup API with email confirmation and expiry.
- Caching added to improve performance.

### Fixes
- Resolves DOM re-interpretation and duplicate data issues.
- Fixes login redirect flow and forced password reset.
- Redis issues resolved.
- Minor UI and form fixes.

### Dependency Updates
- `pymongo` upgraded 4.6.1 → 4.6.3
- `apscheduler` upgraded 3.10.4 → 3.11.0


## v3.1.0 – *The Reminder Revolution Edition* 🌟

### New Features

* **Email Reminder System**: Implemented a robust system for demonstration reminders, including `.ics` calendar attachments compatible with Gmail and Google Calendar.
* **Popup/Modal UI for Reminders**: Introduced a fully accessible and responsive modal interface for subscribing to reminders, supporting both light and dark modes.

### Fixes

* **Critical Crash Resolutions**: Fixed crashes occurring during profile picture uploads; improved data synchronization reliability.
* **.ics Attachment and Encoding**: Resolved issues with `.ics` encoding to ensure full calendar compatibility.

### Updates

* **Performance Optimization**: Migrated legacy features and optimized module interactions.
* **Deprecation Guidelines**: Revised to align with updated project standards.
* **Email Sending Refactor**: Improved email sending infrastructure with robust `.ics` attachment handling and error management.

---

## v3.0.0 – *Evolution Edition* 🚀

### New Features

* **Redesigned UI**: Introduced a responsive layout with refined grid system and updated color themes.
* **Enhanced Field Naming**: Standardized all field names using underscore formatting.

### Fixes

* **Critical Crash Resolutions**: Addressed issues causing application crashes during profile picture uploads.

### Updates

* **Performance Optimization**: Optimized legacy modules and internal interactions.
* **Deprecation Guidelines**: Updated to reflect current project standards.

---

## v2.9.2 – *Bug Squashing Edition* 🌟

### Fixes

* **Critical Bug Fix**: Resolved a crash issue during profile picture uploads.
* **Minor Bug Fixes**: Various small bug fixes improving overall app stability.

---

## v2.8.6 – *Organization Enhancement Edition* 🌟

### New Features

* **API Endpoint for Organizations**: Added support for creating new organizations via API.

### Updates

* **Organization Insertion Logic**: Improved data integrity checks for organization creation.
* **Admin Interface**: Enhanced UI for organization management.

---

## v2.8.5 – *Organizer Fix Edition* 🌟

### Fixes

* **Organization ID Assignment**: Corrected handling of `None` values in `fix_organizers` function.

---

## v2.8.4 – *Modernization Edition* 🌟

### Updates

* **Flask Upgrade**: Updated to latest Flask version for improved security and performance.
* **Dependency Management**: Upgraded all dependencies to their latest versions.
* **Documentation Overhaul**: Removed outdated docs and added comprehensive guides.
* **Codebase Cleanup**: Refactored and removed deprecated methods to improve maintainability.

---

## v2.8.3 – *Structural Overhaul Edition* 🌟

### Updates

* **Project Structure**: Refactored codebase structure, removed unused files, and added new modules.
* **Email Templates**: Improved templates for higher user engagement.
* **JavaScript Enhancements**: Improved JS functionality for a smoother user experience.

---

## v2.8.2 – *Polished Performance Edition* 🌟

### Deprecations

* **Leaflet Attribution Control**: Deprecated method for hiding Leaflet attribution control.

### Updates

* **Logging**: Adjusted logging level for recurring demonstrations.
* **Type Checking**: Enhanced type validation in the Demonstration class.
* **Documentation**: Improved script documentation and copyright notices.

---

## v2.8.1 – *Sparkly Bug Fix Edition* 🌟

### Fixes

* **Critical Bug Fix**: Resolved profile picture upload crash issue.
* **Minor Bug Fixes**: Multiple minor bug fixes to improve stability.

### Updates

* **Dependency Upgrades**: Updated packages for better performance and security.

### Deprecations

* **Feature Removals**: Removed outdated or unused functionality.

---

## v2.8.0 – *Ultimate Glow-Up Edition* 🌟

### New Features

* Enhanced user profiles with custom avatars, themes, and animations.
* Advanced role management with personalized permissions.
* Smart notifications with emojis, sound effects, and customizable settings.
* AI-driven personalization for user experience.
* One-click settings synchronization across devices.
* Improved privacy and security measures.
* Guardian Mode for automated threat detection.

### Fixes

* Optimized data synchronization.
* Improved startup stability and crash resistance.

### Updates

* Dependency and performance optimization for faster and more efficient operations.

---

## v2.7.0 – *Navigator’s Dream Edition* 🌟

### New Features

* **Language Navigation 2.0**: Introduced advanced translation and localization support.

---

## v2.6.0 – *Foundation for Greatness Edition* 🌟

### New Features

* Advanced authentication, including face recognition.
* Fortress-level encryption for sensitive data.
* UI enhancements and cleaner design updates.
* Expanded language support and emoji integration.

### Fixes

* Optimized data syncing and improved crash resistance under high load.

### Updates

* Backend component upgrades for scalability and performance.
* Refined codebase for better efficiency.

---

## [Unreleased]

### Added

* Automatic email notifications to `tuki@mielenosoitukset.fi` when a new demonstration is submitted.
* Reminder subscription system for demonstrations via email (1 week prior, day before at 9:00, day of at 9:00 or at least 2 hours before).
* Reminder subscription popup/modal UI with light/dark mode support.
* Popups and modals now appear above the header (`z-index: 1000001` for backdrop, `1000002` for modal).
* Main CSS and button styles now use color variables and `light-dark()` for full theme support.

### Changed

* UI containers and popups improved for contrast, spacing, and clarity.
* Reminder subscribe button grouped with social/share buttons.

### Fixed

* Modals and popups never hidden behind the header.
* Removed unnecessary borders from stacked containers for cleaner UI.
* Demo cards now use one shared browser styling source across homepage, list, city, tag, organization, siblings, and Pride views, fixing page-to-page visual drift from conflicting card CSS.
* The Pride page now loads the correct shared `demo_list.css` asset path, so its shared card support styles apply consistently.
* Shared demonstration card titles are now centered consistently across the browser-rendered card views.
* The demonstration detail page’s report-error menu now uses a more polished card-based modal design with clearer actions and feedback while keeping the existing reporting flow unchanged.
* The detail-page error report form now correctly hides its loading spinner until submission, resets cleanly when the modal closes, and uses more deliberate modal button styling.
* The detail-page report flow now has explicit mobile modal layout rules so the form, actions, and status blocks stay usable on narrow screens.
* Preview environments now connect to their own MongoDB container by container name and start a dedicated mail container, so PR previews can resolve their services reliably and finish seeding instead of stalling on startup.
* Preview deploys now print explicit progress markers during setup, seeding, app startup, and Caddy reload so long-running previews remain observable in GitHub Actions.

---

✅ **Overall:** Improved security, performance, accessibility, and polished UI for a more professional and reliable experience.
