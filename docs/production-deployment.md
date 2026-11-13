# Production deployment

Every push to `main` creates a deployment candidate, not a promise that every
revision becomes live. The workflow keeps one active run and one replaceable
pending run (`queue: single`, `cancel-in-progress: false`). Quiet-period releases
start immediately; bursts coalesce pending candidates without canceling a release
that has begun. Several PRs in one merge-group update require one deployment of
the resulting revision, not separate deployments for each PR.

The workflow has two jobs:

| Job | Behavior |
| --- | --- |
| `release` | Require current `main` and a successful trusted full `python-tests` job for the exact SHA. Reuse a complete verified `release-<sha>`, or build, verify and publish React/Go artifacts once. Recheck admission after artifact preparation. Superseded candidates skip production activation explicitly. |
| `deploy` | Run one restricted SSH transaction: Flask → Go API → React host → optional routing, under the existing host lock. Main pushes activate routing; manual dispatch defaults to activation. Verify origin health and exact SHA before returning, then retain the independent public HTTPS checks. |

Full required tests remain on `pull_request` and `merge_group`. The duplicate
post-push suite is removed: admission reuses successful evidence for the same
SHA from the trusted Tests workflow and its successful `python-tests` job. A
legacy successful main-push run can supply evidence for a manual retry; PR-only,
wrong-repository, failed, skipped and wrong-SHA evidence cannot admit a release.
No successful evidence means failure, never an unverified deployment.

`release.json` names the commit and the source tree and records the size and
SHA-256 of both artifacts. The server downloads the assets for the requested
commit with `deploy/release_artifacts.py`, which refuses anything missing,
renamed, oversized or not matching its recorded digest. The artifacts therefore
come from the same GitHub repository the server already fetches from, and each
one is tied to the commit by construction instead of by an operator's local
`git rev-parse` check.

The server script serializes deployments, refuses stale SHAs before admission,
checks ancestry against its successful-deployment receipt, fast-forwards the
production checkout, verifies dependency deltas against an installation receipt,
provisions the public pagination index before worker startup,
atomically records the deployed commit in `.deploy-build-sha`, and asks
systemd/Gunicorn for a graceful reload. Existing workers keep serving while
replacements start. Each worker captures that commit when its Flask app starts,
and `/health` publishes it as `build_sha` with `Cache-Control: no-store`. Both
the server and GitHub Actions wait for a healthy worker whose `build_sha`
exactly matches the requested commit; a response from an old worker cannot
finish the deployment.

The server probes Gunicorn directly through its Unix socket, not through
Cloudflare. The default socket is `${PRODUCTION_REPO_DIR}/mielenosoitus.sock`
(repository default `/var/www/mielenosoitukset_fi`); override it with
`PRODUCTION_HEALTH_SOCKET` if Gunicorn uses a different path. The default
`PRODUCTION_HEALTH_URL` is `http://mielenosoitukset.fi/health`: its hostname is
sent as the HTTP Host header, but the connection stays on the local socket.
Existing HTTPS URL overrides are also accepted: only their Host/path/query are
used, and transport still stays on the local plain-HTTP Unix socket. This does
not downgrade the independent public HTTPS check or disable its TLS verification.
No TCP listener, TLS bypass, authentication bypass or firewall exception is added.

GitHub Actions retains the independent public HTTPS/build-SHA check. Only after
the trusted SSH deployment command succeeds does the origin step publish its
verified SHA as a step output. The public verifier receives that receipt through
`--origin-verified-sha`; it must exactly match the requested build and cannot be
used for socket, plain-HTTP or credentialed URL probes.

With that receipt, an initial HTTP 403 response bearing `cf-mitigated: challenge`
produces a GitHub warning rather than failing a verified origin deployment.
The warning explicitly says that public reachability is **not verified**; it is
not evidence of a successful public health response. A challenge after an earlier
bad/stale response still fails. Normal 403/5xx, network/TLS errors, invalid health
metadata and a wrong SHA remain failures. Without the origin receipt, challenges
remain failures too. The default server/socket verification stays strict.

No Cloudflare exception, site-wide WAF change, TLS bypass, extra credential or
public authentication bypass is installed. Public/browser release acceptance
remains separate when the CDN prevents the automated probe.

Index provisioning runs as `python3 -m
mielenosoitukset_fi.scripts.provision_public_indexes` before the reload, not
during route imports or application migrations. A failure stops deployment
before reloading workers. Operators using a different deployment entrypoint
must run this idempotent command before starting replacement workers.

Configure the GitHub `production` environment with:

- variables `PRODUCTION_SSH_HOST` and `PRODUCTION_SSH_USER`
- secrets `PRODUCTION_SSH_PRIVATE_KEY` and `PRODUCTION_SSH_KNOWN_HOSTS`

