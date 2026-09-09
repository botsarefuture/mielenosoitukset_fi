#!/usr/bin/env bash

set -euo pipefail

repo_dir="${PRODUCTION_REPO_DIR:-/var/www/mielenosoitukset_fi}"
service_name="${PRODUCTION_SERVICE_NAME:-mielenosoitukset_fi}"
health_url="${PRODUCTION_HEALTH_URL:-https://mielenosoitukset.fi/health}"
expected_sha="${1:-}"

if [[ ! "$expected_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "production_deploy.sh: expected a full 40-character commit SHA" >&2
  exit 2
fi

exec 9>"${PRODUCTION_LOCK_FILE:-/run/lock/mielenosoitukset-fi-deploy.lock}"
flock -w 300 9 || {
  echo "production_deploy.sh: another deployment still holds the lock" >&2
  exit 1
}

cd "$repo_dir"
git config --global --add safe.directory "$repo_dir" >/dev/null 2>&1 || true

old_sha="$(git rev-parse HEAD)"
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

if ! git diff --quiet "$old_sha" "$expected_sha" -- requirements.txt; then
  python3 -m pip install --disable-pip-version-check --requirement requirements.txt
fi

if ! restore_local_changes; then
  trap - EXIT
  exit 1
fi
trap - EXIT

chown -R www-data:www-data "$repo_dir"

# Gunicorn's HUP reload starts replacement workers before retiring the old
# workers, avoiding the hard outage caused by systemctl restart.
systemctl reload "$service_name"

for attempt in $(seq 1 30); do
  if systemctl is-active --quiet "$service_name" && \
     curl --fail --silent --show-error --max-time 5 \
       --header 'Cache-Control: no-cache' \
       "${health_url}?deploy=${expected_sha}" >/dev/null; then
    echo "Deployed ${expected_sha} with a graceful worker reload."
    exit 0
  fi
  sleep 2
done

echo "production_deploy.sh: health check did not recover after deploying ${expected_sha}" >&2
exit 1
