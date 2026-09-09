#!/usr/bin/env bash
set -euo pipefail

MODE="${1:---check}"

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

branch="$(git rev-parse --abbrev-ref HEAD)"
safe_branch="${branch//\//__}"
handoff_path="docs/handoffs/${safe_branch}.md"
today="$(date +%F)"

create_template() {
  mkdir -p "$(dirname "$handoff_path")"
  cat >"$handoff_path" <<EOF
# Branch Handoff: ${branch}

## Scope

- Describe the branch goal here.

## Current State

- Summarize the implemented work.

## Validation

- List the latest checks run here.

## Open Issues

- Note blockers, caveats, or review concerns.

## Next Steps

- Write the next concrete actions here.

## Updated

- ${today}
EOF
}

case "$MODE" in
  --create)
    if [ ! -f "$handoff_path" ]; then
      create_template
      printf 'Created %s\n' "$handoff_path"
    else
      printf '%s\n' "$handoff_path"
    fi
    ;;
  --path)
    printf '%s\n' "$handoff_path"
    ;;
  --check)
    if [ ! -f "$handoff_path" ]; then
      printf 'Missing branch handoff: %s\n' "$handoff_path" >&2
      printf 'Run ./scripts/ensure_agent_handoff.sh --create\n' >&2
      exit 1
    fi
    ;;
  *)
    printf 'Unknown mode: %s\n' "$MODE" >&2
    exit 2
    ;;
esac
