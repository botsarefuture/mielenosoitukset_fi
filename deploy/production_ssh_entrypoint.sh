#!/usr/bin/env bash

set -euo pipefail

# This is the forced command for the dedicated GitHub Actions SSH key. The key
# can request exactly two operations and cannot obtain an interactive root
# shell, forward ports, or select another executable.
#
# Keep this file small and stable: it only validates the request and snapshots
# the versioned deploy logic from the requested commit. The snapshot is taken
# before that script moves the checkout it was read from, so a deployment can
# never execute a half-updated copy of itself.
read -r command commit_sha extra <<<"${SSH_ORIGINAL_COMMAND:-}"

case "$command" in
  deploy) routing_argument="" ;;
  deploy-routing) routing_argument="--routing" ;;
  *)
    echo "Only 'deploy <40-character commit SHA>' or 'deploy-routing <40-character commit SHA>' is allowed." >&2
    exit 2
    ;;
esac

if [[ ! "$commit_sha" =~ ^[0-9a-f]{40}$ || -n "${extra:-}" ]]; then
  echo "Only 'deploy <40-character commit SHA>' or 'deploy-routing <40-character commit SHA>' is allowed." >&2
  exit 2
fi

repo_dir="${PRODUCTION_REPO_DIR:-/var/www/mielenosoitukset_fi}"
git -C "$repo_dir" config --global --add safe.directory "$repo_dir" >/dev/null 2>&1 || true
git -C "$repo_dir" fetch --prune --quiet origin main

if [[ "$(git -C "$repo_dir" rev-parse origin/main)" != "$commit_sha" ]]; then
  echo "Refusing a stale deployment: ${commit_sha} is not the current origin/main." >&2
  exit 1
fi

snapshot="$(mktemp /run/moso-deploy.XXXXXX.sh)"
trap 'rm -f -- "$snapshot"' EXIT
git -C "$repo_dir" show "${commit_sha}:deploy/production_deploy.sh" >"$snapshot"
chmod 0600 "$snapshot"

# /run is mounted noexec on the production host, so the snapshot is executed
# through an interpreter instead of being run directly.
if [[ -n "$routing_argument" ]]; then
  bash "$snapshot" "$routing_argument" "$commit_sha"
else
  bash "$snapshot" "$commit_sha"
fi
