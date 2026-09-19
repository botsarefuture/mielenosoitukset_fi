#!/usr/bin/env bash

set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_file="${1:-${repo_dir}/messages.pot}"

cd "$repo_dir"
pybabel extract \
  -F babel.cfg \
  -k flash_message:1 \
  --ignore-dirs='.* ._ tests venv .venv volume data' \
  -o "$output_file" \
  .
