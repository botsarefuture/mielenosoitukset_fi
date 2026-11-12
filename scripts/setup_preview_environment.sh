#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  setup_preview_environment.sh [--repo owner/name] [--apply] [--print-only]

Environment variables:
  PREVIEW_SSH_HOST
  PREVIEW_SSH_USER
  PREVIEW_DOMAIN
  PREVIEW_BASE_DIR
  PREVIEW_SNIPPETS_DIR
  PREVIEW_RELOAD_CMD
  PREVIEW_ENV_FILE
  PREVIEW_SSH_PRIVATE_KEY_PATH
  PREVIEW_SSH_PRIVATE_KEY
  PREVIEW_SECRET_KEY
  PREVIEW_MONGO_SOURCE_URI
  PREVIEW_MONGO_SOURCE_DB
  PREVIEW_MAIL_SERVER
  PREVIEW_MAIL_USERNAME
  PREVIEW_MAIL_PASSWORD
  PREVIEW_CDN_BASE_URL
EOF
}

die() {
  echo "setup_preview_environment.sh: $*" >&2
  exit 1
}

require_value() {
  local name="$1"
  local value="${2:-}"
  if [[ -z "$value" ]]; then
    die "missing required value: $name"
  fi
}

is_logged_in() {
  gh auth status >/dev/null 2>&1
}

get_repo() {
  if [[ -n "${REPO:-}" ]]; then
    echo "$REPO"
    return 0
  fi

  if gh repo view >/dev/null 2>&1; then
    gh repo view --json nameWithOwner -q .nameWithOwner
    return 0
  fi

  local repo
  repo="$(git remote get-url origin 2>/dev/null || true)"
  case "$repo" in
    git@github.com:*)
      echo "${repo#git@github.com:}" | sed 's#\.git$##'
      ;;
    https://github.com/*)
      echo "${repo#https://github.com/}" | sed 's#\.git$##'
      ;;
    *)
      die "could not infer repository; pass --repo owner/name"
      ;;
  esac
}

print_setting() {
  local label="$1"
  local value="${2:-}"
  printf '%-24s %s\n' "$label" "${value:-<missing>}"
}

set_repo_var() {
  local repo="$1"
  local name="$2"
  local value="$3"
  gh variable set "$name" --repo "$repo" --body "$value" >/dev/null
}

set_repo_secret() {
  local repo="$1"
  local name="$2"
  local value_file="$3"
  gh secret set "$name" --repo "$repo" < "$value_file" >/dev/null
}

main() {
  local repo=""
  local apply="false"
  local print_only="false"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo)
        repo="${2:-}"
        shift 2
        ;;
      --apply)
        apply="true"
        shift
        ;;
      --print-only)
        print_only="true"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument: $1"
        ;;
    esac
  done

  repo="${repo:-$(get_repo)}"

  local preview_ssh_host="${PREVIEW_SSH_HOST:-}"
  local preview_ssh_user="${PREVIEW_SSH_USER:-}"
  local preview_domain="${PREVIEW_DOMAIN:-}"
  local preview_base_dir="${PREVIEW_BASE_DIR:-/srv/mielenosoitukset-fi-previews}"
  local preview_snippets_dir="${PREVIEW_SNIPPETS_DIR:-/etc/caddy/previews}"
  local preview_reload_cmd="${PREVIEW_RELOAD_CMD:-sudo -n /usr/bin/systemctl restart caddy}"
  local preview_env_file="${PREVIEW_ENV_FILE:-/etc/mielenosoitukset-preview.env}"
  local preview_secret_key="${PREVIEW_SECRET_KEY:-}"
  local preview_mongo_source_uri="${PREVIEW_MONGO_SOURCE_URI:-}"
  local preview_mongo_source_db="${PREVIEW_MONGO_SOURCE_DB:-}"
  local preview_mail_server="${PREVIEW_MAIL_SERVER:-}"
  local preview_mail_username="${PREVIEW_MAIL_USERNAME:-}"
  local preview_mail_password="${PREVIEW_MAIL_PASSWORD:-}"
  local preview_cdn_base_url="${PREVIEW_CDN_BASE_URL:-}"
  local ssh_key_path="${PREVIEW_SSH_PRIVATE_KEY_PATH:-}"
  local ssh_key_value="${PREVIEW_SSH_PRIVATE_KEY:-}"

  if [[ "$print_only" == "true" ]]; then
    apply="false"
  fi

  if [[ "$apply" == "true" ]] && ! is_logged_in; then
    die "gh is not authenticated. Run 'gh auth login' and rerun with --apply, or use --print-only."
  fi

  cat <<EOF
