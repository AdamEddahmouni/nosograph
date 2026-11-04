#!/usr/bin/env bash
# Open or update the tracking issue for a failed reference identifier audit.
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${GH_REPO:?GH_REPO is required}"
: "${RUN_URL:?RUN_URL is required}"

title="[automated] Reference identifier audit failed"
search="Reference identifier audit failed in:title"

existing="$(
  gh issue list \
    --repo "$GH_REPO" \
    --state open \
    --search "$search" \
    --limit 100 \
    --json number,title \
  | python -c 'import json, sys; title = sys.argv[1]; numbers = [item["number"] for item in json.load(sys.stdin) if item.get("title") == title]; print(numbers[0] if numbers else "")' "$title"
)"

body="$(cat <<EOF
The weekly reference identifier audit failed.

- Run: ${RUN_URL}
- Ref: ${REF_NAME:-unknown}
- Commit: ${SHA:-unknown}

Download the \`reference-identifier-audit\` artifact, inspect the dead or errored identifier, and fix or replace it before the next weekly run.
EOF
)"

if [[ -n "$existing" ]]; then
  gh issue comment "$existing" --repo "$GH_REPO" --body "$body"
  echo "Updated reference audit issue #${existing}"
else
  gh issue create --repo "$GH_REPO" --title "$title" --body "$body"
fi
