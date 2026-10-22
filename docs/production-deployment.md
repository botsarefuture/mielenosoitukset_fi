# Production deployment

Every commit pushed to `main` triggers `.github/workflows/production-deploy.yml`.
The workflow connects with a dedicated SSH credential and invokes
`deploy/production_deploy.sh` on the server with the exact merged commit SHA.

The server script serializes deployments, refuses stale SHAs, fast-forwards the
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

The forced command accepts only `deploy <full 40-character SHA>` and then calls
`/root/update-moso.sh`. The installed update script should be kept byte-for-byte
in sync with `deploy/production_deploy.sh`; the private key remains only in the
GitHub production environment secret.

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
