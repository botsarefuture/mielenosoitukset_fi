#!/usr/bin/env bash
# Deploy the CI-built public React host and Go API for one commit.
#
# Called by production_deploy.sh after the checkout is at the requested commit,
# so every input here comes from the repository at that commit plus the release
# assets CI attached to it. Only the services that do not already report this
# commit are touched, which makes re-runs and partial failures resumable.
set -euo pipefail

expected_sha=${1:?full commit SHA required}
repo_dir=${PRODUCTION_REPO_DIR:-/var/www/mielenosoitukset_fi}
production_python=${PRODUCTION_PYTHON:-python3}
api_health_url=${PUBLIC_API_HEALTH_URL:-http://127.0.0.1:8091/health}
host_health_url=${PUBLIC_HOST_HEALTH_URL:-http://127.0.0.1:8090/health}

[[ $expected_sha =~ ^[0-9a-f]{40}$ ]] || {
  echo "release_public.sh: expected a full 40-character commit SHA" >&2
  exit 2
}
[[ $(id -u) == 0 ]] || {
  echo "release_public.sh: root required" >&2
  exit 2
}

cd "$repo_dir"

log() { printf 'release_public: %s\n' "$*"; }

# deployed_sha <health-url> prints the build SHA a service reports, and nothing
# when it is down, unreachable, or not reporting a full SHA. The SHA each service
# reports is the same value the release scripts verify, so it is the only honest
# answer to "is this service already at this commit?" - git history is not.
deployed_sha() {
  "$production_python" - "$1" <<'PY' 2>/dev/null || true
import json
import sys
from urllib.request import urlopen

with urlopen(sys.argv[1], timeout=5) as response:
    payload = json.load(response)
sha = payload.get("build_sha")
if isinstance(sha, str) and len(sha) == 40:
    print(sha)
PY
}

deploy_api=true
deploy_host=true
if [[ "$(deployed_sha "$api_health_url")" == "$expected_sha" ]]; then
  deploy_api=false
  log "the Go API already reports ${expected_sha}"
fi
if [[ "$(deployed_sha "$host_health_url")" == "$expected_sha" ]]; then
  deploy_host=false
  log "the React public host already reports ${expected_sha}"
fi

if [[ $deploy_api == false && $deploy_host == false ]]; then
  log "both public services already report ${expected_sha}"
  exit 0
fi

remote=$(git remote get-url origin)
case $remote in
  https://github.com/*) slug=${remote#https://github.com/} ;;
  git@github.com:*) slug=${remote#git@github.com:} ;;
  *)
    log "unsupported origin remote; expected a GitHub repository"
    exit 1
    ;;
esac
slug=${slug%.git}
[[ $slug =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || {
  log "could not derive owner/name from origin remote"
  exit 1
}

stage=$(mktemp -d /run/moso-public-release.XXXXXX)
trap 'rm -rf -- "$stage"' EXIT

assets=()
if [[ $deploy_api == true ]]; then assets+=(--asset api); fi
if [[ $deploy_host == true ]]; then assets+=(--asset app.tar.gz); fi

log "downloading release assets for ${expected_sha} from ${slug}"
"$production_python" deploy/release_artifacts.py \
  --repository "$slug" \
  --sha "$expected_sha" \
  --output "$stage/assets" \
  "${assets[@]}"

if [[ $deploy_api == true ]]; then
  install -d -m 0700 "$stage/go"
  cp deploy/go-api/deploy.sh \
     deploy/go-api/configure_environment.py \
     deploy/go-api/mielenosoitukset-api.service \
     "$stage/go/"
  install -m 0755 "$stage/assets/api" "$stage/go/api"
  api_sha=$(sha256sum "$stage/go/api" | cut -d' ' -f1)
  log "deploying the Go API at ${expected_sha}"
  bash "$stage/go/deploy.sh" "$expected_sha" "$api_sha"
fi

if [[ $deploy_host == true ]]; then
  install -d -m 0700 "$stage/public"
  cp deploy/public-app/deploy.sh \
     deploy/public-app/environment \
     deploy/public-app/mielenosoitukset-public.service \
     "$stage/public/"
  install -m 0600 "$stage/assets/app.tar.gz" "$stage/public/app.tar.gz"
  app_sha=$(sha256sum "$stage/public/app.tar.gz" | cut -d' ' -f1)
  log "deploying the React public host at ${expected_sha}"
  bash "$stage/public/deploy.sh" "$expected_sha" "$app_sha"
fi

log "public services are at ${expected_sha}"
