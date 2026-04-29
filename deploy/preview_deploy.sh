#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  preview_deploy.sh deploy <pr_number> <image_tag>
  preview_deploy.sh destroy <pr_number>
EOF
}

die() {
  echo "preview_deploy.sh: $*" >&2
  exit 1
}

require_var() {
  local name="$1"
  local value="${2:-}"
  if [[ -z "$value" ]]; then
    die "missing required environment variable: $name"
  fi
}

source_env_file() {
  local env_file="${PREVIEW_ENV_FILE:-/etc/mielenosoitukset-preview.env}"
  if [[ ! -f "$env_file" ]]; then
    die "preview environment file not found: $env_file"
  fi

  # shellcheck disable=SC1090
  set -a
  source "$env_file"
  set +a
}

render_config() {
  local config_file="$1"
  local hostname="$2"
  local db_name="$3"
  local mongo_host="$4"

  cat >"$config_file" <<EOF
SECRET_KEY: "${PREVIEW_SECRET_KEY}"
MONGO_URI: "mongodb://${mongo_host}:27017"
MONGO_DBNAME: "${db_name}"
MAIL:
  SERVER: "${PREVIEW_MAIL_SERVER:-mailserver}"
  PORT: ${PREVIEW_MAIL_PORT:-1025}
  USE_TLS: ${PREVIEW_MAIL_USE_TLS:-false}
  USERNAME: "${PREVIEW_MAIL_USERNAME:-}"
  PASSWORD: "${PREVIEW_MAIL_PASSWORD:-}"
  DEFAULT_SENDER: "${PREVIEW_MAIL_DEFAULT_SENDER:-${PREVIEW_MAIL_USERNAME:-preview@mielenosoitukset.fi}}"
SERVER_NAME: "${hostname}"
PREFERRED_URL_SCHEME: "https"
PORT: 5002
DEBUG: false
CDN_BASE_URL: "${PREVIEW_CDN_BASE_URL:-https://${hostname}}"
CACHE_TYPE: "SimpleCache"
CACHE_DEFAULT_TIMEOUT: 60
REDIS_HOST: "${PREVIEW_REDIS_HOST:-redis}"
REDIS_PORT: ${PREVIEW_REDIS_PORT:-6379}
REDIS_DB: ${PREVIEW_REDIS_DB:-0}
DEFAULT_TIMEZONE: "${PREVIEW_DEFAULT_TIMEZONE:-Europe/Helsinki}"
ENFORCE_RATELIMIT: false
ENABLE_CHAT: false
ENABLE_EMAIL_WORKER: false
ENABLE_PANIC_THREAD: false
ENABLE_BACKGROUND_JOBS: false
BABEL:
  DEFAULT_LOCALE: "${PREVIEW_DEFAULT_LOCALE:-fi}"
  SUPPORTED_LOCALES:
    - "fi"
  LANGUAGES:
    fi: "Suomi"
EOF
}

wait_for_mongo() {
  local network="$1"
  local mongo_host="$2"

  for _ in $(seq 1 60); do
    if docker run --rm --network "$network" mongo:8 mongosh "mongodb://${mongo_host}:27017" --quiet --eval 'db.adminCommand({ ping: 1 }).ok' >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  die "preview MongoDB did not become ready"
}

seed_mongo_if_requested() {
  local network="$1"
  local preview_dir="$2"
  local dest_db="$4"
  local mongo_host="$5"

  if [[ -z "${PREVIEW_MONGO_SOURCE_URI:-}" || -z "${PREVIEW_MONGO_SOURCE_DB:-}" ]]; then
    return 0
  fi

  local dump_file="${preview_dir}/mongo-seed.archive.gz"

  docker run --rm \
    -v "${preview_dir}:/dump" \
    -e SOURCE_URI="${PREVIEW_MONGO_SOURCE_URI}" \
    -e SOURCE_DB="${PREVIEW_MONGO_SOURCE_DB}" \
    mongo:8 bash -lc 'mongodump --uri "$SOURCE_URI" --db "$SOURCE_DB" --archive=/dump/mongo-seed.archive.gz --gzip'

  docker run --rm \
    --network "$network" \
    -v "${preview_dir}:/dump" \
    -e SOURCE_DB="${PREVIEW_MONGO_SOURCE_DB}" \
    -e DEST_DB="${dest_db}" \
    -e MONGO_HOST="${mongo_host}" \
    mongo:8 bash -lc 'mongorestore --uri "mongodb://${MONGO_HOST}:27017" --nsFrom "${SOURCE_DB}.*" --nsTo "${DEST_DB}.*" --drop --archive=/dump/mongo-seed.archive.gz --gzip'

  rm -f "$dump_file"
}

