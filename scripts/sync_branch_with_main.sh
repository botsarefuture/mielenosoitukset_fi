#!/usr/bin/env bash
set -euo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not inside a git repository." >&2
  exit 1
fi

current_branch="$(git branch --show-current)"
if [[ -z "${current_branch}" ]]; then
  echo "Detached HEAD; refusing to rebase." >&2
  exit 1
fi

echo "[sync] fetching origin/main"
git fetch origin main

echo "[sync] rebasing ${current_branch} onto origin/main"
if ! git rebase origin/main; then
  cat <<'EOF' >&2
Rebase stopped on conflicts.
Resolve them, then run:
  git rebase --continue
or abort with:
  git rebase --abort
EOF
  exit 1
fi

echo "[sync] branch is now aligned with origin/main"
