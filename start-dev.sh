#!/usr/bin/env bash
set -Eeuo pipefail

# =========================
# Config
# =========================
HOSTNAME_ENTRY="miekkari.localhost"
HOSTS_LINE="127.0.0.1 ${HOSTNAME_ENTRY}"

CONFIG_FILE="config.compose.dev.yaml"
CONFIG_EXAMPLE="config.compose.dev.example.yaml"

COMPOSE_FILE="compose.dev.yml"
COMPOSE=(docker compose -f "$COMPOSE_FILE")

CADDY_SERVICE="caddy"
CADDY_CONTAINER="mielenosoitukset_caddy"
CADDY_ROOT_CA_PATH="/data/caddy/pki/authorities/local/root.crt"

SYSTEM_CERT_NAME="miekkari-caddy-local-root.crt"
SYSTEM_CERT_DEST="/usr/local/share/ca-certificates/${SYSTEM_CERT_NAME}"

FIREFOX_CERT_NICK="Caddy Local Dev CA"

# =========================
# Pretty output
# =========================
log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✅\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m⚠️ \033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m❌\033[0m %s\n' "$*" >&2; }

cleanup() {
  if [[ -n "${TMP_CERT:-}" && -f "${TMP_CERT:-}" ]]; then
    rm -f "$TMP_CERT"
  fi
}
trap cleanup EXIT

# =========================
# Helpers
# =========================
require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    err "Required command not found: $1"
    exit 1
  }
}

file_sha256() {
  sha256sum "$1" | awk '{print $1}'
}

wait_for_command_success() {
  local description="$1"
  shift
  local attempts="${WAIT_ATTEMPTS:-120}"
  local sleep_seconds="${WAIT_SLEEP_SECONDS:-1}"

  log "$description"
  for ((i=1; i<=attempts; i++)); do
    if "$@" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$sleep_seconds"
  done

  err "Timed out: $description"
  return 1
}

is_firefox_running() {
  pgrep -x firefox >/dev/null 2>&1 \
    || pgrep -x firefox-bin >/dev/null 2>&1 \
    || pgrep -f '/firefox' >/dev/null 2>&1
}

wait_for_firefox_to_close() {
  if is_firefox_running; then
    warn "Firefox is running."
    warn "Please close all Firefox windows so certificate import can succeed."
    while is_firefox_running; do
      printf '   Waiting for Firefox to close...\n'
      sleep 2
    done
    ok "Firefox is closed"
  else
    ok "Firefox is not running"
  fi
}

close_firefox_gracefully() {
  if is_firefox_running; then
    log "Closing Firefox gracefully"
    killall -TERM firefox firefox-bin 2>/dev/null || true
    
    # Wait up to 10 seconds for firefox to close
    local counter=0
    while is_firefox_running && [[ $counter -lt 10 ]]; do
      sleep 0.5
      ((counter++))
    done
    
    # If firefox is still running, force kill it
    if is_firefox_running; then
      warn "Firefox did not shut down gracefully, forcing shutdown"
      killall -KILL firefox firefox-bin 2>/dev/null || true
      sleep 1
    fi
    
    ok "Firefox closed"
    return 0
  else
    return 1
  fi
}

reopen_firefox() {
  log "Reopening Firefox"
  
  # Find firefox executable
  local firefox_cmd
  if command -v firefox >/dev/null 2>&1; then
    firefox_cmd="firefox"
  elif command -v firefox-bin >/dev/null 2>&1; then
    firefox_cmd="firefox-bin"
  else
    warn "Could not find firefox executable"
    return 1
  fi
  
  # Reopen firefox in background
  nohup "$firefox_cmd" >/dev/null 2>&1 &
  ok "Firefox reopened in background"
}

ensure_hosts_entry() {
  log "Checking /etc/hosts"
  if grep -qE "(^|[[:space:]])${HOSTNAME_ENTRY}([[:space:]]|$)" /etc/hosts; then
    ok "${HOSTNAME_ENTRY} is already present in /etc/hosts"
  else
    warn "${HOSTNAME_ENTRY} is missing from /etc/hosts"
    echo "${HOSTS_LINE}" | sudo tee -a /etc/hosts >/dev/null
    ok "Added ${HOSTNAME_ENTRY} to /etc/hosts"
  fi
}

ensure_config_file() {
  log "Checking compose config file"
  if [[ -f "$CONFIG_FILE" ]]; then
    ok "${CONFIG_FILE} already exists"
    return 0
  fi

  if [[ -f "$CONFIG_EXAMPLE" ]]; then
    cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
    ok "Created ${CONFIG_FILE} from ${CONFIG_EXAMPLE}"
  else
    warn "${CONFIG_FILE} does not exist and ${CONFIG_EXAMPLE} was not found"
  fi
}

start_compose() {
  log "Starting Docker Compose"
  "${COMPOSE[@]}" up -d
  ok "Docker Compose started"
}

wait_for_caddy() {
  wait_for_command_success \
    "Waiting for Caddy service to be running" \
    "${COMPOSE[@]}" ps --status running "$CADDY_SERVICE"

  wait_for_command_success \
    "Waiting for Caddy local root CA to exist" \
    "${COMPOSE[@]}" exec -T "$CADDY_SERVICE" sh -c "test -f '$CADDY_ROOT_CA_PATH'"

  ok "Caddy local CA is available"
}

