# Public React host deployment

The maintainer approved the production rollout on 1 November 2026. This service
serves only the explicitly migrated public home GET/HEAD route. Flask retains
administration, authentication, APIs, other pages and all writes.

Release is automated: `.github/workflows/production-deploy.yml` builds this
bundle in CI, publishes it as a `release-<commit>` asset, and the server
installs it through `deploy/release_public.sh` after the Flask deploy. The host
is redeployed only when `http://127.0.0.1:8090/health` does not already report
the requested commit, so a re-run or a retry after a partial failure converges
without touching a healthy service. The manual procedure below is the
break-glass path for a host that CI cannot reach; it is not the normal release.

Manual build of a reviewed commit with the repository's Node 22.12+ toolchain:

```sh
npm ci
npm run app:build
node scripts/verify_public_host.mjs
tar -czf /tmp/app.tar.gz frontend/server.mjs frontend/dist
sha256sum /tmp/app.tar.gz
```

The runtime bundle needs no `node_modules`, database credentials or Node compiler
on the server. Install the Linux x64 Node 22 runtime from the official Node
distribution only after checking its archive against the official SHA256 file.
Record the exact version and checksum with the release. Install it root-owned
under `/opt/mielenosoitukset-public/node`, with `bin/node` executable. The service
runs as `www-data`, can read the root-owned release, and reaches the existing
Flask socket as its existing group. Confirm directory traversal/socket permissions
before activating routing; do not make the socket world-writable.

Upload `app.tar.gz`, `deploy.sh`, `environment` and
`mielenosoitukset-public.service` into one root-owned private directory. Run:

```sh
bash deploy.sh FULL_REVIEWED_COMMIT_SHA APP_TAR_GZ_SHA256
```

The deploy script verifies the archive hash and members, checks its manifest,
installs an immutable release, saves the old service/environment/release pointer,
atomically switches `current`, and requires exact-build loopback health. Failure
restores the prior service state. No Apache or database changes happen here.
The public environment file has no database credentials or application secret.

Before enabling the Apache include, verify `http://127.0.0.1:8090/health` reports
the intended `build_sha`, the home page loads Go data, and anonymous/signed-in
session reads work through `FLASK_SOCKET_PATH`. Check malformed asset URLs return
404 and the process stays healthy. Existing static files remain Apache-owned;
do not set local-verification `STATIC_DIR` in production.

Back up the active regular file `/etc/apache2/sites-enabled/mielenosoitukset-le-ssl.conf`, install the
reviewed `deploy/apache/react-ssr-routing.conf` in an Apache include file, and add
its `Include` **before** the catch-all `ProxyPass "/"` rule. Preserve Cloudflare
origin restrictions, existing proxy headers, TLS and other vhosts. Run
`apache2ctl configtest`, then gracefully reload Apache. Confirm only `/` and
`/app-assets/` changed handler; `/api/session`, `/admin`, `/users`, `/submit`,
`/demonstrations`, event pages, feeds and POSTs still reach Flask. Verify the
public origin through normal TLS without an origin bypass.

## Rollback

First restore the saved Apache vhost (or remove only this include), run
`apache2ctl configtest` and reload Apache. This immediately sends the home page
back to the unchanged Flask route. The new session endpoint is additive.

To restore a prior Node release, use the deploy script's printed backup directory:

```sh
backup=/var/backups/mielenosoitukset-public/PRINTED_TIMESTAMP
previous=$(cat "$backup/previous-release")
ln -sfn "$previous" /opt/mielenosoitukset-public/current.next
mv -Tf /opt/mielenosoitukset-public/current.next /opt/mielenosoitukset-public/current
cp -a "$backup/environment" /etc/mielenosoitukset-public/environment
cp -a "$backup/mielenosoitukset-public.service" /etc/systemd/system/mielenosoitukset-public.service
systemctl daemon-reload
systemctl restart mielenosoitukset-public.service
```

On a first installation there is no previous Node release: restore Apache first,
then stop/disable `mielenosoitukset-public.service`. Keep the release/backup for
inspection. No database rollback or user-session reset is required.