The production SSH key should be dedicated to this workflow and constrained on
the server with `deploy/production_ssh_entrypoint.sh` as its forced command. Do
not reuse a personal administrative key. Install its **public** key with a full
`authorized_keys` entry like this (replace the public-key placeholder only):

```text
restrict,command="/var/www/mielenosoitukset_fi/deploy/production_ssh_entrypoint.sh" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA_REPLACE_WITH_GITHUB_ACTIONS_PUBLIC_KEY github-actions-production
```

On an older OpenSSH release without `restrict`, use the explicit equivalent:

```text
no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty,command="/var/www/mielenosoitukset_fi/deploy/production_ssh_entrypoint.sh" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA_REPLACE_WITH_GITHUB_ACTIONS_PUBLIC_KEY github-actions-production
```

The forced command accepts only `deploy <full 40-character SHA>` and
`deploy-routing <full 40-character SHA>`. It never takes a shell command, a port
forward or another executable, and the private key remains only in the GitHub
production environment secret.

`deploy/production_ssh_entrypoint.sh` also snapshots the deploy logic from the
requested commit (`git show <sha>:deploy/production_deploy.sh`) into
`/run/moso-deploy.*.sh` and runs that copy. A deployment can therefore neither
execute a half-updated script nor need a hand-copied `/root/update-moso.sh`:
the reviewed logic ships with the commit it deploys.

## One-time server bootstrap for the automated release

The pipeline needs the updated forced command once. Until it is installed, the
current `/usr/local/sbin/moso-github-deploy` still accepts `deploy <sha>`, so a
push would run the new `production_deploy.sh` (which downloads release assets)
but reject `deploy-routing`. Apply this as root on lc-main, from a reviewed
`main` checkout at `/var/www/mielenosoitukset_fi`:

```sh
install -m 0755 /var/www/mielenosoitukset_fi/deploy/production_ssh_entrypoint.sh \
  /usr/local/sbin/moso-github-deploy.tmp
mv -f /usr/local/sbin/moso-github-deploy.tmp /usr/local/sbin/moso-github-deploy
```

The `authorized_keys` entry keeps `command="/usr/local/sbin/moso-github-deploy"`,
so only that file changes. No new key, service, toolchain or secret is needed on
the server; the artifacts are public release assets of a public repository.

Verify after the next push: the `deploy` job must end with both health checks
reporting the pushed SHA (`https://mielenosoitukset.fi/health` and
`https://api.mielenosoitukset.fi/health`), and the step log must say whether the
active Apache include already matches the commit. Once deployment and both
health checks pass, main-push runs automatically activate the committed route
set. A failed deployment or health check prevents the routing job from running.
Manual dispatch keeps an optional `routing` switch (enabled by default) for
deliberate deployment-only recovery runs.

Rollback is unchanged and does not depend on the pipeline: restore the previous
Apache include first, then restore the prior release from the backup directory
each deploy script prints. Reverting the bootstrap is re-installing a previous
`production_ssh_entrypoint.sh` copy over `/usr/local/sbin/moso-github-deploy`.

## Python trust-store security update (2026-10-22)

The [Python security announcement](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576)
requires certifi >=2026.10.19 and upstream pip >=26.2.2. This repository pins
those versions and uses `deploy/bootstrap_python_trust.sh <python-executable>`
before dependency installation in CI and Docker. The pip wheel URL
includes the announcement's SHA256; a modified download fails verification even
when the previous pip trust store is affected. TLS verification remains enabled.
The bootstrap intentionally pins pip 26.2.2, including on a newer environment;
update this reviewed URL/hash together when advancing that pin.

For existing project virtual environments, run the bootstrap with their Python,
then install `certifi==2026.10.19`. Rebuild containers with `--pull --no-cache`
to refresh both the base image and OS `ca-certificates`; already-running images
do not change when a dependency file is updated. uv, sigstore and pixi are not
declared repository tools; independently managed installations need their own
updates if present (minimums 0.13.4, 4.5.1 and 0.82.1 respectively).