copy_caddy_root_ca() {
  TMP_CERT="$(mktemp)"
  log "Copying Caddy local root CA from container"
  docker cp "${CADDY_CONTAINER}:${CADDY_ROOT_CA_PATH}" "$TMP_CERT" >/dev/null
  ok "Copied Caddy root CA to temporary file"
}

install_system_ca_if_needed() {
  log "Checking system trust store certificate"

  local needs_install="yes"

  if [[ -f "$SYSTEM_CERT_DEST" ]]; then
    local existing_hash new_hash
    existing_hash="$(file_sha256 "$SYSTEM_CERT_DEST")"
    new_hash="$(file_sha256 "$TMP_CERT")"

    if [[ "$existing_hash" == "$new_hash" ]]; then
      needs_install="no"
    fi
  fi

  if [[ "$needs_install" == "no" ]]; then
    ok "System CA already matches current Caddy CA — skipping reinstall"
    return 0
  fi

  sudo cp "$TMP_CERT" "$SYSTEM_CERT_DEST"
  sudo update-ca-certificates >/dev/null
  ok "Installed/updated system CA at ${SYSTEM_CERT_DEST}"
}

ensure_certutil() {
  if command -v certutil >/dev/null 2>&1; then
    ok "certutil already installed"
    return 0
  fi

  log "Installing libnss3-tools"
  sudo apt-get update -y
  sudo apt-get install -y libnss3-tools
  ok "Installed libnss3-tools"
}

find_firefox_profiles() {
  local dirs=(
    "$HOME/.mozilla/firefox"
    "$HOME/snap/firefox/common/.mozilla/firefox"
    "$HOME/.var/app/org.mozilla.firefox/.mozilla/firefox"
  )

  local found_any=1

  for base in "${dirs[@]}"; do
    [[ -d "$base" ]] || continue
    found_any=0
    find "$base" -mindepth 1 -maxdepth 1 -type d 2>/dev/null
  done

  return "$found_any"
}

firefox_profile_has_cert() {
  local profile="$1"
  certutil -L -d "sql:${profile}" 2>/dev/null | grep -Fq "$FIREFOX_CERT_NICK"
}

firefox_profile_cert_matches() {
  local profile="$1"
  local existing_export
  existing_export="$(mktemp)"

  if ! certutil -L -d "sql:${profile}" -n "$FIREFOX_CERT_NICK" -a >"$existing_export" 2>/dev/null; then
    rm -f "$existing_export"
    return 1
  fi

  local existing_hash new_hash
  existing_hash="$(file_sha256 "$existing_export")"
  new_hash="$(file_sha256 "$TMP_CERT")"
  rm -f "$existing_export"

  [[ "$existing_hash" == "$new_hash" ]]
}

import_firefox_ca() {
  ensure_certutil

  log "Checking if Firefox is running"
  local firefox_was_open=0
  
  # Check if Firefox is open and close it gracefully if needed
  if is_firefox_running; then
    firefox_was_open=1
    close_firefox_gracefully
  else
    ok "Firefox is not running"
  fi

  log "Checking Firefox profiles"

  local profiles=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && profiles+=("$line")
  done < <(find_firefox_profiles || true)

  if [[ "${#profiles[@]}" -eq 0 ]]; then
    warn "No Firefox profiles found — skipping Firefox import"
    
    # Reopen Firefox if it was open before
    if [[ $firefox_was_open -eq 1 ]]; then
      sleep 1
      reopen_firefox
    fi
    return 0
  fi

  local profile
  for profile in "${profiles[@]}"; do
    log "Processing Firefox profile: ${profile}"

    if [[ ! -f "${profile}/cert9.db" && ! -f "${profile}/key4.db" ]]; then
      warn "Skipping ${profile} (not an NSS profile)"
      continue
    fi

    if firefox_profile_has_cert "$profile"; then
      if firefox_profile_cert_matches "$profile"; then
        ok "Firefox profile already trusts the current CA — skipping"
        continue
      else
        warn "Firefox profile has an older/different CA with same nickname — replacing"
        certutil -D -d "sql:${profile}" -n "$FIREFOX_CERT_NICK" >/dev/null 2>&1 || true
      fi
    fi

    certutil -A \
      -d "sql:${profile}" \
      -n "$FIREFOX_CERT_NICK" \
      -t "C,," \
      -i "$TMP_CERT"

    ok "Imported CA into Firefox profile"
  done
  
  # Reopen Firefox if it was open before
  if [[ $firefox_was_open -eq 1 ]]; then
    sleep 1
    reopen_firefox
  fi
}

print_final_notes() {
  echo
  ok "Dev environment bootstrap completed"
  echo
  echo "Open:"
  echo "  https://${HOSTNAME_ENTRY}"
  echo
  echo "If your compose maps HTTPS to host port 8443 instead of 443, use:"
  echo "  https://${HOSTNAME_ENTRY}:8443"
  echo
}

main() {
  require_cmd docker
  require_cmd sudo
  require_cmd sha256sum
  require_cmd grep
  require_cmd awk

  ensure_hosts_entry
  ensure_config_file
  start_compose
  wait_for_caddy
  copy_caddy_root_ca
  install_system_ca_if_needed
  import_firefox_ca
  print_final_notes
}

main "$@"