# Initial modernization assessment

Assessed on 27 October 2026. This is an initial source assessment, not a complete
runtime audit or an implementation approval. The maintainer's original context
is preserved in [modernization-context.txt](modernization-context.txt).
The initial assessment was documentation-only. The later header implementation
is documented in the update below; database and production configuration remain unchanged.

## Maintainer direction

Preserve functionality, accounts, MongoDB data and Flask administration. Migrate
gradually and base performance work on measurements. Evaluate React for the
public frontend and a separate API, with Go currently preferred for evaluation.
Language/framework selection, subdomains, deployment topology, session design,
repository reorganization and migration order remain proposals.

## Verified source findings

| Area | Evidence and implications |
| --- | --- |
| Flask application | `mielenosoitukset_fi/app.py:create_app` registers public API, account, admin, campaign and other blueprints. Public HTML routes and Jinja templates remain part of the same application. Extracting admin needs dependency mapping, not just DNS changes. |
| Public frontend in this checkout | Templates and static JavaScript serve the public site; this checkout has no frontend package manifest or React source. This observation does **not** cover all worktrees. See the React work below. |
| Existing API | `mielenosoitukset_fi/api/routes.py` already implements listing/detail and other operations under `/api/`. `api/api.yaml`, `tests/test_api_contract.py` and the surface inventory provide existing contracts to inspect before designing replacements. |
| MongoDB | `database_manager.py` uses PyMongo with a cached client, a 50-connection maximum pool and 5-connection minimum per client. `app.py` loads users from `mongo.users` by BSON ObjectId and can run migrations on startup. A new service must not silently assume migration or write ownership. |
| Passwords | `users/models.py` calls Werkzeug `generate_password_hash` for creation/password changes and `check_password_hash` for verification; stored field is `password_hash`. The context's bcrypt assertion is not supported by this code. Production hash formats and historical compatibility have not been inspected. |
| Authentication | Flask-Login is initialized in `app.py`; account blueprints include password/MFA and passkey flows. These need a compatibility inventory covering permissions, reset, revocation, disabled accounts and step-up authentication before any replacement. Sharing users does not share sessions. |
| Other workloads | `app.py` configures optional Socket.IO chat, background jobs and request-time analytics. These are responsibilities to account for when comparing capacity or splitting applications. |
| Deployment | `docs/production-deployment.md` and `deploy/production_deploy.sh` describe git-based deployment with systemd/Gunicorn graceful reload and build-SHA health verification. Apache/Cloudflare integration is documented under `deploy/apache/`. Actual running unit, worker counts, hardware and proxy configuration are unverified. |
| Development container | `Dockerfile` runs `python run.py`; `run.py` uses `app.run`. `compose.dev.yml` is explicitly a development stack. This does not establish that production runs Flask's development server. |
| Caching | `utils/cache.py` has configurable Flask-Caching/Redis integration and session-aware bypass rules. Redis is already present in development infrastructure, although a future architecture does not have to depend on it. |

### React work in another checkout