Production inspection on 2026-10-22 found `/usr/bin/python3`, distro-owned pip
24.0 using `/etc/ssl/certs/ca-certificates.crt`, and separately installed certifi
2026.2.25 under `/usr/local`. PEP668 rejected the initial direct pip upgrade
without changing packages. Subsequent verification against
[Canonical's notice](https://ubuntu.com/blog/emudhra-ca-compromise-fixes-available)
confirmed installed ca-certificates20260816ubuntu0.24.04.1 is already fixed;
the actual system/pip bundle excludes the affected roots. This distro-patched
pip is not equivalent to an upstream pip24 bundle and was not overwritten.

The separately installed certifi did contain the affected emSign root. After
checking the exact package location, lack of dpkg ownership, and patched pip CA,
its package and metadata were backed up under root-only `/var/backups`, then
only certifi was upgraded with `--no-deps --break-system-packages` to2026.10.19.
This was an explicit, bounded operational exception for a known pip-owned
`/usr/local` package, not a generic PEP668 bypass policy. Reinspection confirmed
the affected root absent, followed by graceful reload and active/status:ok at
the unchanged fcb6a295 build. This verifies this application/system trust-store
scope, not every host/container/virtual environment or possible TLS override.

## Dependency installation contract (#952)

`deploy/install_dependencies.py` replaces the checkout-diff skip gate. Deploy
invokes it on every attempt, before index provisioning, build marker and reload.
Its atomically replaced 0600 receipt defaults to
`/var/lib/mielenosoitukset-fi-deploy/dependencies.json` in a 0700 parent, outside
the application-owned checkout. Keep this state directory root-owned.
`PRODUCTION_DEPENDENCY_RECEIPT` can select an equally protected location.

- Existing distro/system Python is **read-only**: on first adoption, the previous
  `.deploy-build-sha` manifest establishes the serving dependency baseline, never
  the already-advanced checkout. Missing/invalid baseline fails closed. Changed
  pins are checked against actual installed metadata. Already-correct certifi
  can therefore be acknowledged without replacing distro pip or reinstalling
  unrelated boto3/Flask/pymongo drift. Unchanged legacy drift is printed and
  preserved, not claimed to satisfy repository pins.
- Subsequent attempts compare the target manifest with the last acknowledged
  manifest. All previously managed pins are rechecked too, including when the
  manifest itself is unchanged. A failed install, validation or receipt write
  does not advance acknowledgement; the same SHA must retry that work.
- Needed package writes require an application-owned virtual environment. A
  fresh venv verifies/installs the full manifest; later updates install only the
  changed/missing managed pins. Hash-verified pip bootstrapping, pip install and
  pip check must succeed, followed by exact installed-version verification,
  before acknowledgement. Only plain exact package pins are supported; unknown
  requirement syntax fails before pip rather than being guessed.
- `PRODUCTION_PYTHON` selects the interpreter (default `python3`) consistently
  for dependency verification, index provisioning and health verification. When
  migrating, configure Gunicorn to use that **same application environment**
  before claiming runtime acceptance; selecting a deploy interpreter alone
  does not move the serving workers. A receipt from another runtime is rejected;
  provision a separate receipt path with the new environment.
- Removed requirements are not automatically uninstalled; neither are unknown
  server packages. Resolve historical drift individually before a full venv
  migration. This contract is not a reproducible environment lockfile or a
  claim that all inherited package versions are approved/current.

Before first production adoption, inspect the exact helper/target manifest,
previous verified build marker, interpreter, and reported drift under the deploy
lock. Preserve the existing service and server overlays. Verify changed pins
and receipt, then normal graceful reload/exact-SHA health. Do not automatically
retry through PEP668 or turn a failed install into a successful deployment.
Operational rollback keeps the old environment and receipt available; select
its matching interpreter/receipt and verified application revision. Do not point
an old code revision at unverified newly installed dependencies. This helper is
implemented/tested on the branch; actual production receipt adoption and venv
migration remain unverified until performed and recorded separately.

## Production virtual environment (12 November 2026)

Flask no longer has to run on the read-only system Python. Production uses an
application-owned virtual environment at `/opt/mielenosoitukset-fi/venv`, created
by `deploy/create_production_venv.sh` (run once, as root). It is created with
`--system-site-packages`, so Gunicorn, eventlet and other system packages that
are not in `requirements.txt` keep working; the pinned packages are installed
inside the venv and take precedence over the system copies. Root owns the venv;
the `www-data` workers only read it.

Wiring:

- `mielenosoitukset_fi.service` starts Gunicorn as
  `/opt/mielenosoitukset-fi/venv/bin/python -m gunicorn ...`.
- `/etc/mielenosoitukset-fi/deploy.env` (root-owned, mode 0644 or stricter) sets
  `PRODUCTION_PYTHON=/opt/mielenosoitukset-fi/venv/bin/python` and a new
  `PRODUCTION_DEPENDENCY_RECEIPT` path, because a receipt from the system runtime
  is rejected by design.
- The first deploy after the switch installs and verifies the full manifest in
  the venv, then writes the new receipt.

Rollback: the previous unit and receipt are kept on the host in
`/root/venv-migration-20261112/`. Restore the unit file from there,
`systemctl daemon-reload`, restart the service, and remove
`/etc/mielenosoitukset-fi/deploy.env`. The system Python was never modified, so
this returns to the earlier state, except that the system copies of Pillow,
PyJWT and PyMongo are the older versions. Revert the pins in `requirements.txt`
only together with that rollback.

## Immutable artifacts and failed publication

`deploy/publish_release.py` checks the release tag, manifest commit/tree, asset
sizes and SHA-256 values before reuse. A missing release is built once and uploaded
as a draft without `--clobber`; only a complete verified draft is published.
Existing partial releases or interrupted drafts fail with a repair-needed error.
They are not overwritten, deleted or silently rebuilt. Preserve any published
release for audit and rollback. Undeployed revisions remain in Git history; the
separate changelog artifact still includes retained change notes.

Go and React SHA-named release directories reject different bytes for an existing
SHA. Matching API binaries are reused without overwriting the running inode.
A service is skipped only when successful health reports `status: ok` and its
exact full lowercase SHA. Publication success is distinct from deployment success.

## Admission, failures and rollback holds

`/var/lib/mielenosoitukset-fi-deploy/last-successful.json` records the last verified
origin activation, its predecessor, release tag and whether routing was activated.
It advances atomically only after successful service and requested routing checks.
Independent public checks can still fail afterward; the workflow then stays failed
and the origin receipt is not a claim of public reachability. The existing
`.deploy-build-sha` remains the worker label, not a successful full-release receipt.
Initial adoption uses that existing serving marker as the baseline; an invalid
receipt never silently falls back to the marker.

Before admission, a superseded candidate can be skipped. After admission, its SHA
is pinned: a newer `main` update waits while all components and routing finish.
An older or unrelated target cannot replace the successful revision. A duplicate
healthy successful revision rechecks migration/service readiness and requested
routing without repeating reloads. A failed or partial release retains the previous
success receipt and fails visibly; retries verify the actual component state.

For emergency recovery, take the existing deploy lock before creating the
root-owned `/var/lib/mielenosoitukset-fi-deploy/hold` file. New admissions refuse
while it exists; an already running transaction is allowed to finish. Keep the
hold until the chosen compatible recovery and exact-SHA verification finish.
Release the hold deliberately, then re-run the current verified main candidate.
Do not cancel an unsafe active deployment or let a queued deployment undo a
manual recovery. Normal rollback is a tested forward-revert PR. Restoring old
Go/React pointers alone is not a full Flask/dependency/database rollback.

## Explicit migration readiness

Normal deployment runs `deploy/run_migrations.py --check --baseline <previous-sha>`
under the host lock before index provisioning and reload. It writes no database
data. The history check reads registries between the serving baseline and target;
an unapplied ID introduced and subsequently removed blocks deployment and requires
an approved bridge/manual procedure. Keep migrations cumulative and do not change
an applied migration to implement a new transition: add a new ID instead.

The root-owned, worker-readable `/etc/mielenosoitukset-fi/migrations-managed`
marker switches Flask workers to read-only migration readiness checks. Pending
migrations stop replacement workers rather than running in parallel on startup.
The deploy creates this marker before exposing target source or dependencies, so worker respawns
cannot independently execute a pending migration after a failed deployment.
`PRODUCTION_MIGRATIONS_MANAGED_FILE` overrides its path consistently for isolated
verification; production uses the default. Do not remove the marker to bypass a
failed check. Local/legacy installations without the marker retain startup
behavior, and test configuration can still disable automatic migrations.

When a migration is required, obtain explicit approval and a verified backup or
recovery plan first. Hold deployment admission and the same host lock, inspect the
read-only plan, then use the application interpreter from the target checkout:

```sh
/opt/mielenosoitukset-fi/venv/bin/python deploy/run_migrations.py --check --baseline <previous-sha>
/opt/mielenosoitukset-fi/venv/bin/python deploy/run_migrations.py --apply --approve <migration-id> --baseline <previous-sha>
```

Repeat `--approve` for every pending registered ID. The complete set is checked
before any migration effect. The CLI does not create Flask or start scheduled jobs.
Successful IDs are acknowledged in order; a failed callback is not acknowledged.
Retries skip acknowledged IDs, but partially completed data/index work can remain:
review the migration's idempotence and recovery before retrying. Automatic rollback
never reverses TTL deletion, backfills or permission changes. Legacy unregistered
migrations and external configuration changes require their own approved procedure.

Backwards compatibility must cover the graceful Flask overlap and Flask → Go →
React deployment order. This pipeline does not make the three services or MongoDB
one atomic transaction. A migration needing a particular intermediate application
version must use an approved bridge instead of relying on every PR becoming live.
