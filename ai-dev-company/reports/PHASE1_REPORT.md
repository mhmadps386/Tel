# AI Dev Company — Phase 1 Final Report

Date: 2026-10-30 · Status: **Phase 1 complete with one open item (Codex sign-in), waiting for supervisor approval.**
Nothing was deployed. No paid API usage was enabled.

## 1. Acceptance criteria

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | Manager delegates tasks | Met | `runs/run-phase1-demo/plan.json`, `events.jsonl` (`task.planned`, `task.claimed` by two different agents) |
| 2 | Developer produces a working change | Met | commit `54ed2c9` on `aidc/run-phase1-demo/dev-1`; `evidence/dev-1.patch` (+241/−22, 4 files) |
| 3 | QA reviews independently | Met | separate agent, separate worktree, no access to the developer's report; `reports/qa-1.md` |
| 4 | Automated tests with recorded results | Met | demo app 24/24 (developer, QA and manager each ran it); orchestrator 19/19 (`evidence/`) |
| 5 | Changes isolated from production | Met | per-task worktrees on `aidc/*` branches; no deploy; app binds to 127.0.0.1 only |
| 6 | Reproducible run log and final report | Met | `events.jsonl`, `board.json`, this report; commands in §6 |
| 7 | No unauthorised API charges or deployments | Met | no API keys present; Codex never authenticated; Railway not used |

**Open item:** the live run used **Claude Code subagents**. The **Codex** runner could not run live,
because ChatGPT sign-in cannot be completed in this cloud container (see §4). The Codex path is
built and tested against a fake binary, and the live auth gate was exercised (`runs/run-codex-authgate`).

## 2. Architecture

```mermaid
flowchart LR
  U[User requirement] --> M[Manager agent<br/>plan · assign · track · accept]
  M -- aidc plan --> B[(Task board<br/>board.json + events.jsonl)]
  B -- ready task --> R{Runner}
  R -- "codex exec<br/>workspace-write, net off" --> D[Developer agent]
  R -- "codex exec<br/>read-only" --> Q[QA agent]
  R -. "manual claim/complete<br/>(Claude Code subagents)" .-> D
  R -. .-> Q
  D -- commit --> W1[[worktree<br/>aidc/run/dev-1]]
  W1 -- base for --> W2[[worktree<br/>aidc/run/qa-1]]
  Q -- reviews/tests --> W2
  D -- report --> B
  Q -- verdict --> B
  P[Policy guard<br/>subscription-only auth · sandbox allow-list<br/>timeouts · bounded retries · halt on usage limit] --- R
  B --> F[Final report + metrics]
```

- **Board** (`orchestrator/aidc/board.py`): tasks with roles, dependencies, attempts/`max_attempts` (≤5),
  `timeout_s` (≤4h), leases, `fail`/retry, `cancel` (cascades to dependants), `halt`/`resume`,
  `recover` (expired leases), and an append-only JSONL run log. It is protected by a file lock and written atomically.
- **Policy** (`policy.py`): worktrees only under `.aidc-worktrees/` on new `aidc/<run>/<task>` branches; path
  confinement; sandbox allow-list (`read-only`, `workspace-write`); `codex login status` mode check.
- **Codex runner** (`codex_runner.py`): `codex exec --sandbox … -c approval_policy="never" --json -o …`.
  It removes `OPENAI_API_KEY`/`CODEX_API_KEY` from the child environment, kills the process group on timeout,
  and halts the run on a usage-limit message.
- **Native Codex multi-agent**: `.codex/config.toml` defines `[agents.developer]` and `[agents.qa]`, with
  `max_threads=2`, `max_depth=1` and `job_max_runtime_seconds=1800`. Codex 0.166.0 accepts it under
  `--strict-config` (a deliberately unknown key was rejected, which shows the keys are really validated).

## 3. Repository and branches

| Item | Value |
|------|-------|
| Repository | `mhmadps386/Tel`, folder `ai-dev-company/` |
| Working branch | `claude/ai-dev-company-phase-1-2y0h5h` (non-production; pushed) |
| Developer branch | `aidc/run-phase1-demo/dev-1` → `54ed2c9` (local only; fast-forwarded into the working branch after QA PASS) |
| QA branch | `aidc/run-phase1-demo/qa-1` (read-only review checkout, no commits) |
| `main` | untouched |

**Deviation:** I could not create a new `ai-dev-company` repository. The GitHub integration available to
this session returned `403 Resource not accessible by integration`. The folder is self-contained.
To create the repo: create an empty private `ai-dev-company` repo on GitHub, then
`git subtree split --prefix ai-dev-company -b aidc-only && git push <new-repo-url> aidc-only:main`.

## 4. Tools, versions and authentication

| Tool | Version | Auth mode |
|------|---------|-----------|
| Codex CLI (`@openai/codex`, pinned, project-local install) | 0.166.0 | **Not signed in.** `multi_agent` feature: stable, enabled |
| Claude Code | 2.1.314 | The account's own Claude Code cloud session (official product). No `ANTHROPIC_API_KEY` |
| Node.js | 22.22.0 | — |
| Python | 3.13.17 | — |
| git | 2.43.0 | — |

Codex sign-in: this container's network policy returns **HTTP 403 for `chatgpt.com` and `auth.openai.com`**,
so neither browser nor device-code ChatGPT login can complete here. Only `api.openai.com` is reachable,
and that would mean API-key billing, which Phase 1 forbids. `aidc dispatch` therefore refused to run
(`runs/run-codex-authgate`, exit 2, zero attempts). The owner should sign in on a trusted machine of
their own; see `docs/OWNER_SETUP.md`. No credentials were requested, seen or stored.

