#!/usr/bin/env bash
# Run as root from a reviewed upload bundle. Apache activation is a separate step.
set -euo pipefail
release_sha=${1:?full reviewed commit SHA required}
artifact_sha=${2:?app.tar.gz SHA256 required}
[[ $release_sha =~ ^[0-9a-f]{40}$ && $artifact_sha =~ ^[0-9a-f]{64}$ ]] || exit 2
[[ $(id -u) == 0 ]] || { echo 'Root required' >&2; exit 2; }
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
app_root=/opt/mielenosoitukset-public
service=mielenosoitukset-public.service
config_dir=/etc/mielenosoitukset-public
unit_file=/etc/systemd/system/$service
exec 9>/run/lock/mielenosoitukset-public-deploy.lock
flock -n 9 || { echo 'Public app deploy already running' >&2; exit 1; }
printf '%s  %s\n' "$artifact_sha" "$script_dir/app.tar.gz" | sha256sum --check --status
[[ -x $app_root/node/bin/node ]] || { echo 'Verified Node runtime must be installed first' >&2; exit 1; }
[[ -S /var/www/mielenosoitukset_fi/mielenosoitus.sock ]] || { echo 'Flask socket is missing' >&2; exit 1; }
install -d -m 0755 "$app_root/releases"
backup_dir=/var/backups/mielenosoitukset-public/$(date -u +%Y%m%dT%H%M%SZ)
install -d -m 0700 "$backup_dir" "$config_dir"
previous=$(readlink -f "$app_root/current" || true)
if [[ -n $previous ]]; then printf '%s\n' "$previous" > "$backup_dir/previous-release"; fi
for path in "$config_dir/environment" "$unit_file"; do
    if [[ -f $path ]]; then cp -a -- "$path" "$backup_dir/$(basename "$path")"; fi
done
staging=$(mktemp -d "$app_root/releases/.upload.XXXXXX")
trap 'rm -rf -- "$staging"' EXIT

# Validate the complete trusted, checksummed archive before extracting anything.
# Only regular files/directories under frontend/ are accepted; no links or devices.
python3 - "$script_dir/app.tar.gz" "$staging" <<'PY'
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile

destination = Path(sys.argv[2])
with tarfile.open(sys.argv[1], "r:gz") as archive:
    members = archive.getmembers()
    if len(members) > 5000 or sum(member.size for member in members) > 100 * 1024 * 1024:
        raise SystemExit("Unexpected app archive size")
    for member in members:
        path = PurePosixPath(member.name)
        if (path.is_absolute() or ".." in path.parts or not path.parts
                or path.parts[0] != "frontend"
                or not (member.isfile() or member.isdir())):
            raise SystemExit("Unsafe app archive member")
    archive.extractall(destination, members=members)
required = ["frontend/server.mjs", "frontend/public-availability.mjs", "frontend/dist/server/render.js",
            "frontend/dist/client/.vite/manifest.json"]
if not all((destination / path).is_file() for path in required):
    raise SystemExit("Incomplete app release")
client = destination / "frontend/dist/client"
manifest = json.loads((client / ".vite/manifest.json").read_text())
if "src/app/client.tsx" not in manifest:
    raise SystemExit("Client manifest entry is missing")
for entry in manifest.values():
    for name in [entry["file"], *entry.get("css", []), *entry.get("assets", [])]:
        asset = (client / name).resolve()
        if not asset.is_relative_to(client.resolve()) or not asset.is_file():
            raise SystemExit("Client manifest references a missing/unsafe asset")
PY
release_dir=$app_root/releases/$release_sha
if [[ -e $release_dir ]]; then
    [[ -f $release_dir/artifact.sha256 && $(cat "$release_dir/artifact.sha256") == "$artifact_sha" ]] || {
        echo 'Existing release has a different artifact; refusing overwrite' >&2; exit 1;
    }
else
    printf '%s\n' "$artifact_sha" > "$staging/artifact.sha256"
    chown -R root:root "$staging"
    find "$staging" -type d -exec chmod 0755 {} +
    find "$staging" -type f -exec chmod 0644 {} +
    mv -- "$staging" "$release_dir"
fi

rollback_service() {
    set +e
    systemctl stop "$service"
    if [[ -n $previous && -f $previous/frontend/server.mjs ]]; then
        ln -sfn "$previous" "$app_root/current.next"
        mv -Tf "$app_root/current.next" "$app_root/current"
    else
        rm -f -- "$app_root/current"
    fi
    if [[ -f $backup_dir/environment ]]; then
        cp -a "$backup_dir/environment" "$config_dir/environment"
    else
        rm -f -- "$config_dir/environment"
    fi
    if [[ -f $backup_dir/$service ]]; then
        cp -a "$backup_dir/$service" "$unit_file"
    else
        rm -f -- "$unit_file"
    fi
    systemctl daemon-reload
    if [[ -n $previous && -f $backup_dir/$service ]]; then systemctl restart "$service"; fi
}
on_error() {
    failed_status=$?
    trap - ERR
    rollback_service
    echo "Public app deployment failed; rollback state: $backup_dir" >&2
    exit "$failed_status"
}
trap on_error ERR
install -o root -g root -m 0600 "$script_dir/environment" "$config_dir/environment"
printf 'APP_BUILD_SHA=%s\n' "$release_sha" >> "$config_dir/environment"
install -o root -g root -m 0644 "$script_dir/$service" "$unit_file"
ln -sfn "$release_dir" "$app_root/current.next"
mv -Tf "$app_root/current.next" "$app_root/current"
systemctl daemon-reload
systemctl restart "$service"
healthy=false
for attempt in {1..20}; do
    if curl --fail --silent --show-error --max-time 3 http://127.0.0.1:8090/health 2>/dev/null |
       python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get("status")=="ok" and d.get("build_sha")==sys.argv[1] else 1)' "$release_sha" 2>/dev/null; then
        healthy=true; break
    fi
    sleep 1
done
[[ $healthy == true ]] || { echo 'Public app exact-build health failed' >&2; false; }
# /health skips the public availability check and API reads, so it can pass
# while pages still answer 503 for a few seconds after the Go API restarts.
# Wait until the home page renders with the host's own assets.
warm=false
for attempt in {1..30}; do
    if curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8090/ 2>/dev/null | grep -q -- /app-assets/; then
        warm=true; break
    fi
    sleep 1
done
[[ $warm == true ]] || { echo 'Public app did not render the home page after restart' >&2; false; }
systemctl enable "$service"
trap - ERR
printf 'Public app healthy at %s; rollback state %s\n' "$release_sha" "$backup_dir"
echo 'Apache routing is unchanged. Activate it only after host/session checks.'
