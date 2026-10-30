#!/usr/bin/env bash
# Owner-only: install the pinned Codex CLI and sign in with a ChatGPT subscription.
#
# Run this yourself, in a terminal on a machine you control. This script never
# reads, prints, copies or uploads credentials: sign-in happens between you,
# your browser and OpenAI. Codex stores its credentials in $CODEX_HOME (default
# ~/.codex), outside this repository.
#
#   scripts/owner-codex-setup.sh            # browser sign-in
#   scripts/owner-codex-setup.sh --device   # headless: shows a URL + one-time code
set -euo pipefail

CODEX_VERSION="0.166.0"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/.tools"
CODEX="$TOOLS/node_modules/.bin/codex"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export CODEX_HOME

say() { printf '\n== %s\n' "$*"; }

say "1/5 Install @openai/codex@$CODEX_VERSION into $TOOLS (project-local, pinned)"
mkdir -p "$TOOLS"
if [ "$("$CODEX" --version 2>/dev/null || true)" != "codex-cli $CODEX_VERSION" ]; then
  npm install --no-fund --no-audit --prefix "$TOOLS" "@openai/codex@$CODEX_VERSION"
fi
"$CODEX" --version

say "2/5 Lock Codex to ChatGPT sign-in (forced_login_method = \"chatgpt\")"
mkdir -p "$CODEX_HOME"
touch "$CODEX_HOME/config.toml"
if grep -qE '^\s*forced_login_method\s*=' "$CODEX_HOME/config.toml"; then
  if ! grep -qE '^\s*forced_login_method\s*=\s*"chatgpt"' "$CODEX_HOME/config.toml"; then
    echo "ERROR: $CODEX_HOME/config.toml sets a different forced_login_method; fix it by hand." >&2
    exit 1
  fi
else
  # Root-level key: insert before the first [table] header so it is not swallowed by a table.
  python3 - "$CODEX_HOME/config.toml" <<'PY'
import sys
p = sys.argv[1]
lines = open(p).read().splitlines(keepends=True)
i = next((n for n, l in enumerate(lines) if l.lstrip().startswith("[")), len(lines))
lines.insert(i, 'forced_login_method = "chatgpt"  # aidc: never fall back to API-key billing\n')
open(p, "w").writelines(lines)
PY
fi
grep -E '^\s*forced_login_method' "$CODEX_HOME/config.toml"

say "3/5 Refuse to continue if an OpenAI API key is in the environment"
for v in OPENAI_API_KEY CODEX_API_KEY; do
  if [ -n "${!v:-}" ]; then
    echo "ERROR: $v is set. Unset it first (aidc never uses API keys in Phase 1)." >&2
    exit 1
  fi
done
echo "ok: no API key variables set"

say "4/5 Sign in with ChatGPT (you complete this step; nothing is captured)"
if "$CODEX" login status 2>&1 | grep -qi "chatgpt"; then
  echo "already signed in with ChatGPT"
elif [ "${1:-}" = "--device" ]; then
  "$CODEX" login --device-auth
else
  "$CODEX" login
fi

say "5/5 Verify"
STATUS="$("$CODEX" login status 2>&1 || true)"
if ! printf '%s' "$STATUS" | grep -qi "chatgpt"; then
  echo "ERROR: Codex is not signed in with ChatGPT (status: $(printf '%s' "$STATUS" | head -1))." >&2
  exit 1
fi
echo "ok: Codex auth mode = ChatGPT subscription"
PATH="$TOOLS/node_modules/.bin:$PATH" "$ROOT/aidc" preflight
echo
echo "Next: scripts/codex-e2e.sh   (real manager -> developer -> QA -> manager review run)"