start_mongo_container() {
  local mongo_container="$1"
  local network="$2"
  local mongo_data_dir="$3"

  mkdir -p "$mongo_data_dir"

  docker rm -f "$mongo_container" >/dev/null 2>&1 || true
  docker run -d \
    --name "$mongo_container" \
    --network "$network" \
    --network-alias mongo \
    --restart unless-stopped \
    -v "$mongo_data_dir:/data/db" \
    mongo:8 \
    mongod --bind_ip_all --port 27017 >/dev/null
}

start_mail_container() {
  local mail_container="$1"
  local network="$2"

  docker rm -f "$mail_container" >/dev/null 2>&1 || true
  docker run -d \
    --name "$mail_container" \
    --network "$network" \
    --network-alias mailserver \
    --restart unless-stopped \
    reachfive/fake-smtp-server >/dev/null
}

create_network() {
  local network="$1"
  if ! docker network inspect "$network" >/dev/null 2>&1; then
    if [[ "${PREVIEW_INTERNAL_NETWORK:-true}" == "true" ]]; then
      docker network create --internal "$network" >/dev/null
    else
      docker network create "$network" >/dev/null
    fi
  fi
}

deploy_preview() {
  local pr_number="$1"
  local image_tag="$2"

  source_env_file

  require_var PREVIEW_DOMAIN "${PREVIEW_DOMAIN:-}"
  require_var PREVIEW_BASE_DIR "${PREVIEW_BASE_DIR:-/srv/mielenosoitukset-fi-previews}"
  require_var PREVIEW_SNIPPETS_DIR "${PREVIEW_SNIPPETS_DIR:-/etc/caddy/previews}"
  require_var PREVIEW_RELOAD_CMD "${PREVIEW_RELOAD_CMD:-systemctl reload caddy}"
  require_var PREVIEW_SECRET_KEY "${PREVIEW_SECRET_KEY:-}"

  local domain="${PREVIEW_DOMAIN}"
  local base_dir="${PREVIEW_BASE_DIR:-/srv/mielenosoitukset-fi-previews}"
  local snippets_dir="${PREVIEW_SNIPPETS_DIR:-/etc/caddy/previews}"
  local reload_cmd="${PREVIEW_RELOAD_CMD:-systemctl reload caddy}"
  local hostname="pr-${pr_number}.${domain}"
  local preview_dir="${base_dir}/pr-${pr_number}"
  local config_file="${preview_dir}/config.preview.yaml"
  local snippet_file="${snippets_dir}/pr-${pr_number}.caddy"
  local container_name="mielenosoitukset-preview-pr-${pr_number}"
  local mongo_container="mielenosoitukset-preview-mongo-pr-${pr_number}"
  local mail_container="mielenosoitukset-preview-mail-pr-${pr_number}"
  local network_name="${PREVIEW_NETWORK_PREFIX:-mielenosoitukset-preview}-pr-${pr_number}"
  local port_base="${PREVIEW_PORT_BASE:-20000}"
  local port="$((port_base + pr_number))"
  local db_name="${PREVIEW_MONGO_DBNAME_PREFIX:-preview_pr_}${pr_number}"
  local mongo_host="${mongo_container}"
  local mongo_data_dir="${preview_dir}/mongo"

  mkdir -p "$preview_dir" "$snippets_dir"
  chmod 0750 "$preview_dir" "$snippets_dir"

  echo "[preview] creating isolated network and service containers"
  create_network "$network_name"
  start_mongo_container "$mongo_container" "$network_name" "$mongo_data_dir"
  start_mail_container "$mail_container" "$network_name"

  echo "[preview] waiting for MongoDB to become ready"
  wait_for_mongo "$network_name" "$mongo_host"

  echo "[preview] writing preview application config"
  render_config "$config_file" "$hostname" "$db_name" "$mongo_host"
  chmod 0640 "$config_file"

  echo "[preview] seeding preview database if configured"
  seed_mongo_if_requested "$network_name" "$preview_dir" "$db_name" "$mongo_host"

  echo "[preview] starting application container"
  docker rm -f "$container_name" >/dev/null 2>&1 || true

  docker run -d \
    --name "$container_name" \
    --network "$network_name" \
    -p "127.0.0.1:${port}:5002" \
    --cap-drop=ALL \
    --security-opt no-new-privileges:true \
    --pids-limit 256 \
    --memory "${PREVIEW_MEMORY_LIMIT:-1024m}" \
    --cpus "${PREVIEW_CPU_LIMIT:-1.5}" \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /var/tmp:rw,noexec,nosuid,size=16m \
    --restart unless-stopped \
    -e HOST=0.0.0.0 \
    -e PORT=5002 \
    -e CONFIG_YAML_PATH=/app/config.preview.yaml \
    -v "$config_file:/app/config.preview.yaml:ro" \
    "$image_tag" >/dev/null

  echo "[preview] publishing caddy snippet"
  cat >"$snippet_file" <<EOF
$hostname {
  encode zstd gzip
  reverse_proxy 127.0.0.1:${port}
}
EOF
  chmod 0644 "$snippet_file"

  echo "[preview] reloading caddy"
  eval "$reload_cmd"

  echo "https://${hostname}"
}

