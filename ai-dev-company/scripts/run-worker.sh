#!/usr/bin/env bash
# Start the AI Dev Company execution worker on a host YOU control (Linux with
# unprivileged user namespaces: Ubuntu/Debian desktop or VM, WSL2 Ubuntu, or a
# Linux VM on macOS). The worker connects out to the private panel over HTTPS;
# no inbound ports are opened. Agents run only inside OS sandboxes on this host.
#
#   AIDC_SERVER_URL=https://<panel> scripts/run-worker.sh
#
# The worker token is read from ~/.aidc-worker/token (create it in the panel:
# Execution workers -> Create worker token; paste it into that file, chmod 600).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${AIDC_DATA_DIR:-$HOME/.aidc-worker}"
CODEX_VERSION="0.166.0"
mkdir -p "$DATA" && chmod 700 "$DATA"

: "${AIDC_SERVER_URL:?set AIDC_SERVER_URL to the panel https URL}"
[ -f "$DATA/token" ] || { echo "Put the worker token from the panel in $DATA/token (chmod 600)." >&2; exit 1; }
[ "$(stat -c %a "$DATA/token")" = "600" ] || { echo "$DATA/token must be chmod 600" >&2; exit 1; }
for v in OPENAI_API_KEY CODEX_API_KEY; do [ -z "${!v:-}" ] || { echo "$v is set; unset it (no API billing)." >&2; exit 1; }; done

command -v bwrap >/dev/null || echo "note: no system bwrap; the Codex-bundled bubblewrap will be used"
unshare -Ur true 2>/dev/null || { echo "This host blocks user namespaces: agents cannot be sandboxed here." >&2; exit 1; }

if [ "$("$ROOT/.tools/node_modules/.bin/codex" --version 2>/dev/null || true)" != "codex-cli $CODEX_VERSION" ]; then
  npm install --no-fund --no-audit --prefix "$ROOT/.tools" "@openai/codex@$CODEX_VERSION"
fi

echo "Running sandbox tests first (they must pass with no skips)..."
"$ROOT/scripts/run-tests.sh" "$DATA/last-test-evidence" >/dev/null || {
  echo "Sandbox/orchestrator tests failed; refusing to start. See $DATA/last-test-evidence" >&2; exit 1; }

export AIDC_DATA_DIR="$DATA" AIDC_WORKER_TOKEN="$(cat "$DATA/token")"
export AIDC_WORKER_ID="${AIDC_WORKER_ID:-$(hostname)}"
exec python3 "$ROOT/worker/main.py"
