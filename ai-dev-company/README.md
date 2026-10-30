# AI Dev Company — Phase 1.6 (private staging)

A manager agent breaks a requirement into tasks, hands them to a **developer** agent and an
independent **QA** agent, tracks progress on a task board, and produces a run log and report.
The demo is disposable and runs only on this machine: nothing is deployed and nothing touches production.

Reports: [Phase 1](reports/PHASE1_REPORT.md), [Phase 1.5](reports/PHASE1_5_REPORT.md), [Phase 1.6](reports/PHASE1_6_REPORT.md).
Private staging panel (Railway): https://aidc-web-staging.up.railway.app (owner login required).
Connect an execution worker + Codex device sign-in: [`docs/WORKER_SETUP.md`](docs/WORKER_SETUP.md).

Phase 1.6 layout: `server/` = control panel + AI Manager state machine (Railway, Postgres);
`worker/` = execution worker (owner-controlled Linux host; agents run only here, in OS sandboxes);
`deploy/` = Dockerfiles (web, sandbox probe).

```
ai-dev-company/
├── aidc                     # CLI wrapper: ./aidc <command>
├── orchestrator/aidc/       # board (state + run log), policy, sandbox (OS isolation), codex_runner, cli
├── orchestrator/tests/      # 45 tests: board, dispatch, process-level integration, sandbox negative tests
├── scripts/                 # owner-codex-setup, codex-e2e (real run), run-tests, scan-secrets
├── agents/                  # role prompts: manager.md, developer.md, qa.md
├── .codex/                  # native Codex multi-agent roles (developer, qa)
├── demo-app/                # disposable Node app: dashboard, task list, JSON API, node:test
├── runs/<run-id>/           # board.json, events.jsonl, plan.json, reports/, evidence/
├── docs/                    # OWNER_SETUP, ISOLATION, SECURITY_FINDINGS, GITHUB_403, MANAGER_LOOP, CLAUDE_INTEGRATION
└── reports/                 # PHASE1_REPORT.md, PHASE1_5_REPORT.md
```

## Quick start

```sh
./aidc preflight                                   # tool versions + auth MODE (never secrets)
./aidc init --goal "..." --run-id my-run
./aidc plan --run my-run --file plan.json          # manager decomposition (see runs/run-phase1-demo/plan.json)
./aidc status --run my-run

# Option A — Codex agents (needs the owner's ChatGPT sign-in; refuses API-key auth)
./aidc dispatch --run my-run --max-tasks 4

./aidc review   --run my-run --task dev-1       # manager acceptance gate (tests re-run in the OS sandbox)

# Option B — a hand-driven agent session (NOT OS-sandboxed; write tasks need an explicit ack)
./aidc worktree --run my-run --task dev-1
./aidc claim    --run my-run --task dev-1 --agent <name> --unsandboxed-ack
./aidc complete --run my-run --task dev-1 --agent <name> --result pass --summary "..." --report-file r.md

# Control
./aidc cancel  --run my-run --task qa-1 --reason "..."
./aidc halt    --run my-run --reason "..."     ;  ./aidc resume --run my-run --note "..."
./aidc recover --run my-run                     # re-queue tasks whose lease expired
./aidc metrics --run my-run
```

Tests: `scripts/run-tests.sh` (orchestrator + demo app; fails if any security test is skipped).
Run a command in the OS sandbox: `./aidc sandbox-exec --workdir demo-app -- npm test`.

Requires Python 3.10+, Node 20+, git. No third-party packages.

To move this into its own repository later: `git subtree split --prefix ai-dev-company -b ai-dev-company-only`
then push that branch to the new repo.
