#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

git config core.hooksPath hooks
./scripts/ensure_agent_handoff.sh --create >/dev/null

printf 'Installed repo hooks from %s/hooks\n' "$repo_root"
printf 'Current branch handoff: %s\n' "$(./scripts/ensure_agent_handoff.sh --path)"
