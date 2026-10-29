# Independent public Go API deployment

Owner authorized api.mielenosoitukset.fi deployment and reuse of the existing
production MongoDB credentials on29October2026. The endpoint remains read-only;
the reused credential may have broader privileges. Do not describe it as a
restricted database principal. No account/authentication or schema migration.

The existing site uses Apache, Cloudflare, a Gunicorn Unix socket and MongoDB7.
The Go service binds only127.0.0.1:8091, under a systemd dynamic user, with a
root-owned release binary and environment file. Its credentials are copied on
the server from config.yaml, never fetched into tool output or Git. The existing
Flask service and routing are untouched. No Go compiler is needed on the server.

Build a reviewed clean release with Go1.27.3:

```
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go -C go-api build -trimpath -ldflags="-s -w -X main.buildSHA=$RELEASE_SHA" -o /tmp/go-api-release/api .
```

Upload deploy/go-api's files and the binary into one root-owned private bundle
on lc-main. Run deploy.sh FULL_COMMIT_SHA BINARY_SHA256 from it. The script
serializes deploys, verifies the artifact, saves prior service/environment/link,
installs an atomic release pointer and checks exact-build localhost health. On
failure it restores the previous service, or stops the first installation.
Keep the bundle's SHA and the local/remote Git-tree equivalence in the release
record if publication used the GitHub connector.

## First hostname activation

1. Install api-http.conf as a new Apache available/enabled site. Create
   /var/lib/mielenosoitukset-api-acme/.well-known/acme-challenge with public
   traversal/read permission. Configtest and gracefully reload Apache.
2. Place a random temporary probe in that challenge directory and confirm its
   exact body through the public HTTP hostname before requesting a certificate.
3. The host's distro Certbot works with
   `PYTHONPATH=/usr/lib/python3/dist-packages /usr/bin/certbot`; its existing
   systemd service already has this override. Use `certonly --webroot` with
   the ACME root above, cert-name api.mielenosoitukset.fi and that one domain.
   Reuse the existing ACME account. Never disable TLS validation or replace the
   serving site's certificate.
4. Extract the existing production site's Cloudflare peer-address Location
   restriction into /etc/mielenosoitukset-api/cloudflare-origin.conf. Keep the
   actual CONN_REMOTE_ADDR restriction so mod_remoteip cannot turn a forged
   visitor address into origin access. Do not introduce an origin bypass.
5. Install api-https.conf only after its certificate exists. Configtest and
   graceful reload. Add a cert renewal deploy hook that configtests and reloads
   Apache when this certificate renews. Existing Certbot timer handles renewal.
6. Verify public HTTPS health with exact release SHA, one approved event, generic
   404 for a nonpublic event and public CORS. Confirm existing site health and
   Flask service remain good. No bulk production benchmark is required.

## Rollback

Disable only the two new API vhosts, configtest and gracefully reload Apache;
stop/disable mielenosoitukset-api.service. This first release does not switch any
website consumer, so the original site stays in place. Preserve environment and
certificate files in root-only locations for diagnosis. Later releases can
atomically select the prior release and restore its matching environment/unit
from the deployment backup, then restart and verify exact-build health. Never
change the original site's vhost or database data for API rollback.

The detail-page integration and list endpoint are subsequent slices. This
service's deployment alone does not accelerate an existing HTML page.

## Verified first production activation,29October2026

- Published release9189a017607331b8dbecb32c2b7d41afedf2ef05, source tree
  9aa3492045c0305379084bd2bdf5d8454fd5c7c9 (identical to reviewed local34a9ddaf).
  Linux/amd64 binary SHA256
  05b7f72dc9186aeaf9b1a3414e138288460067bc35053dddfdaf3940cb07479d.
- Go service active/enabled; local and public HTTPS health return exact release.
  Real public event200, real nonpublic event404, allowlisted public payload and
  open CORS verified without database writes. Direct-origin TLS request403;
  public requests must pass the preserved Cloudflare peer restriction.
- Environment mode0600 root:root, settings copied only onserver. Existing Apache
  and Flask service remain active; original site health remainsok.
- Own Let's Encrypt certificate valid through27January2027. Actual HTTP-01
  issuance succeeded. Existing Certbot timer isactive and already uses the
  required distro Python path. Dedicated certificate deploy hook installed to
  configtest/gracefully reload Apache after renewal. Renewal dryrun not repeated.
- Target systemd unit verification passed with pre-existing unrelated warnings
  in shorturl.service and luova_auth.service. Apache configtest passed. A first
  configtest caught a missing API ACL include before any reload; the standalone
  copy_origin_restriction.py helper then installed it and configtest passed.
- Operational rollback state:
  /var/backups/mielenosoitukset-api/20261029T170121Z.
  Production files are installed independently of the Flask checkout. Merging
  this operational documentation does not itself redeploy the Go service.
