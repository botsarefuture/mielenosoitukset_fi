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
Use plain HTTP for this socket transport; it is not an insecure public request.
No TCP listener, TLS bypass, authentication bypass or firewall exception is added.

GitHub Actions retains the independent public HTTPS/build-SHA check. A
Cloudflare challenge makes that check fail with an explicit `HTTP 403
(Cloudflare challenge)` diagnostic rather than being confused with a stale
worker. If bot protection blocks it, operators must configure a narrowly scoped
Cloudflare exception for the health probe (GET `/health` on the production
hostname, limited to the necessary challenge rule), not disable site-wide WAF
or bot protection. No exception is installed by this code change. The public
probe remains a release gate until it can return the expected SHA.

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
