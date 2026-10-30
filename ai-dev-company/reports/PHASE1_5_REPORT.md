# AI Dev Company — Phase 1.5 Report: Validation & Security

Date: 2026-10-30 · Branch: `claude/ai-dev-company-phase-1-2y0h5h` · Status: **Phase 1.5 work is complete, but the
real Codex run is blocked on owner sign-in.** Phase 2 was not started. Nothing was deployed, no paid API was activated,
and `main` is unchanged.

## Summary by priority

| # | Priority | Status | Evidence |
|---|----------|--------|----------|
| 1 | Telegram token | **Removed from code.** Still in history of public `main` (`62901f1`). **Owner must revoke it in BotFather now** | `docs/SECURITY_FINDINGS.md`, `evidence/secret-scan.txt` |
| 2 | OS-level isolation + negative test | **Done.** Kernel-enforced sandboxes; 16 negative tests (13 `aidc` sandbox + 2 Codex sandbox + 1 escape-canary integration) | `docs/ISOLATION.md`, `orchestrator/tests/test_sandbox.py` |
| 3 | Codex ChatGPT auth workflow | **Done (procedure).** Official `codex login` with `forced_login_method="chatgpt"`; API-key login is refused by Codex itself | `scripts/owner-codex-setup.sh`, `docs/OWNER_SETUP.md` |
| 4 | Real Codex manager→dev→QA→review run | **Blocked**: this container returns 403 for `auth.openai.com` and `chatgpt.com`. Script ready: `scripts/codex-e2e.sh` | `evidence/codex-auth-status.txt`, `evidence/codex-e2e-attempt.txt` |
| 5 | Timeout / cancel / retry / resume / recovery / stop integration tests | **Done.** 11 process-level tests | `orchestrator/tests/test_integration.py` |
| 6 | GitHub 403 diagnosis | **Done.** Missing *Administration: write* on the Claude GitHub App; least-privilege fix = owner creates repo + grants App that one repo | `docs/GITHUB_403.md` |
| 7 | Continuous manager loop design | **Done (design only, not enabled)** | `docs/MANAGER_LOOP.md` |

Evidence paths are relative to `ai-dev-company/runs/phase1_5/`.

## 1. Security findings

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| F1 | **Critical** | Telegram bot token hard-coded in `newfile.py`. The repo is **public** (GitHub API: `"visibility": "public"`). Exposed since 2025-01-03 in commit `62901f1` on `main` | Code now reads `TELEGRAM_BOT_TOKEN` from the environment. **Revocation pending (owner)**. History rewrite would need a force-push to `main`; not done without approval |
| F2 | High | Phase 1 agent isolation was instruction-only (QA wrote `/home/user/api.test.js`) | Fixed: OS-enforced, with a regression test on that exact path |
| F3 | Medium | Codex `workspace-write` allows `/tmp` and `$TMPDIR` by default, which are shared with the host | Fixed: `exclude_slash_tmp` and `exclude_tmpdir_env_var` forced; Codex now reports `workspace-write [workdir]`; tested |
| F4 | Medium | Possible paid-billing fallback | Closed: `forced_login_method="chatgpt"` makes Codex refuse API-key login. `aidc` refuses API-key mode and strips key variables. A fake `OPENAI_API_KEY` was not sent (401 "Missing bearer") |

The token value was never printed, logged or sent anywhere. All scans mask it. I chose not to call GitHub's
secret-scanning API, because that would transmit the value.

**Owner action (≈2 min):** Telegram → @BotFather → `/mybots` → your bot → **API Token** → **Revoke current token**.
Store the new token only as the `TELEGRAM_BOT_TOKEN` environment variable (e.g. Railway → Variables), never
in a file in the repo. Full steps are in `docs/SECURITY_FINDINGS.md`.

## 2. Isolation design (what is enforced, by whom)

- **Codex agents:** every model-issued command runs in Codex's official Linux sandbox (bubblewrap/seccomp).
  Developers get write access to their worktree only; QA is read-only; network is off; `/tmp` is excluded;
  approvals are never auto-granted (`approval_policy="never"` refuses escalations).
