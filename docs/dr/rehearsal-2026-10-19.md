# Pentest and disaster-recovery rehearsal, 19 October 2026

This is an isolated application recovery experiment, not production failover or
approval to change production backup schedules. The existing pentest host, DNS,
nginx, TLS certificate, SSH key, firewall and noindex policy were reused.

## Working environment

- App: `https://pentest.mielenosoitukset.fi/` (HTTP Basic authentication).
- Snapshot: `https://pentest.mielenosoitukset.fi/mirror/` (public, read-only).
- Mailpit: loopback port 8025, accessed through an SSH tunnel; no SMTP relay.
- MongoDB 7.0.37, Redis, an isolated real MinIO instance and app listen locally.
- MinIO is the verified production binary, `RELEASE.2025-07-23T15-54-02Z`, with
  identical SHA-256 `eef6581f6509f43ece007a6f2eb4c5e3ce41498c8956e919a7ac7b4b170fa431`.
  The sandbox uses fresh credentials and its own bucket/data, not production IAM.
- Original application release: `63c85eae99f51f6d805e141300a0c9186c202b4e`.
- Production uses distro-patched Gunicorn 20.1.0. The tested venv equivalent is
  pinned Gunicorn 23.0.0 / Eventlet 0.35.2. Unpinned Gunicorn 26 removed this worker;
  unpatched PyPI Gunicorn 20.1.0 cannot import this Eventlet's removed sentinel.
- nginx replaces production Apache in this copy. This is not OS/image parity.

Credentials, dumps, media, wheels, source bundles and raw test outputs stay in
private storage outside Git and web roots. Generated configuration uses mode
0600, owned by the service account. Release archives omit environment files.

The full copy contains restored private data and requires the separate access
password. A synthetic sandbox-only administrator exists; restored accounts,
permissions and audit history remain present. Never publish its access file.

## Results measured so far

| Test | Result | Scope |
| --- | --- | --- |
| Fresh logical MongoDB archive | About 173 MiB | Read-only export; not an atomic cross-collection snapshot |
| Initial DB import | 84 seconds; 3,138,403 restored documents, zero failures | Existing prepared host; indexes included |
| Offline app + DB rehearsal | 103.40 seconds; DB phase 81.08 seconds (repeat; first run 102.69 seconds) | Separate temporary DB, fresh venv from saved wheels, second app, matching SHA and three API events |
| HTTP checks | Home, health, event list/API, login, admin status and contact form work | Authenticated copy; anonymous app access returns 401 |
| Mail | Contact-form message captured in Mailpit | No external delivery; original two queue entries preserved in quarantine |
| Egress | Local SMTP allowed; production DB connection blocked | systemd `IPAddressDeny=any`, `IPAddressAllow=localhost` |
| Full media restore | 204 seconds; 52,465 objects / 3,282,875,798 bytes | Complete source coverage, zero unavailable objects, per-object hashes and destination ETags verified |
| Local S3 | Native MinIO write/read verified | Same binary as production; fresh local credentials and isolated data |
| Static fallback | Crawl and offline dependencies prepared; first 12 public events materialized | Bounded snapshot; forms/scripts disabled, missing source images use a placeholder |

The successful 103-second test **does not include** ordering a replacement host,
OS/runtime provisioning, certificate/DNS work, downloading the backup bundle,
the full media restore, or production traffic cutover. It is not full-service RTO.

## Why the VM-image path was too slow

The available scheduled backups are Proxmox VMA archives: roughly 45.2 GB for the
app guest and 17.0 GB for the DB guest, compressed. The app guest contains 180 GB
of virtual disks. The 40 GB pentest machine cannot hold these full images.

An attempt to restore into spare hypervisor storage stalled on LVM metadata and
disk-I/O waits. Running app disk allocation beside the DB extraction delayed the
DB path. Both test restores were stopped; this exercise does not establish that
the original VM images recovered successfully. Production guests and source
archives were not replaced. Sampled public production health requests passed.

Do not plan rapid application recovery around full VM extraction. Keep the VM
backups as another recovery layer, and measure that path separately on suitable,
verified staging storage. Do not tune production storage during a rehearsal.

## Tested repeatable command

On the prepared sandbox, point the interpreter at the checked-out recovery tools
and an already downloaded private bundle:

```sh
sudo /srv/mielenosoitukset-dr/venv/bin/python \
  scripts/dr/rehearse_bundle.py /private/path/to/recovery-bundle
```

The tool verifies `SHA256SUMS.json`, extracts `app.tar.gz` safely, refuses embedded
environment files, installs `requirements.lock` from `wheels/` with `--no-index`,
restores `mongo.archive.gz` into a generated `dr_verify_*` database, and starts an
isolated second worker on loopback port 5004. It checks health/build identity and
the event API, then stops that worker and drops only its generated test database.
It records `last-rehearsal.json` and a private log in the bundle directory.

