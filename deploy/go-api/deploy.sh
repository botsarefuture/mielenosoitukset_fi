#!/usr/bin/env bash
# Run as root from an uploaded, reviewed release bundle. No git/pip/DB writes.
set -euo pipefail
release_sha=${1:?full reviewed commit SHA required}
binary_sha=${2:?binary SHA256 required}
[[ $release_sha =~ ^[0-9a-f]{40}$ && $binary_sha =~ ^[0-9a-f]{64}$ ]] || exit 2
[[ $(id -u) == 0 ]] || { echo 'Root required'; exit 2; }
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec 9>/run/lock/mielenosoitukset-api-deploy.lock
flock -n 9 || { echo 'API deploy already running'; exit 1; }
printf '%s  %s\n' "$binary_sha" "$script_dir/api" | sha256sum --check --status
release_dir=/opt/mielenosoitukset-api/releases/$release_sha
backup_dir=/var/backups/mielenosoitukset-api/$(date -u +%Y%m%dT%H%M%SZ)
install -d -m 0700 "$backup_dir" /etc/mielenosoitukset-api
install -d -m 0755 "$release_dir"
previous=$(readlink -f /opt/mielenosoitukset-api/current || true)
if [[ -n $previous && -x $previous/api ]]; then printf '%s\n' "$previous" > "$backup_dir/previous-release"; fi
for path in /etc/mielenosoitukset-api/environment /etc/systemd/system/mielenosoitukset-api.service; do
    if [[ -f $path ]]; then cp -a -- "$path" "$backup_dir/$(basename "$path")"; fi
done
rollback_service() {
    if [[ -n $previous && -x $previous/api ]]; then
        ln -sfn "$previous" /opt/mielenosoitukset-api/current.next
        mv -Tf /opt/mielenosoitukset-api/current.next /opt/mielenosoitukset-api/current
        [[ ! -f $backup_dir/environment ]] || cp -a "$backup_dir/environment" /etc/mielenosoitukset-api/environment
        [[ ! -f $backup_dir/mielenosoitukset-api.service ]] || cp -a "$backup_dir/mielenosoitukset-api.service" /etc/systemd/system/mielenosoitukset-api.service
        systemctl daemon-reload
        systemctl restart mielenosoitukset-api.service
    else
        systemctl stop mielenosoitukset-api.service || true
    fi
}
trap 'rollback_service || echo "Automatic API rollback failed; inspect service and saved backup" >&2' ERR
install -o root -g root -m 0755 "$script_dir/api" "$release_dir/api"
python3 "$script_dir/configure_environment.py" /var/www/mielenosoitukset_fi/config.yaml /etc/mielenosoitukset-api/environment
install -m 0644 "$script_dir/mielenosoitukset-api.service" /etc/systemd/system/mielenosoitukset-api.service
ln -sfn "$release_dir" /opt/mielenosoitukset-api/current.next
mv -Tf /opt/mielenosoitukset-api/current.next /opt/mielenosoitukset-api/current
systemctl daemon-reload

if ! systemctl restart mielenosoitukset-api.service; then false; fi
healthy=false
for attempt in {1..20}; do
    if curl --fail --silent --show-error --max-time 3 http://127.0.0.1:8091/health 2>/dev/null | python3 -c 'import json,sys; value=json.load(sys.stdin);sys.exit(0 if value.get("status")=="ok" and value.get("build_sha")==sys.argv[1] else 1)' "$release_sha" 2>/dev/null; then
        healthy=true; break
    fi
    sleep 1
done
if [[ $healthy != true ]]; then echo 'API failed exact-build health; rolling back'; false; fi
systemctl enable mielenosoitukset-api.service
printf 'API healthy at commit %s; rollback state %s\n' "$release_sha" "$backup_dir"