- **`aidc` sandbox (bubblewrap)** for manager verification (`aidc review`) and any hand-run command
  (`aidc sandbox-exec`): the filesystem is read-only except the workdir. `$HOME`, `/root` and the repo are
  hidden behind read-only empty overlays. It has private `/tmp`, new user/pid/net/ipc/uts namespaces, runs as
  uid 1000, has a cleared environment, dies with its parent, has rlimits, and fails closed if bubblewrap is unavailable.
- **Orchestrator guards:** a git-status canary on the manager checkout halts the run with
  `isolation_violation`; agents get `PDEATHSIG`, so a crashed orchestrator leaves no orphans.
- **Hand-driven agents** (the Phase 1 Claude subagents) cannot be sandboxed by `aidc`. Developer claims
  now require `--unsandboxed-ack` and are logged as `policy.unsandboxed_claim`.

Live demonstration with the real CLI (`evidence/sandbox-cli-demo.txt`):

```
$ ./aidc sandbox-exec --workdir demo-app -- sh -c "cp test/api.test.js /home/user/api.test.js; echo x > ../README.md; id -u; ls -A ~"
cp: cannot create regular file '/home/user/api.test.js': Read-only file system
sh: 1: cannot create ../README.md: Read-only file system
1000
host check: /home/user/api.test.js exists? no; README.md modified? no
```

Writing the negative tests turned up four problems, all now fixed:

- **Fixtures under `/tmp` gave false results.** The sandbox's private `/tmp` shadowed the fixtures, so the
  tests were not testing what they claimed. No real escape happened: the host files were untouched.
- **Silent writes into hidden paths.** Writes into the empty overlays that hide paths "succeeded" without
  error. The overlays are now read-only.
- **A bad availability probe.** It used `/` as the workdir, so 12 security tests were silently skipped.
  The probe is fixed, `/` and `$HOME` are now refused as workdirs, and `run-tests.sh` fails on any skip.
- **Codex's default `/tmp` write access** (finding F3).

## 3. Test evidence (exact)

`scripts/run-tests.sh` → `runs/phase1_5/evidence/` (2026-10-30T14:28Z, Linux 6.18, Python 3.13.17, Node 22.22.0, codex-cli 0.166.0):