This command needs the native MongoDB tools, service account, local dependencies
and existing systemd setup. It does not yet bootstrap a blank OS. It intentionally
does not replace the working app or process restored email queue items.

## Preparing recovery artifacts

1. Build a release from a known Git commit. Exclude `.env`, `.env.*`, private YAML,
   dumps, keys and host configuration. Record `build_sha` separately.
2. `backup_database.py` reads the source YAML locally and streams a gzip MongoDB
   archive. Its secret-bearing tool configuration uses a Linux anonymous memfd;
   credentials are not passed in command arguments or copied to the destination.
   It preserves the application's authentication database, including the default
   `admin` auth source when the URI has no database component.
3. Save the exact tested dependency lock and wheels. Pin the worker stack; a
   source checkout alone is not enough to reproduce a running environment.
4. `backup_media.py` makes read-only S3 list/get requests and streams a tar with
   per-object hashes and content-type metadata. Copy server-to-server rather than
   relaying large archives through an operator's laptop. Any temporary SSH key
   must have a forced write-only command, source-address restriction and expiry;
   remove it after the transfer.
5. Store all artifacts privately, verify transfer hashes and run a restoration.
   Hashes detect corruption; authenticity still depends on trusted backup storage.

These tools do not enable a production backup schedule, retention or alerting.
A new live dump is not proof that an existing historical backup can recover, and
concurrent production writes can produce cross-collection time differences.
Design consistent snapshots/PITR and recovery-point selection separately.

## Side effects and integration safety

`write_config.py` generates new session and test secrets without reading a
production environment. `install_services.sh` installs units with local-only
network access. `enable_capture_mail.py` preserves each restored queue document
and original status before permitting new mail into Mailpit. The SMTP adapter
also redirects explicit sender profiles, so they cannot select a real SMTP host.

Schedulers, panic polling, IMAP ingress and external integrations remain disabled.
The response adapter rewrites production app/CDN links to the sandbox; CSP blocks
browser connections to external services. The separate MinIO instance binds only
to loopback, uses fresh local credentials, and is reached through the app's
authenticated media proxy. Production IAM and external integrations are not copied.

## S3 failure-domain discovery

Live inspection confirmed that the site's S3 is MinIO on `lc-main`, not an
independent external provider. Its data directory is on that guest's root
filesystem. The VM backup includes that disk, but successful object recovery from
the VM image was not proven. The site's S3 and app therefore share that failure
domain; independent object backups remain important.

Bulk export through the public S3 hostname hit HTTP 403 on object reads and
pagination. The same credentials passed local S3 API reads and pagination. The
exporter accepts an explicit override only for the verified loopback source
endpoint, so it can avoid the web-proxy path for a normal authenticated backup
without changing production configuration or access rights. Never redirect those
credentials to an arbitrary endpoint. Denied/missing/changed objects are recorded
in the archive manifest, and the exporter exits nonzero for incomplete coverage.

The two VM/QEMU-agent helpers are experimental and were not validated by a
completed image restore. They reject production guest IDs and are not part of the
tested fast path. Do not boot a restored VM with its original network interface.

## Static outage rehearsal

`switch_mode.sh snapshot` changes only this sandbox's root URL to the saved HTML.
`switch_mode.sh app` restores the local app proxy after checking the app service.
`/mirror/` always remains static. nginx configuration is tested before reload and
the previous include is restored if validation fails. Never use this switch to
change production DNS, Cloudflare or the production service.

## Open continuity work

- Automate and measure blank-host provisioning separately from artifact restore.
- Approve, deploy and monitor scheduled logical DB/release/media artifacts.
- Define consistency, retention, encryption, RPO and independent-copy policy.
- Re-test full VM recovery on staging storage with proven I/O performance.
- Test actual mail-server recovery separately; Mailpit does not prove it.
- Keep the incident investigation and its evidence lifecycle separate.

Canonical continuity procedure and this rehearsal's sanitized evidence are in
[Palautusmenettely](https://docs.google.com/document/d/1D1FTEbfPN3f9FLb9py3vls0z_fGd_lXo12WhsZ8C49c/edit),
tab “Palautusharjoitus 19.10.2026”.

## Validation limits

The 13 focused DR tests pass. Python compilation and shell syntax checks pass.
The deployed application templates compiled successfully. The wider application
test run on the operator’s Python 3.14 reached 68% with five failures, then hung
and was stopped; the full suite is not green and those failures were not
attributed to a baseline. Production uses a different runtime.
