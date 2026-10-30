#!/usr/bin/env bash
# Look for credential-shaped strings in the working tree and the full git history.
# Matches are reported by location only; the secret values are never printed.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
PATTERNS=(
  'telegram-bot-token:[0-9]{8,10}:[A-Za-z0-9_-]{35}'
  'openai-key:sk-[A-Za-z0-9_-]{20,}'
  'anthropic-key:sk-ant-[A-Za-z0-9_-]{20,}'
  'github-token:gh[pousr]_[A-Za-z0-9]{36}'
  'aws-access-key:AKIA[0-9A-Z]{16}'
  'private-key:-----BEGIN [A-Z ]*PRIVATE KEY-----'
)
found=0
for entry in "${PATTERNS[@]}"; do
  name="${entry%%:*}"; re="${entry#*:}"
  tree=$(git grep -lE -- "$re" -- . ':!*.aidc-worktrees/*' ':!*/.tools/*' 2>/dev/null | tr '\n' ' ')
  hist=$(git log --all --format='%h(%ad)' --date=short -G "$re" 2>/dev/null | tr '\n' ' ')
  if [ -n "$tree$hist" ]; then
    found=1
    echo "$name: working-tree files=[${tree% }] history commits=[${hist% }]"
  fi
done
[ $found = 0 ] && echo "no credential-shaped strings found"
exit $found
