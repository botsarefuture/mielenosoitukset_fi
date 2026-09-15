#!/usr/bin/env bash

set -euo pipefail

# This is the forced command for the dedicated GitHub Actions SSH key. The key
# can request only one exact operation and cannot obtain an interactive root
# shell, forward ports, or select another executable.
read -r command commit_sha extra <<<"${SSH_ORIGINAL_COMMAND:-}"

if [[ "$command" != "deploy" || ! "$commit_sha" =~ ^[0-9a-f]{40}$ || -n "${extra:-}" ]]; then
  echo "Only 'deploy <40-character commit SHA>' is allowed." >&2
  exit 2
fi

exec /root/update-moso.sh "$commit_sha"