The referenced chat [Viimeistele pienkeräyskokonaisuus](thread://01a17871-2046-7f82-9665-7cc2acb6be9a?hostId=local)
was read, then its implementation was inspected at
`/Users/emiliavuorenmaa/.codex/worktrees/campaign-page-refresh/mielenosoitukset_fi`.
At inspection that worktree was clean on `codex/campaign-page-refresh`, commit
`f7d7c571`. Its documentation and source establish:

- A root `package.json`, TypeScript and Vite build entries under `frontend/`.
  There is an existing frontend foundation to extend, not recreate.
- React campaign and confirmation content, with `CampaignPage` composing
  `VolunteerForm`. The shared header/footer, fundraising page, authentication
  and administration remain Flask/Jinja. Header migration is deferred.
- Page-specific React islands mount with `createRoot` inside Flask HTML; there
  is no SPA router or request-time Node service. Escaped JSON props carry Flask
  URLs and translated behavior messages.
- `frontend/prerender.mjs` generates Jinja fallback partials from React at build
  time. Mounting replaces fallback content; this is not hydration. Information
  stays readable without JavaScript; fallback signup forms remain disabled.
- Vite writes tracked hashed assets and a manifest under
  `mielenosoitukset_fi/static/frontend/`, supporting the existing Python deployment
  without Node at runtime. Build/type checks and generated-file checks are documented.
- Signup validation, publication/access checks, database writes, confirmation
  tokens and queued mail stay in Flask. React does not acquire authorization.

The chat reports [PR #989](https://github.com/botsarefuture/mielenosoitukset_fi/pull/989),
83 focused tests passing and visual acceptance, with nothing merged or deployed
at that chat's completion. Those tests were not rerun here; current remote
merge/deployment status is unverified. Read that worktree's `docs/react-frontend.md`
and inspect the actual target branch before implementing further frontend work.
Do not copy or merge the branch solely on the basis of this assessment.

## Performance investigation: hypotheses, not measured bottlenecks

- The listing handler performs `count_documents`, then a projected, sorted,
  offset-paginated query. Search includes case-insensitive regular expressions.
  Use representative queries and index/explain evidence to determine whether
  counting, filtering or deep pagination is costly before changing contracts.
- Measure worker/thread utilization and database pool usage together. A language
  change cannot establish whether worker capacity, queries or upstream limits
  currently dominate latency. Include jobs and chat in resource accounting.
- Compare anonymous/authenticated and warm/cold requests. Localhost bypasses
  caching in the current helper, so naive local timing is not a production cache
  benchmark. Include static asset delivery and browser work separately.
- The current working tree already contains operational-metrics and latency-probe
  work (`scripts/measure_http_latency.py`). Inspect and reuse it before adding
  another monitoring path; no measurements from it were collected here.

## Architecture evaluation and repository recommendation

React + a separate API + Flask administration is a plausible gradual destination.
The existing islands provide a smaller next step: extend one real page at a time
inside Flask while keeping URLs, metadata, localization and account workflows.
Build-time fallbacks already address readable initial content for the campaign;
dynamic event pages need their own SEO/rendering assessment.

Go merits a small measured evaluation after a contract is selected, but adds a
language the maintainer is learning and another deployment boundary. Keeping
Flask and fixing measured deployment/query issues is the baseline alternative;
TypeScript/Fastify is another option if shared language improves maintenance.
No performance advantage has been measured in this assessment.

Keep this monorepo and the current Flask layout for now. Reuse `frontend/` from
the existing React work once its integration is settled. Add a backend directory
only for an approved prototype; do not move everything into speculative
`apps/web`, `apps/api` and `apps/legacy` directories. Preserve current deployment
and test paths until there is a concrete benefit and an approved move.

## Compatibility and unresolved risks

- Inventory MongoDB collections, indexes, validators, BSON types, date/time
  representations and relationships from actual migrations/models and an
  approved representative dataset. The few inspected call sites are not a
  complete schema. Keep Flask as write owner until a feature explicitly moves.
- Verify real password-format distributions without exposing hashes; use
  synthetic cross-language fixtures for every supported format. Do not assume
  a bcrypt verifier will support Werkzeug-generated records.
- Map cookies, CSRF, CORS, passkey origins/RP settings, sessions and admin
  redirects before subdomain separation. Retain current authentication initially.
- Confirm live hardware, process/proxy configuration, traffic, latency/error
  baseline, backups and rollback procedure. Numerical performance targets,
  migration schedule and a production topology are still open.
- This checkout contains unrelated uncommitted work. It was preserved. Findings
  describe inspected source, including that work, rather than a release audit.

## Recommended sequence and first milestone

1. Confirm integration status of the existing React PRs and finish the current
   route/consumer, authentication, database and deployment inventory.
2. Establish a reproducible baseline on staging for actual public journeys:
   listing/filtering, event detail and campaign signup. Record workload, cache
   state, sample count, latency percentiles, throughput, errors, CPU/RAM and query
   evidence. Agree targets from traffic and available resources.
3. Propose one bounded feature contract using real consumers. Describe purpose,
   request/response, authentication/authorization, database reads/writes,
   performance expectations and replaced behavior. The existing public listing
   is a candidate for investigation, not a selected migration requirement.
4. Review Flask improvements versus a Go or TypeScript prototype against that
   contract. Obtain approval before significant API implementation; test with
   isolated representative data and retain an immediate Flask rollback path.
5. Integrate one approved slice, verify compatibility, then expand. Evaluate
   admin separation and authentication changes separately when justified.

**First implementation milestone proposed for review:** integrate/extend the
existing React foundation on the agreed target branch and produce the staging
baseline plus one migration contract. Acceptance is documented build/behavior
compatibility, reproducible measurements and a reviewed contract—not a full
rewrite or new production routing. This documentation update does not approve
that implementation, merge a PR or modify production.


## Updated owner direction and integration status — 27 October 2026

PR #989 is now contained in fetched `origin/main` at `c435275d` (merge verified
from Git history). Production deployment has not been verified here. The React
foundation is therefore available directly on main; a parallel setup is unnecessary.

The maintainer selected this order: shared header/navigation first, then public
demonstration listings, then event details and recurring-series pages such as
`/demonstration/<parent_id>/children?occurrence=<slug>`. Use reusable React
components rather than implementing each page independently. This supersedes
the initial milestone/order recommendation above. Backend replacement, new
subdomains, authentication replacement and database schema changes are not
part of that instruction.

The first implementation slice moves the shared header into typed React
components while preserving the current product styling and Flask permissions,
URLs and translations. Listing and detail bodies remain in their existing
implementation until their own slices. Render strategy, metadata, canonical
series URLs and direct occurrence selection need explicit compatibility checks
before those bodies move.
