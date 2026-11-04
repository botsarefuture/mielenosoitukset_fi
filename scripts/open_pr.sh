#!/usr/bin/env bash
# Create (or reuse) a pull request for the current branch without `gh auth`.
#
# Reuses the same stored HTTPS credential that `git push` already authenticates
# with (osxkeychain on macOS). Pull-request creation only needs the `repo` scope
# that push already carries, so an interactive `gh auth login` is not required.
# The token is piped directly into curl and never printed.
#
# Usage: scripts/open_pr.sh [head-branch] [base-branch] [title] [body-file|-]
#        e.g.: scripts/open_pr.sh submit-react main "Fix the wizard" /tmp/body.md
set -euo pipefail

HEAD=${1:-$(git branch --show-current)}
BASE=${2:-main}
TITLE=${3:?Usage: scripts/open_pr.sh [head] [base] [title] [body-file|-]}
BODY_FILE=${4:-}

REMOTE=$(git remote get-url origin | sed -E 's#(git@github\.com:|https://github\.com/)##; s#\.git$##')
OWNER="${REMOTE%%/*}"
REPO="${REMOTE##*/}"
API="https://api.github.com"

TOKEN=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill | sed -n 's/^password=//p')
[ -n "$TOKEN" ] || { echo "No stored GitHub credential in the keychain — run one git push first." >&2; exit 1; }
api() { curl -sS -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" "$@"; }

# Reuse an open PR for this head if one already exists.
EXISTING=$(api "$API/repos/$OWNER/$REPO/pulls?head=$OWNER:$HEAD&state=open")
URL=$(printf '%s' "$EXISTING" | python3 -c "import json,sys; prs=json.load(sys.stdin); print(prs[0]['html_url'] if prs else '')")
if [ -n "$URL" ]; then
  echo "Existing PR for $HEAD: $URL"
  exit 0
fi

[ -n "$BODY_FILE" ] || { echo "Pass the PR body as a file path, or - to read stdin." >&2; exit 1; }
if [ "$BODY_FILE" = "-" ]; then
  echo "Enter the PR body, then press Ctrl+D:" >&2
  BODY=$(cat)
else
  BODY=$(python3 - "$BODY_FILE" <<'PY'
import pathlib, sys
print(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"), end="")
PY
)
fi
[ -n "$BODY" ] || { echo "Empty PR body — refusing to open a blank PR." >&2; exit 1; }

PAYLOAD=$(python3 - "$HEAD" "$BASE" "$TITLE" "$BODY" <<'PY'
import json, sys
print(json.dumps({"head": sys.argv[1], "base": sys.argv[2], "title": sys.argv[3], "body": sys.argv[4]}))
PY
)

RESPONSE=$(printf '%s' "$PAYLOAD" | api -X POST "$API/repos/$OWNER/$REPO/pulls" -d @-)
URL=$(printf '%s' "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('html_url') or '')")
if [ -n "$URL" ]; then
  echo "Opened PR: $URL"
else
  printf '%s' "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print('Failed:', d.get('message'), d.get('errors', ''))" >&2
  exit 1
fi