Repository: ${repo}

GitHub repository variables:
EOF
  print_setting PREVIEW_SSH_HOST "$preview_ssh_host"
  print_setting PREVIEW_SSH_USER "$preview_ssh_user"
  print_setting PREVIEW_DOMAIN "$preview_domain"
  print_setting PREVIEW_BASE_DIR "$preview_base_dir"
  print_setting PREVIEW_SNIPPETS_DIR "$preview_snippets_dir"
  print_setting PREVIEW_RELOAD_CMD "$preview_reload_cmd"
  print_setting PREVIEW_ENV_FILE "$preview_env_file"

  cat <<EOF

GitHub repository secret:
EOF
  if [[ -n "$ssh_key_path" ]]; then
    print_setting PREVIEW_SSH_PRIVATE_KEY_PATH "$ssh_key_path"
  else
    print_setting PREVIEW_SSH_PRIVATE_KEY "<set from PREVIEW_SSH_PRIVATE_KEY>"
  fi

  cat <<EOF

Server preview env file (${preview_env_file}):
EOF
  print_setting PREVIEW_SECRET_KEY "$preview_secret_key"
  print_setting PREVIEW_MONGO_SOURCE_URI "$preview_mongo_source_uri"
  print_setting PREVIEW_MONGO_SOURCE_DB "$preview_mongo_source_db"
  print_setting PREVIEW_MAIL_SERVER "$preview_mail_server"
  print_setting PREVIEW_MAIL_USERNAME "$preview_mail_username"
  print_setting PREVIEW_MAIL_PASSWORD "$preview_mail_password"
  print_setting PREVIEW_CDN_BASE_URL "$preview_cdn_base_url"

  if [[ "$apply" != "true" ]]; then
    cat <<EOF

To apply these values manually, use:
  gh variable set PREVIEW_SSH_HOST --repo ${repo} --body "${preview_ssh_host}"
  gh variable set PREVIEW_SSH_USER --repo ${repo} --body "${preview_ssh_user}"
  gh variable set PREVIEW_DOMAIN --repo ${repo} --body "${preview_domain}"
  gh variable set PREVIEW_BASE_DIR --repo ${repo} --body "${preview_base_dir}"
  gh variable set PREVIEW_SNIPPETS_DIR --repo ${repo} --body "${preview_snippets_dir}"
  gh variable set PREVIEW_RELOAD_CMD --repo ${repo} --body "${preview_reload_cmd}"
  gh variable set PREVIEW_ENV_FILE --repo ${repo} --body "${preview_env_file}"
  gh secret set PREVIEW_SSH_PRIVATE_KEY --repo ${repo} < "${ssh_key_path:-/path/to/private_key}"
EOF
    exit 0
  fi

  require_value PREVIEW_SSH_HOST "$preview_ssh_host"
  require_value PREVIEW_SSH_USER "$preview_ssh_user"
  require_value PREVIEW_DOMAIN "$preview_domain"
  require_value PREVIEW_ENV_FILE "$preview_env_file"

  local tmp_key=""
  if [[ -n "$ssh_key_path" ]]; then
    [[ -f "$ssh_key_path" ]] || die "PREVIEW_SSH_PRIVATE_KEY_PATH does not exist: $ssh_key_path"
    tmp_key="$ssh_key_path"
  elif [[ -n "$ssh_key_value" ]]; then
    tmp_key="$(mktemp)"
    printf '%s' "$ssh_key_value" >"$tmp_key"
  else
    die "set PREVIEW_SSH_PRIVATE_KEY_PATH or PREVIEW_SSH_PRIVATE_KEY when using --apply"
  fi

  set_repo_var "$repo" PREVIEW_SSH_HOST "$preview_ssh_host"
  set_repo_var "$repo" PREVIEW_SSH_USER "$preview_ssh_user"
  set_repo_var "$repo" PREVIEW_DOMAIN "$preview_domain"
  set_repo_var "$repo" PREVIEW_BASE_DIR "$preview_base_dir"
  set_repo_var "$repo" PREVIEW_SNIPPETS_DIR "$preview_snippets_dir"
  set_repo_var "$repo" PREVIEW_RELOAD_CMD "$preview_reload_cmd"
  set_repo_var "$repo" PREVIEW_ENV_FILE "$preview_env_file"
  set_repo_secret "$repo" PREVIEW_SSH_PRIVATE_KEY "$tmp_key"

  if [[ "$tmp_key" != "$ssh_key_path" ]]; then
    rm -f "$tmp_key"
  fi

  echo "Applied GitHub repository variables and secrets for ${repo}."
}

main "$@"
