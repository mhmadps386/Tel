#!/usr/bin/env bash
# Real end-to-end run with Codex agents (no mocks): manager plan -> Codex developer
# -> independent Codex QA -> manager review (tests re-run in the OS sandbox).
#
# Uses the owner's ChatGPT subscription quota (about 2 Codex tasks). It refuses to
# start unless Codex reports ChatGPT sign-in, and halts on any usage-limit message.
#
#   scripts/codex-e2e.sh [run-id]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$ROOT/.tools/node_modules/.bin:$PATH"
RUN="${1:-run-codex-e2e-$(date -u +%Y%m%d-%H%M%S)}"
AIDC="$ROOT/aidc"

command -v codex >/dev/null || { echo "Codex not installed: run scripts/owner-codex-setup.sh" >&2; exit 1; }
codex login status 2>&1 | grep -qi chatgpt || { echo "Codex is not signed in with ChatGPT: run scripts/owner-codex-setup.sh" >&2; exit 1; }
for v in OPENAI_API_KEY CODEX_API_KEY; do [ -z "${!v:-}" ] || { echo "$v is set; unset it" >&2; exit 1; }; done

# The run's plan reuses the Phase 1 feature spec, re-targeted at a different, small feature
# so Codex starts from the current code.
PLAN="$(mktemp)"
cat > "$PLAN" <<'JSON'
{
  "notes": "Phase 1.5 real-Codex validation run. One developer task, one independent QA task depending on it.",
  "tasks": [
    {"id": "dev-1", "role": "developer", "title": "Due dates and overdue count", "timeout_s": 1800, "max_attempts": 2,
     "spec": "In ai-dev-company/demo-app: (1) tasks accept an optional `dueDate` string in YYYY-MM-DD format on POST and PATCH; any other format or an impossible date (e.g. 2026-02-30) returns 400; `null` clears it on PATCH. (2) GET /api/stats gains an integer `overdue`: open tasks whose dueDate is before today's date (UTC). (3) The dashboard shows the due date per task and an Overdue card. (4) node:test coverage for every rule; all existing tests keep passing (`npm test`)."},
    {"id": "qa-1", "role": "qa", "title": "Independent QA of dev-1", "depends_on": ["dev-1"], "timeout_s": 1200, "max_attempts": 2,
     "spec": "Review the dev-1 change (optional dueDate with strict YYYY-MM-DD validation incl. impossible dates, null clears on PATCH, stats.overdue counts only open past-due tasks in UTC, dashboard wiring, tests). Run `npm test` in ai-dev-company/demo-app and record exact counts. Report bugs with file:line and severity."}
  ]
}
JSON

"$AIDC" preflight
"$AIDC" init --goal "Phase 1.5 real Codex workflow validation" --run-id "$RUN"
"$AIDC" plan --run "$RUN" --file "$PLAN"
cp "$PLAN" "$ROOT/runs/$RUN/plan.json"
set +e
"$AIDC" dispatch --run "$RUN" --max-tasks 4
DISPATCH=$?
"$AIDC" review --run "$RUN" --task dev-1
REVIEW=$?
set -e
"$AIDC" status --run "$RUN"
"$AIDC" metrics --run "$RUN"
echo "dispatch exit=$DISPATCH review exit=$REVIEW  (evidence: runs/$RUN/)"
[ "$DISPATCH" = 0 ] && [ "$REVIEW" = 0 ]
