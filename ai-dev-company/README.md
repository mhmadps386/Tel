# AI Dev Company — Phase 1 (proof of concept)

A manager agent breaks a requirement into tasks, hands them to a **developer** agent and an
independent **QA** agent, tracks progress on a task board, and produces a run log and report.
The demo is disposable and runs only on this machine: nothing is deployed and nothing touches production.

The final report is [`reports/PHASE1_REPORT.md`](reports/PHASE1_REPORT.md).

```
ai-dev-company/
├── aidc                     # CLI wrapper: ./aidc <command>
├── orchestrator/aidc/       # board (state + run log), policy (safety), codex_runner, cli
├── orchestrator/tests/      # 19 unit/e2e tests (fake Codex binary, no network)
├── agents/                  # role prompts: manager.md, developer.md, qa.md
├── .codex/                  # native Codex multi-agent roles (developer, qa)
├── demo-app/                # disposable Node app: dashboard, task list, JSON API, node:test
├── runs/<run-id>/           # board.json, events.jsonl, plan.json, reports/, evidence/
├── docs/                    # architecture, owner setup, safety, Claude integration
└── reports/PHASE1_REPORT.md
```

## Quick start

```sh
./aidc preflight                                   # tool versions + auth MODE (never secrets)
./aidc init --goal "..." --run-id my-run
./aidc plan --run my-run --file plan.json          # manager decomposition (see runs/run-phase1-demo/plan.json)
./aidc status --run my-run

# Option A — Codex agents (needs the owner's ChatGPT sign-in; refuses API-key auth)
./aidc dispatch --run my-run --max-tasks 4

# Option B — any officially supported agent session drives the board by hand
./aidc worktree --run my-run --task dev-1
./aidc claim    --run my-run --task dev-1 --agent <name>
./aidc complete --run my-run --task dev-1 --agent <name> --result pass --summary "..." --report-file r.md

# Control
./aidc cancel  --run my-run --task qa-1 --reason "..."
./aidc halt    --run my-run --reason "..."     ;  ./aidc resume --run my-run --note "..."
./aidc recover --run my-run                     # re-queue tasks whose lease expired
./aidc metrics --run my-run
```

Tests: `cd orchestrator && python3 -m unittest discover -s tests` and `cd demo-app && npm test`.

Requires Python 3.10+, Node 20+, git. No third-party packages.

To move this into its own repository later: `git subtree split --prefix ai-dev-company -b ai-dev-company-only`
then push that branch to the new repo.
