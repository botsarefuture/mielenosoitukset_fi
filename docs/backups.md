# MongoDB backups (OPS-01)

## Current state (checked 11 November 2026, read-only)

- The database runs on **lc-db** (`/var/lib/mongodb`, 4.1 GB including other
  databases). It has no MongoDB dump timer, cron entry or backup directory.
- **lc-main** (app host) has no database backup either. Its
  `luovasec-snapshot-mielenosoitukset` timer is a *static HTML snapshot* of
  public pages for a fallback site, not a data backup. It currently fails every
  night in its own link check (missing `/app-assets/*` files and links to
  `/submit` and `/users/auth/*`), and has no `OnFailure` alert. That tool is
  maintained outside this repository.
- Whether Proxmox takes scheduled VM backups of lc-db was **not checked**. If it
  does, those are crash-consistent disk images; a logical dump is still needed
  for clean, per-database restores.

So today there is no restorable backup of the mielenosoitukset database.

## What this repository provides

`deploy/backup/` holds a ready-to-install nightly backup that runs on **lc-main**
and dumps the database over the network from lc-db, using the same `MONGO_URI`
and `MONGO_DBNAME` as the app (`/var/www/mielenosoitukset_fi/config.yaml`).
The archives therefore live on a different machine from the database.

- `mongodb-backup.sh`:
  - writes `/var/backups/mielenosoitukset/<db>-<mode>-<UTC time>.archive.gz`.
    Mode `core` (nightly) skips `super_audit_logs` and `admin_logs`, which are
    about 13.6 GB uncompressed together (most of the database). Mode `full`
    (weekly) includes them. A full dump read for more than 20 minutes and
    loaded lc-db enough that a Go API restart during it failed its startup
    database check (11 November 2026), so full dumps run only once a week, at
    night;
  - checks every archive's full gzip stream (CRC over every byte) and that
    `mongorestore --dryRun` can parse it. The dry run alone does not read
    collection data, so the restore drill below remains the real proof;
  - removes unfinished `.partial` files from failed or killed runs;
  - keeps 14 days of core archives and 35 days of full archives. Each mode only
    prunes its own files.
  - The URI is passed through a mode-0600 temporary config file, never on the
    command line.
- `mielenosoitukset-mongodb-backup.service` / `.timer`: core dump nightly at
  02:30 UTC, with `Persistent=true` so a missed run catches up.
- `mielenosoitukset-mongodb-backup-full.service` / `.timer`: full dump on
  Sundays at 03:30 UTC.
- `mielenosoitukset-backup-failed.service`: on failure it logs an error-level
  line tagged `mielenosoitukset-backup`. Hook a real alert to it once a channel
  is chosen.

Expected size: the dump is gzip-compressed BSON, typically well under the
on-disk size. Check the first archive and adjust `KEEP_DAYS` if lc-main's disk
(about 45 GB free) gets tight.

## Install (production change: needs the maintainer's go-ahead)

On lc-main as root, after the branch is deployed:

```sh
install -d -m 0700 /var/backups/mielenosoitukset
cp /var/www/mielenosoitukset_fi/deploy/backup/mielenosoitukset-*.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl start mielenosoitukset-mongodb-backup.service   # first run now
journalctl -u mielenosoitukset-mongodb-backup -n 20 --no-pager
ls -lh /var/backups/mielenosoitukset
systemctl enable --now mielenosoitukset-mongodb-backup.timer mielenosoitukset-mongodb-backup-full.timer
```

Roll back with `systemctl disable --now mielenosoitukset-mongodb-backup.timer
mielenosoitukset-mongodb-backup-full.timer`. The archives stay where they are.

The script needs `mongodump` and `mongorestore` (database tools 100.x, already on
lc-main) and Python with PyYAML (already used by the app).

## Restore

To a scratch database first. Never restore straight over production.

```sh
mongorestore --config=<file with uri: "..."> --archive=/var/backups/mielenosoitukset/<file>.archive.gz --gzip \
  --nsFrom='mielenosoitukset.*' --nsTo='restore_check.*'
```

Compare document counts against production, then drop `restore_check`. A real
recovery restores into `mielenosoitukset` only after the maintainer decides to.

## Still to decide (maintainer)

1. **Off-site copy.** lc-main and lc-db may sit on the same physical host. Copy
   the archives somewhere off that hardware (for example rclone or restic to
   object storage) and decide on encryption keys and who holds them.
2. **Alert channel.** Replace the `logger` line in
   `mielenosoitukset-backup-failed.service` with Telegram, email or the
   monitoring the team uses.
3. **Recovery drill (OPS-02).** Restore one archive into a scratch database,
   time it, and record the RPO (24 h with nightly dumps) and RTO.
4. **The static snapshot job** on lc-main: fix or silence its nightly failure,
   which is outside this repository.
