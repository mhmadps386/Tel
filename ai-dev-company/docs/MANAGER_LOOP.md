# Proposed continuous manager loop (design only, NOT enabled)

Status: proposal for supervisor review. No code in this repository runs this loop unattended.
`aidc dispatch` still processes one run per explicit command and stops when the run is drained,
halted or `--max-tasks` is reached.

## Inputs

**Owner-approved backlog** (`backlog.json`, committed and changed only by PR with owner approval):

```json
{
  "approved_by": "mhmadps386",
  "approved_at": "2026-11-01",
  "budget": {"max_rounds": 5, "max_tasks_per_round": 4, "max_agent_minutes_per_day": 120},
  "items": [
    {
      "id": "B-001",
      "priority": 1,
      "title": "Due dates and overdue count",
      "spec": "...",
      "acceptance": {
        "test_cmd": "npm test", "test_dir": "ai-dev-company/demo-app",
        "must_add_tests": true,
        "max_files_changed": 8,
        "paths_allowed": ["ai-dev-company/demo-app/"]
      },
      "depends_on": [],
      "risk": "low",
      "status": "approved"
    }
  ]
}
```

Only items with `"status": "approved"` are eligible. The loop never edits `approved_by`, `budget`,
`acceptance` or `status: approved`; only the owner does.

## One round

```
1. PRE-CHECKS         stop conditions (below); `aidc preflight` must show chatgpt auth, forced_login_method=chatgpt,
                      os_sandbox_available=true; no unresolved isolation_violation in any run
2. SELECT             highest-priority approved item whose depends_on items are all "accepted"
                      and that has not failed 2 rounds in a row; nothing eligible -> stop (DONE)
3. PLAN               manager writes plan.json: dev task (+ fix task if this is a retry) and a QA task depending on it
4. GATE A (approval)  plan is shown to the owner; continue only on explicit approval
                      (Phase 2: auto-approve allowed only for risk=low items, if the supervisor enables it)
5. DISPATCH           aidc dispatch --max-tasks <budget>; Codex developer (workspace-write) then Codex QA (read-only)
6. REVIEW             aidc review: objective checks (below); writes manager.accepted / manager.rejected
7. DECIDE             accepted   -> item "accepted"; open a PR from the aidc/* branch (never auto-merged)
                      rejected   -> if QA/test findings are specific and rounds remain: next round creates a
                                    fix task with the QA report attached; else item "needs_owner"
8. GATE B (approval)  merging the PR is always a human action
9. RECORD             append round summary to loop-log.jsonl: item, run id, verdicts, tests, minutes, failures
```

## Objective completion criteria (all must hold for "accepted")

| Check | Source |
|---|---|
| Developer task `done` with `result=pass` | board |
| At least one QA task, different agent, `done` with `result=pass` | board |
| Manager re-run of `acceptance.test_cmd` in the OS sandbox exits 0 | `aidc review` evidence file |
| Test count did not decrease vs. base branch, and new tests were added if `must_add_tests` | test output diff |
| Changed files ⊆ `paths_allowed` and count ≤ `max_files_changed` | `git diff --name-only base..branch` |
| No secret-scan hits in the diff | `scripts/scan-secrets.sh` on the branch |
| No isolation violation, no halt during the run | events.jsonl |

`aidc review` implements the first three today. The rest are listed for Phase 2.

## Bounds and stop conditions

- **Maximum rounds:** `budget.max_rounds` (default 5), counted per loop session; each item gets at most
  2 consecutive rejected rounds, then becomes `needs_owner`.
- **Per-task limits:** existing `timeout_s` (≤ 4 h) and `max_attempts` (≤ 5) on the board.
- **Stop immediately (no further rounds) when:**
  - Codex reports a subscription usage limit (`subscription_usage_limit` halt). Never switch to API billing;
  - auth mode is not `chatgpt` or `forced_login_method` is missing;
  - any `isolation_violation`;
  - `max_agent_minutes_per_day` is reached (summed `agent_seconds`);
  - 2 consecutive rounds with infrastructure failures (agent crash or timeout, not a QA rejection);
  - the backlog has no eligible item (normal completion);
  - the owner runs `aidc halt` or adds a `STOP` file in the run root.
- **Never, at any point:** deploy, merge, push to `main`, touch paths outside `paths_allowed`, edit the
  backlog's approval fields, or raise its own budget.

## Approval gates

| Gate | Default in Phase 2 |
|---|---|
| Backlog item approval | owner, by PR to `backlog.json` |
| Plan approval before dispatch (Gate A) | owner, each round (optional auto for `risk: low` once trusted) |
| Merge (Gate B) | owner, always |
| Resume after any halt | owner (`aidc resume --note`) |
| Budget changes | owner |

## Enabling (later, needs supervisor approval)

It would be a new `aidc loop --backlog backlog.json --interactive` command that defaults to interactive
gates. Scheduled or unattended operation would be a separate, explicit decision after a period of
supervised loops with zero isolation violations.