| Suite | Tests | Result |
|-------|-------|--------|
| `test_board.BoardTest` | 8 | OK |
| `test_dispatch.DispatchTest` (fake Codex, in-process) | 7 | OK |
| `test_dispatch.PolicyTest` | 4 | OK |
| `test_integration.IntegrationTest` (separate dispatcher process, real child processes) | 11 | OK |
| `test_sandbox.SandboxTest` (real bubblewrap, nothing mocked) | 13 | OK |
| `test_sandbox.CodexSandboxTest` (real `codex sandbox` with the runner's config) | 2 | OK |
| **Orchestrator total** | **45** | **`Ran 45 tests in 26.445s — OK`, 0 skipped** |
| demo-app `npm test` (host) | 24 | 24 pass, 0 fail |
| demo-app `npm test` inside `aidc sandbox-exec` (no network, read-only host) | 24 | 24 pass, 0 fail |

Integration coverage for priority 5:

| Behaviour | Test | What is asserted |
|-----------|------|------------------|
| Timeout | `test_timeout_kills_whole_process_tree` | 2 s timeout; the agent **and its grandchild** are dead; task failed "timed out after 2s"; QA cancelled |
| Cancellation | `test_cancel_running_task_from_another_process` | `aidc cancel` from another process kills the running agent in < 15 s; dev and QA cancelled; no `task.completed` |
| Retry limit | `test_retry_limit_is_enforced` | always-crashing agent: exactly 3/3 attempts, 2 `retry_scheduled`; a later dispatch does not start a 4th |
| Halt + resume | `test_halt_stops_running_agent_and_resume_completes` | `aidc halt` kills the running agent; dispatch exits 3; while halted nothing is claimed; after `resume` the run completes (dev attempt 2, QA done) |
| Crash recovery | `test_recovery_after_dispatcher_crash` | SIGKILL the dispatcher → the agent dies too (PDEATHSIG); after lease expiry `recover` re-queues; the next dispatch completes |
| Stop: max tasks | `test_max_tasks_stop_condition` | `--max-tasks 1` runs only dev |
| Stop: usage limit | `test_usage_limit_stop_condition` | Codex limit message → halt `subscription_usage_limit`, exit 3, no retry |
| Stop: isolation | `test_isolation_violation_halts_run` | an agent writing into the manager checkout → task failed, run halted `isolation_violation` |
| Manager gate | `test_manager_review_gate`, `test_manager_review_rejects_failed_qa` | `aidc review` accepts only when dev and QA both passed and the sandboxed tests pass; rejects on failing tests or a QA FAIL |
| Manual write gate | `test_manual_developer_claim_requires_ack` | developer claim without `--unsandboxed-ack` is refused; the ack is logged |

These integration tests use the fake Codex binary as the *agent process*, because their purpose is to test the
orchestrator's process control. They are not the "real Codex" evidence asked for in priority 4, which is still outstanding.

## 4. Real Codex execution status

**Not executed.** No real Codex agent has run yet.

- `codex login status` → `Not logged in`. `https://auth.openai.com` → 403 and `https://chatgpt.com` → 403 from this
  container's network policy (`evidence/codex-auth-status.txt`). Both sign-in methods (browser and device code) need those hosts.
- `scripts/codex-e2e.sh` refused to start: "Codex is not signed in with ChatGPT" (`evidence/codex-e2e-attempt.txt`).
  Nothing switched to API billing.
- Ready to run on an owner-controlled machine: `scripts/owner-codex-setup.sh` then `scripts/codex-e2e.sh`. The
  procedure, environment requirements and pass criteria are in `docs/OWNER_SETUP.md`. Expected cost is about 2 Codex
  tasks from the ChatGPT plan quota.

## 5. Resource usage

| Resource | Phase 1.5 usage | Cost |
|----------|-----------------|------|
| Codex / ChatGPT plan | 0 agent tasks. About 5 unauthenticated `codex exec` config-validation calls reached `api.openai.com` and got 401, with no account attached | $0 |
| OpenAI / Anthropic API | none; no keys present | $0 |
| Claude Code | this session only (no subagents in Phase 1.5); counts against the account's Claude plan | no pay-as-you-go |
| Railway | not used | $0 |
| GitHub | existing repo/branch; one failed repo-create call (403) | $0 |
| Compute | full test suite ≈ 26 s; disk: Codex CLI in git-ignored `.tools/` (~436M) | — |

## 6. Remaining blockers

1. **Owner: revoke the Telegram token** (critical, independent of everything else).
2. **Owner: sign in to Codex on a trusted machine** and run `scripts/codex-e2e.sh`. This is the only thing blocking priority 4.
3. **Owner decision:** rewrite `main` history to purge the token (force-push), or accept the revoked token staying in history.
4. **Owner (optional):** create the private `ai-dev-company` repo and grant the Claude App that one repo (`docs/GITHUB_403.md`).
5. Merge of this branch into `main` (needs a PR and owner review; not done).

## 7. Phase 2 readiness recommendation

**Not ready yet. Conditionally ready once blockers 1 and 2 are cleared.**

The orchestration, isolation and stop/recovery machinery is now enforced and tested at the process and OS level.
What has not been shown is the core Phase 1 claim with Codex: real Codex agents completing manager → developer →
independent QA → manager review. I recommend approving Phase 2 only after:

1. The token is revoked (and history purged if wanted).
2. `scripts/codex-e2e.sh` passes on an owner machine with `aidc review` → `"accepted": true`, and the evidence is
   pushed (`runs/<id>/`, including the raw Codex event streams).
3. `scripts/run-tests.sh` passes on that same machine (45/45, no skips, 24/24).

After that, Phase 2 should start with the interactive manager loop in `docs/MANAGER_LOOP.md`, with every approval
gate on. Unattended operation and the management dashboard should stay off until several supervised loops complete
with zero isolation violations.

Phase 1.5 stops here, waiting for supervisor approval.
