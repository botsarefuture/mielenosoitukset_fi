#!/usr/bin/env bash

set -euo pipefail

repo_dir="${PRODUCTION_REPO_DIR:-/var/www/mielenosoitukset_fi}"
service_name="${PRODUCTION_SERVICE_NAME:-mielenosoitukset_fi}"
health_url="${PRODUCTION_HEALTH_URL:-http://mielenosoitukset.fi/health}"
health_socket="${PRODUCTION_HEALTH_SOCKET:-${repo_dir}/mielenosoitus.sock}"
build_sha_file="${PRODUCTION_BUILD_SHA_FILE:-${repo_dir}/.deploy-build-sha}"
deploy_env="${PRODUCTION_DEPLOY_ENV:-/etc/mielenosoitukset-fi/deploy.env}"

# load_deploy_env FILE: optional root-owned settings for this host, such as the
# application virtual environment. The file is parsed, never sourced, and only
# PRODUCTION_PYTHON and PRODUCTION_DEPENDENCY_RECEIPT are accepted. Variables
# already set in the environment win. Prints the two values, one per line.
load_deploy_env() {
  local file=$1 python=${PRODUCTION_PYTHON:-} receipt=${PRODUCTION_DEPENDENCY_RECEIPT:-} key value line
  local file_python="" file_receipt=""
  if [[ -e $file ]]; then
    if [[ ! -f $file || -L $file || ! -O $file ]]; then
      echo "production_deploy.sh: $file must be a regular file owned by the deploying user" >&2
      return 2
    fi
    if [[ -n $(find "$file" -maxdepth 0 \( -perm -020 -o -perm -002 \)) ]]; then
      echo "production_deploy.sh: $file must not be group- or world-writable" >&2
      return 2
    fi
    while IFS= read -r line || [[ -n $line ]]; do
      [[ $line =~ ^[[:space:]]*(#|$) ]] && continue
      if [[ ! $line =~ ^([A-Z_]+)=(/[A-Za-z0-9._/-]+)$ ]]; then
        echo "production_deploy.sh: unsupported line in $file" >&2
        return 2
      fi
      key=${BASH_REMATCH[1]} value=${BASH_REMATCH[2]}
      case $key in
        PRODUCTION_PYTHON) file_python=$value ;;
        PRODUCTION_DEPENDENCY_RECEIPT) file_receipt=$value ;;
        *) echo "production_deploy.sh: unsupported setting $key in $file" >&2; return 2 ;;
      esac
    done < "$file"
    if [[ -n $file_python && ! -x $file_python ]]; then
      echo "production_deploy.sh: PRODUCTION_PYTHON in $file is not executable" >&2
      return 2
    fi
  fi
  printf '%s\n%s\n' "${python:-${file_python:-python3}}" \
    "${receipt:-${file_receipt:-/var/lib/mielenosoitukset-fi-deploy/dependencies.json}}"
}

routing=false
skip_public=false
expected_sha=""

for argument in "$@"; do
  case "$argument" in
    --routing) routing=true ;;
    --skip-public) skip_public=true ;;
    *)
      if [[ -n "$expected_sha" ]]; then
        echo "production_deploy.sh: unexpected argument: $argument" >&2
        exit 2
      fi
      expected_sha="$argument"
      ;;
  esac
done

