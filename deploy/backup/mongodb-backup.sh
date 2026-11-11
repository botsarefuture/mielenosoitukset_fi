#!/usr/bin/env bash
# Nightly MongoDB backup for mielenosoitukset.fi (OPS-01).
#
# Writes one gzip archive per run, checks the whole compressed stream is intact
# (gzip CRC over every byte) and that mongorestore can parse it, then keeps the
# newest $KEEP_DAYS days of archives. A periodic restore drill (docs/backups.md)
# is still the real proof that a backup restores.
# The database URI is read from the Flask config and handed to the Mongo tools
# through a private config file, so the password never appears in argv or ps.
#
# Environment (all optional):
#   APP_CONFIG    Flask config.yaml   (default /var/www/mielenosoitukset_fi/config.yaml)
#   BACKUP_DIR    where archives go   (default /var/backups/mielenosoitukset)
#   BACKUP_MODE   core or full        (default core)
#                 core skips the bulky audit-log collections in EXCLUDE_COLLECTIONS;
#                 full dumps every collection. Archives are named <db>-<mode>-<time>.
#   EXCLUDE_COLLECTIONS  space-separated, core mode only
#                 (default "super_audit_logs admin_logs")
#   KEEP_DAYS     days to keep archives of this mode (default 14)
#   MONGODUMP     mongodump binary    (default mongodump)
#   MONGORESTORE  mongorestore binary (default mongorestore)
#   PYTHON        interpreter used to read the YAML config (default python3)
set -euo pipefail
umask 077

app_config="${APP_CONFIG:-/var/www/mielenosoitukset_fi/config.yaml}"
backup_dir="${BACKUP_DIR:-/var/backups/mielenosoitukset}"
keep_days="${KEEP_DAYS:-14}"
mode="${BACKUP_MODE:-core}"
exclude="${EXCLUDE_COLLECTIONS-super_audit_logs admin_logs}"
mongodump="${MONGODUMP:-mongodump}"
mongorestore="${MONGORESTORE:-mongorestore}"
python="${PYTHON:-python3}"

[[ "$keep_days" =~ ^[0-9]+$ && "$keep_days" -ge 1 ]] || { echo "mongodb-backup: KEEP_DAYS must be a positive integer" >&2; exit 2; }
[[ "$mode" == core || "$mode" == full ]] || { echo "mongodb-backup: BACKUP_MODE must be core or full" >&2; exit 2; }
excluded=()
if [[ "$mode" == core ]]; then
  for name in $exclude; do
    [[ "$name" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "mongodb-backup: invalid collection name in EXCLUDE_COLLECTIONS" >&2; exit 2; }
    excluded+=("--excludeCollection=$name")
  done
fi
[[ -r "$app_config" ]] || { echo "mongodb-backup: cannot read $app_config" >&2; exit 2; }

work="$(mktemp -d)"
partial=""
# On any exit remove the temp config, and the unfinished archive if this run
# did not complete.
trap 'rm -rf "$work"; [[ -n "$partial" && -e "$partial" ]] && rm -f "$partial"' EXIT

# Read MONGO_URI and MONGO_DBNAME without echoing them.
"$python" - "$app_config" "$work/tools.yaml" "$work/dbname" "$work/authdb" <<'PY'
import sys, yaml
from urllib.parse import parse_qs, urlsplit
config = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
uri, db = config.get("MONGO_URI"), config.get("MONGO_DBNAME")
if not uri or not db:
    sys.exit("mongodb-backup: MONGO_URI and MONGO_DBNAME are required in the app config")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    handle.write("uri: " + yaml.safe_dump(uri, default_style='"').strip() + "\n")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    handle.write(db)
# Authenticate where the app does. PyMongo uses authSource, else the database
# in the URI path, else "admin"; the Mongo tools would otherwise use --db.
parts = urlsplit(uri)
auth = (parse_qs(parts.query).get("authSource") or [parts.path.lstrip("/") or "admin"])[0]
with open(sys.argv[4], "w", encoding="utf-8") as handle:
    handle.write(auth)
PY
dbname="$(cat "$work/dbname")"
[[ "$dbname" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "mongodb-backup: unexpected database name" >&2; exit 2; }
authdb="$(cat "$work/authdb")"
[[ "$authdb" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "mongodb-backup: unexpected authentication database" >&2; exit 2; }

install -d -m 0700 "$backup_dir"
# Clear leftovers from runs that were killed before their own cleanup ran.
find "$backup_dir" -maxdepth 1 -type f -name "*.partial" -print -delete
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$backup_dir/${dbname}-${mode}-${stamp}.archive.gz"
partial="$target.partial"

# No --quiet: on failure mongodump's reason must reach the journal.
"$mongodump" --config="$work/tools.yaml" --authenticationDatabase="$authdb" --db="$dbname" ${excluded[@]+"${excluded[@]}"} --archive="$partial" --gzip
[[ -s "$partial" ]] || { echo "mongodb-backup: dump is empty" >&2; exit 1; }
# --dryRun alone stops before reading collection data, so first prove the whole
# gzip stream decompresses and its checksum matches.
gzip -t "$partial" || { echo "mongodb-backup: archive failed its gzip integrity check" >&2; exit 1; }
"$mongorestore" --config="$work/tools.yaml" --authenticationDatabase="$authdb" --archive="$partial" --gzip --dryRun --quiet \
  --nsFrom="${dbname}.*" --nsTo="restorecheck_${dbname}.*"
mv "$partial" "$target"
partial=""

# Retention: only ever delete our own finished archives, never the newest one.
find "$backup_dir" -maxdepth 1 -type f -name "${dbname}-${mode}-*.archive.gz" -mtime "+$((keep_days - 1))" \
  ! -newer "$target" ! -samefile "$target" -print -delete

echo "mongodb-backup: wrote $target ($(du -h "$target" | cut -f1))"