## 5. Agent workflow evidence (`runs/run-phase1-demo/events.jsonl`)

```
14:02:39 run.created / manager.plan_notes / task.planned dev-1 / task.planned qa-1 (depends_on dev-1)
14:02:39 workspace.created dev-1  → .aidc-worktrees/run-phase1-demo/dev-1  (branch aidc/run-phase1-demo/dev-1)
14:02:56 task.claimed   dev-1 by claude-developer (attempt 1/2)
14:04:05 task.completed dev-1 result=pass 69.5s   → reports/dev-1.md
14:04:21 workspace.created qa-1 (base = dev-1 commit)
14:04:26 manager.note   verified dev commit is isolated; QA gets no developer context
14:04:45 task.claimed   qa-1 by claude-qa (attempt 1/2)
14:06:02 task.completed qa-1 result=pass 76.9s    → reports/qa-1.md
14:06:40 manager.accepted / manager.incident
```

The feature delegated was **task priorities (low/medium/high, validated), `status`/`priority` list filters,
`GET /api/stats`, and dashboard wiring**. The developer also made `PATCH` validate every field before
changing any (previously, a rejected PATCH could still have saved its title).

QA findings (all low severity, none blocking):
1. Repeated query params use the first value only (`?priority=high&priority=bogus` → 200). The spec says nothing on this.
2. A JSON `null` body returns 500 instead of 400 (this predates the change).
3. Unknown filter *keys* are ignored. This fits the spec.
4. The dashboard has no UI error message when adding a task fails (this predates the change).

**Incident (logged):** while probing, the QA agent wrote one stray file outside its scratch area
(`/home/user/api.test.js`, outside the repo). It reported this itself and deleted the file, and the manager
verified both worktrees are clean. Cause: Claude Code subagents in this session share the host filesystem
and are bound by instructions, not an OS sandbox. The Codex runner path closes this gap with Codex's
OS sandbox (read-only for QA).

## 6. Test results

| Suite | Who ran it | Result |
|-------|------------|--------|
| demo-app `npm test` (dev-1 commit) | developer | 24 tests, 24 pass, 0 fail |
| demo-app `npm test` + baseline `api.test.js` against new code | QA | 24/24; regression check 7/7 |
| demo-app `npm test` | manager re-run | 24/24, exit 0 (`evidence/manager-npm-test-dev-1.txt`) |
| orchestrator `unittest` (19 tests) | manager | OK (`evidence/orchestrator-unittest.txt`) |

The orchestrator tests cover dependency gating, owner-only completion, bounded retries, cascading
cancellation, halt/resume, lease recovery, refusing API-key or no auth, halting on a usage limit with no
retry, killing an agent on timeout, crash-then-retry, removing API keys from the agent environment, and
the ban on `danger-full-access` and bypass flags.

To reproduce: `cd ai-dev-company/demo-app && npm test`, `cd ai-dev-company/orchestrator && python3 -m unittest discover -s tests`,
`./aidc status --run run-phase1-demo`, `./aidc metrics --run run-phase1-demo`.

## 7. Usage and cost

| Resource | Usage | Cost |
|----------|-------|------|
| Tasks / attempts / failures | 2 tasks, 2 attempts, 0 failed attempts | — |
| Agent time | 146.4 s on the board (dev 69.5 s, QA 76.9 s) | — |
| Claude Code (subagents) | developer ≈84k tokens, QA ≈91k tokens (as reported by Claude Code), plus the manager session | Counts against the account's Claude plan. No API key, no pay-as-you-go |
| Codex / ChatGPT | 0 tasks. One unauthenticated request made while validating the config got `401`, with no account behind it | $0 |
| OpenAI / Anthropic API | none (`orchestrator_api_calls: 0`, no keys present) | $0 |
| Railway | not used | $0 |
| GitHub | existing repo, one branch | $0 |

## 8. Problems and limitations

- **No live Codex run yet.** This is blocked by the container's network policy and the need for the owner to sign in themselves.
- **Separate repo not created.** The integration got a 403 (see §3).
- **Claude subagents are instruction-bound, not OS-sandboxed.** One out-of-scope write happened and was self-reported (§5).
- **Usage limits are detected by text.** The orchestrator matches Codex's error text because there is no
  stable machine-readable quota API. It halts on a match; it cannot show remaining quota in advance.
- **Single-machine board.** A file lock is fine for one host; it is not a distributed queue.
- **Unrelated finding in this repo:** `newfile.py` (already in the repo before this work) contains a
  hard-coded Telegram bot token. I did not modify it, because modifying existing user projects is out of scope.
  I recommend revoking that token with @BotFather and moving it to an environment variable.

## 9. Recommendation for Phase 2

1. **Owner signs in to Codex on a trusted machine** (a personal workstation, or a small private VM the owner controls),
   then runs the same plan with `./aidc dispatch` to get a live Codex developer→QA run. Compare it with this Claude run.
2. **Use OS sandboxing for every agent.** Prefer Codex's sandbox. For Claude Code subagents, use Claude Code's
   sandbox/permission settings or a per-agent container.
3. **Add a usage ledger.** Record per-task tokens and time from Codex `--json` events and Claude Code session
   data, and set a daily task cap per subscription.
4. **Add a review gate before merge.** Open a PR from the `aidc/*` branch so that a human approves it.
   There should still be no auto-merge and no deploy.
5. **Add a minimal read-only status page** over `board.json`/`events.jsonl`, only after approval, with no public exposure.
6. **Claude API runner**, only if the supervisor approves a budget (`docs/CLAUDE_INTEGRATION.md`).

Phase 1 stops here, waiting for supervisor approval.