destroy_preview() {
  local pr_number="$1"

  source_env_file

  require_var PREVIEW_DOMAIN "${PREVIEW_DOMAIN:-}"
  require_var PREVIEW_BASE_DIR "${PREVIEW_BASE_DIR:-/srv/mielenosoitukset-fi-previews}"
  require_var PREVIEW_SNIPPETS_DIR "${PREVIEW_SNIPPETS_DIR:-/etc/caddy/previews}"
  require_var PREVIEW_RELOAD_CMD "${PREVIEW_RELOAD_CMD:-systemctl reload caddy}"

  local base_dir="${PREVIEW_BASE_DIR:-/srv/mielenosoitukset-fi-previews}"
  local snippets_dir="${PREVIEW_SNIPPETS_DIR:-/etc/caddy/previews}"
  local reload_cmd="${PREVIEW_RELOAD_CMD:-systemctl reload caddy}"
  local preview_dir="${base_dir}/pr-${pr_number}"
  local snippet_file="${snippets_dir}/pr-${pr_number}.caddy"
  local container_name="mielenosoitukset-preview-pr-${pr_number}"
  local mongo_container="mielenosoitukset-preview-mongo-pr-${pr_number}"
  local mail_container="mielenosoitukset-preview-mail-pr-${pr_number}"
  local network_name="${PREVIEW_NETWORK_PREFIX:-mielenosoitukset-preview}-pr-${pr_number}"

  docker rm -f "$container_name" >/dev/null 2>&1 || true
  docker rm -f "$mongo_container" >/dev/null 2>&1 || true
  docker rm -f "$mail_container" >/dev/null 2>&1 || true
  rm -f "$snippet_file"
  rm -rf "$preview_dir"
  docker network rm "$network_name" >/dev/null 2>&1 || true

  eval "$reload_cmd"
}

main() {
  if [[ $# -lt 2 ]]; then
    usage
    exit 1
  fi

  local command="$1"
  local pr_number="$2"

  case "$command" in
    deploy)
      [[ $# -eq 3 ]] || { usage; exit 1; }
      deploy_preview "$pr_number" "$3"
      ;;
    destroy)
      destroy_preview "$pr_number"
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
