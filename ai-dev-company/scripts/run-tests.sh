#!/usr/bin/env bash
# Run every automated test and save the raw output as evidence.
#   scripts/run-tests.sh [evidence-dir]
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/runs/test-evidence}"
mkdir -p "$OUT"
export PATH="$ROOT/.tools/node_modules/.bin:$PATH"
{ echo "date: $(date -u +%FT%TZ)"; uname -sr; python3 --version; node --version; codex --version 2>/dev/null || echo "codex: not installed"; } > "$OUT/environment.txt"
(cd "$ROOT/orchestrator" && python3 -m unittest discover -s tests -v) > "$OUT/orchestrator-tests.txt" 2>&1
ORCH=$?
# Security tests must not pass by being skipped (e.g. bubblewrap unavailable).
if grep -q "skipped" "$OUT/orchestrator-tests.txt" && [ -z "${AIDC_ALLOW_SKIPS:-}" ]; then
  echo "FAIL: some tests were skipped (set AIDC_ALLOW_SKIPS=1 to accept)" | tee -a "$OUT/orchestrator-tests.txt"
  ORCH=1
fi
(cd "$ROOT/demo-app" && npm test) > "$OUT/demo-app-tests.txt" 2>&1
DEMO=$?
# Control panel + worker end-to-end (needs a Postgres where test databases can be created).
E2E=0
if [ -n "${AIDC_TEST_DATABASE_URL:-}" ]; then
  (cd "$ROOT" && python3 -m unittest server.tests.test_e2e -v) > "$OUT/control-plane-e2e.txt" 2>&1
  E2E=$?
  if grep -q "skipped" "$OUT/control-plane-e2e.txt"; then E2E=1; fi
else
  echo "control-plane e2e NOT RUN (AIDC_TEST_DATABASE_URL unset)" > "$OUT/control-plane-e2e.txt"
  [ -n "${AIDC_ALLOW_SKIPS:-}" ] || E2E=1
fi
echo "orchestrator exit=$ORCH; demo-app exit=$DEMO; control-plane-e2e exit=$E2E" | tee "$OUT/summary.txt"
tail -3 "$OUT/orchestrator-tests.txt" | tee -a "$OUT/summary.txt"
grep -E '^# (tests|pass|fail)' "$OUT/demo-app-tests.txt" | tee -a "$OUT/summary.txt"
tail -3 "$OUT/control-plane-e2e.txt" | tee -a "$OUT/summary.txt"
[ $ORCH = 0 ] && [ $DEMO = 0 ] && [ $E2E = 0 ]
