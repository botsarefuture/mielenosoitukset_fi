#!/usr/bin/env bash
# Nightly MongoDB backup for mielenosoitukset.fi (OPS-01).
#
# Writes one gzip archive per run, proves it can be read back with a
# mongorestore dry run, then keeps the newest $KEEP_DAYS days of archives.
# The database URI is read from the Flask config and handed to the Mongo tools
# through a private config file, so the password never appears in argv or ps.
#
# Environment (all optional):
#   APP_CONFIG    Flask config.yaml   (default /var/www/mielenosoitukset_fi/config.yaml)
#   BACKUP_DIR    where archives go   (default /var/backups/mielenosoitukset)
#   KEEP_DAYS     days to keep        (default 14)
#   MONGODUMP     mongodump binary    (default mongodump)
#   MONGORESTORE  mongorestore binary (default mongorestore)
#   PYTHON        interpreter used to read the YAML config (default python3)
set -euo pipefail
umask 077

app_config="${APP_CONFIG:-/var/www/mielenosoitukset_fi/config.yaml}"
backup_dir="${BACKUP_DIR:-/var/backups/mielenosoitukset}"
keep_days="${KEEP_DAYS:-14}"
mongodump="${MONGODUMP:-mongodump}"
mongorestore="${MONGORESTORE:-mongorestore}"
python="${PYTHON:-python3}"

[[ "$keep_days" =~ ^[0-9]+$ && "$keep_days" -ge 1 ]] || { echo "mongodb-backup: KEEP_DAYS must be a positive integer" >&2; exit 2; }
[[ -r "$app_config" ]] || { echo "mongodb-backup: cannot read $app_config" >&2; exit 2; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# Read MONGO_URI and MONGO_DBNAME without echoing them.
"$python" - "$app_config" "$work/tools.yaml" "$work/dbname" <<'PY'
import sys, yaml
config = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
uri, db = config.get("MONGO_URI"), config.get("MONGO_DBNAME")
if not uri or not db:
    sys.exit("mongodb-backup: MONGO_URI and MONGO_DBNAME are required in the app config")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    handle.write("uri: " + yaml.safe_dump(uri, default_style='"').strip() + "\n")
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    handle.write(db)
PY
dbname="$(cat "$work/dbname")"
[[ "$dbname" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "mongodb-backup: unexpected database name" >&2; exit 2; }

install -d -m 0700 "$backup_dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$backup_dir/${dbname}-${stamp}.archive.gz"
partial="$target.partial"

"$mongodump" --config="$work/tools.yaml" --db="$dbname" --archive="$partial" --gzip --quiet
[[ -s "$partial" ]] || { echo "mongodb-backup: dump is empty" >&2; rm -f "$partial"; exit 1; }
"$mongorestore" --config="$work/tools.yaml" --archive="$partial" --gzip --dryRun --quiet \
  --nsFrom="${dbname}.*" --nsTo="restorecheck_${dbname}.*"
mv "$partial" "$target"

# Retention: only ever delete our own finished archives, never the newest one.
find "$backup_dir" -maxdepth 1 -type f -name "${dbname}-*.archive.gz" -mtime "+$((keep_days - 1))" \
  ! -newer "$target" ! -samefile "$target" -print -delete
find "$backup_dir" -maxdepth 1 -type f -name "*.partial" -mmin +720 -print -delete

echo "mongodb-backup: wrote $target ($(du -h "$target" | cut -f1))"
