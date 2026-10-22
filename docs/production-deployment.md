# Production deployment

Every commit pushed to `main` triggers `.github/workflows/production-deploy.yml`.
The workflow connects with a dedicated SSH credential and invokes
`deploy/production_deploy.sh` on the server with the exact merged commit SHA.

The server script serializes deployments, refuses stale SHAs, fast-forwards the
production checkout, installs dependencies only when `requirements.txt`
changed, provisions the public pagination index before worker startup,
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