if [[ ! "$expected_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "production_deploy.sh: expected a full 40-character commit SHA" >&2
  exit 2
fi

exec 9>"${PRODUCTION_LOCK_FILE:-/run/lock/mielenosoitukset-fi-deploy.lock}"
flock -w 300 9 || {
  echo "production_deploy.sh: another deployment still holds the lock" >&2
  exit 1
}

# Read host settings only while holding the lock, so a deploy queued behind a
# migration that changes deploy.env uses the settings the migration left.
{ read -r production_python && read -r dependency_receipt; } < <(load_deploy_env "$deploy_env") || exit 2
[[ -n ${production_python:-} && -n ${dependency_receipt:-} ]] || exit 2

cd "$repo_dir"
git config --global --add safe.directory "$repo_dir" >/dev/null 2>&1 || true

stash_ref=""

restore_local_changes() {
  if [[ -n "$stash_ref" ]] && git rev-parse --verify "$stash_ref" >/dev/null 2>&1; then
    if ! git stash pop "$stash_ref"; then
      echo "production_deploy.sh: deployed successfully, but server-local tracked changes need manual conflict resolution" >&2
      return 1
    fi
  fi
}
trap restore_local_changes EXIT

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  git stash push -m "automatic production deploy before ${expected_sha}"
  stash_ref="stash@{0}"
fi

git fetch --prune origin main
main_sha="$(git rev-parse origin/main)"
if [[ "$main_sha" != "$expected_sha" ]]; then
  echo "production_deploy.sh: requested ${expected_sha}, but origin/main is ${main_sha}; refusing a stale deployment" >&2
  exit 1
fi

git switch main
git merge --ff-only "$expected_sha"

"$production_python" "$repo_dir/deploy/install_dependencies.py" \
  --repo "$repo_dir" --receipt "$dependency_receipt" --baseline-sha-file "$build_sha_file"

if ! restore_local_changes; then
  trap - EXIT
  exit 1
fi
trap - EXIT

chown -R www-data:www-data "$repo_dir"

# Index builds are synchronous even with background=True. Finish the
# idempotent provisioning step while old workers still serve traffic.
"$production_python" -m mielenosoitukset_fi.scripts.provision_public_indexes

# New workers capture this value while creating their Flask application. Write
# it atomically so an existing worker can never observe a partial SHA. Existing
# workers retain the value they captured at their own startup.
build_sha_tmp="${build_sha_file}.tmp.$$"
printf '%s\n' "$expected_sha" >"$build_sha_tmp"
chmod 0644 "$build_sha_tmp"
mv -f "$build_sha_tmp" "$build_sha_file"

# Gunicorn's HUP reload starts replacement workers before retiring the old
# workers, avoiding the hard outage caused by systemctl restart.
systemctl reload "$service_name"

if ! systemctl is-active --quiet "$service_name" || \
   ! "$production_python" "$repo_dir/deploy/verify_health_sha.py" \
     "$expected_sha" "$health_url" --unix-socket "$health_socket" \
     --attempts 30 --delay 2 --timeout 5; then
  echo "production_deploy.sh: no replacement worker served ${expected_sha}" >&2
  exit 1
fi

echo "Deployed ${expected_sha} to Flask with a verified graceful worker reload."

if [[ "$skip_public" == true ]]; then
  echo "production_deploy.sh: skipping the public host and API (--skip-public)" >&2
elif [[ -x "$repo_dir/deploy/release_public.sh" ]]; then
  "$repo_dir/deploy/release_public.sh" "$expected_sha"
else
  echo "production_deploy.sh: deploy/release_public.sh is missing; skipping the public host and API" >&2
fi

if [[ "$routing" == true ]]; then
  if [[ ! -x "$repo_dir/deploy/release_routing.sh" ]]; then
    echo "production_deploy.sh: deploy/release_routing.sh is missing; refusing to claim routing was activated" >&2
    exit 1
  fi
  "$repo_dir/deploy/release_routing.sh" "$expected_sha"
elif [[ -f /etc/apache2/mielenosoitukset-react-ssr.conf ]] && \
     ! cmp -s "$repo_dir/deploy/apache/react-ssr-routing.conf" /etc/apache2/mielenosoitukset-react-ssr.conf; then
  # Routing stays a separate, explicit step; say so instead of letting the
  # release look fully activated when a route set is still handled by Flask.
  echo "production_deploy.sh: the active Apache routing include differs from ${expected_sha}; run 'deploy-routing ${expected_sha}' to activate it" >&2
fi

if [[ "$skip_public" == true ]]; then
  echo "Deployed ${expected_sha} to Flask; the public host and API were skipped."
else
  echo "Deployed ${expected_sha} to Flask, the React public host and the Go API."
fi
exit 0

