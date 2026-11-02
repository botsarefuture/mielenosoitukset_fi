#!/usr/bin/env bash
# Activate the reviewed Apache include that routes migrated GETs to the React
# host. This is the one irreversible-looking production step, so it is only run
# on an explicit request, validates the vhost, and restores the previous include
# if Apache, the services or the routed pages do not answer afterwards.
set -euo pipefail

expected_sha=${1:?full commit SHA required}
repo_dir=${PRODUCTION_REPO_DIR:-/var/www/mielenosoitukset_fi}
include=/etc/apache2/mielenosoitukset-react-ssr.conf
vhost=/etc/apache2/sites-enabled/mielenosoitukset-le-ssl.conf
reviewed="$repo_dir/deploy/apache/react-ssr-routing.conf"
backup_root=/root/apache-backups
probe_host=mielenosoitukset.fi
host_http=http://127.0.0.1:8090
# Keep this list in sync with the RewriteRules in react-ssr-routing.conf: a path
# is probed here only when the reviewed include is expected to route it.
routed_paths=(/ /cities /mielenosoitukset-tanaan)
# The app host serves its own hashed bundle links; Flask serves /static/**.
host_marker=/app-assets/

[[ $expected_sha =~ ^[0-9a-f]{40}$ ]] || {
  echo "release_routing.sh: expected a full 40-character commit SHA" >&2
  exit 2
}
[[ $(id -u) == 0 ]] || {
  echo "release_routing.sh: root required" >&2
  exit 2
}
log() { printf 'release_routing: %s\n' "$*"; }

[[ -f $reviewed ]] || { log "missing $reviewed"; exit 1; }
[[ -f $vhost ]] || { log "missing vhost $vhost"; exit 1; }
[[ -f $include ]] || {
  log "$include does not exist; install it once by hand before using this command"
  exit 1
}
log "activating routing for ${expected_sha}"

include_line=$(grep -n 'mielenosoitukset-react-ssr\.conf' "$vhost" | head -1 | cut -d: -f1 || true)
proxy_line=$(grep -n 'ProxyPass[[:space:]]*"/"' "$vhost" | head -1 | cut -d: -f1 || true)
if [[ -z $include_line ]]; then
  log "the TLS vhost does not include $include; add it before ProxyPass \"/\" first"
  exit 1
fi
if [[ -n $proxy_line && $include_line -ge $proxy_line ]]; then
  log "the include comes after the catch-all ProxyPass rule; fix the vhost order first"
  exit 1
fi

if cmp -s "$reviewed" "$include"; then
  log "routing include already matches ${expected_sha}"
  exit 0
fi

install -d -m 0700 "$backup_root"
backup="$backup_root/mielenosoitukset-react-ssr.conf.$(date -u +%Y%m%dT%H%M%SZ)"
cp -a "$include" "$backup"
log "saved the active include to ${backup}"

restore() {
  set +e
  cp -a "$backup" "$include"
  if apache2ctl configtest; then
    systemctl reload apache2 || log "warning: reloading Apache after the restore failed"
    log "restored the previous routing include"
  else
    log "warning: the restored include does not pass configtest; inspect Apache before continuing"
  fi
}
trap 'status=$?; if [[ $status -ne 0 ]]; then restore; fi; exit $status' EXIT

install -m 0644 "$reviewed" "$include"
apache2ctl configtest
systemctl reload apache2

# The vhost restricts the origin to Cloudflare peer addresses, so a loopback TLS
# request always answers 403. Verify the app host directly, then verify the
# public URL; a Cloudflare challenge is reported instead of rolling back a
# correct include, but a public page without the app host's markup is a real
# routing failure and does roll back.
probe_origin() {
  local path=$1 body
  body=$(mktemp /run/moso-routing-probe.XXXXXX)
  if ! curl --fail --silent --show-error --max-time 10 \
      --output "$body" "${host_http}${path}"; then
    rm -f -- "$body"
    log "the app host did not answer ${path}"
    return 1
  fi
  if ! grep -q -- "$host_marker" "$body"; then
    rm -f -- "$body"
    log "the app host answered ${path} without its own assets"
    return 1
  fi
  rm -f -- "$body"
  return 0
}

probe_public() {
  local path=$1 body status
  body=$(mktemp /run/moso-routing-probe.XXXXXX)
  status=$(curl --silent --show-error --max-time 20 \
    --dump-header "${body}.headers" --output "$body" --write-out '%{http_code}' \
    "https://${probe_host}${path}" 2>/dev/null) || true
  [[ $status =~ ^[0-9]{3}$ ]] || status=000
  if [[ $status == 000 ]]; then
    rm -f -- "$body" "${body}.headers"
    log "warning: the public page ${path} was unreachable; routing is verified on the app host only"
    return 0
  fi
  if [[ $status == 403 ]] && grep -qi 'cf-mitigated: *challenge' "${body}.headers"; then
    rm -f -- "$body" "${body}.headers"
    log "warning: Cloudflare challenged the public probe for ${path}; routing is verified on the app host only"
    return 0
  fi
  if [[ $status != 200 ]] || ! grep -q -- "$host_marker" "$body"; then
    rm -f -- "$body" "${body}.headers"
    log "the public page ${path} answered ${status} without the app host markup"
    return 1
  fi
  rm -f -- "$body" "${body}.headers"
  return 0
}

for path in "${routed_paths[@]}"; do
  probe_origin "$path"
  probe_public "$path"
done

trap - EXIT
log "routing include is active; previous version saved at ${backup}"
