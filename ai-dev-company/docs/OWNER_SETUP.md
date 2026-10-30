# Owner setup: Codex with a ChatGPT subscription

Only the account owner signs in, on a machine they control. This project never asks for,
reads, copies, logs, transmits or stores passwords or OAuth tokens. `aidc` reads only the
**mode** line of `codex login status` and the `forced_login_method` line of Codex's config.

## Why it cannot be done in the Claude Code cloud container

The container's network policy returns HTTP 403 for `auth.openai.com` and `chatgpt.com`
(`runs/phase1_5/evidence/codex-auth-status.txt`). Those hosts are needed for both browser and
device-code sign-in. Even if they were allowed, a ChatGPT session token would then live in a
third-party cloud container. **Recommendation: use an owner-controlled machine**, i.e. your own
laptop/desktop or a small VM in your own account. If you still prefer the cloud container, you
can add `auth.openai.com` and `chatgpt.com` under Allowed domains in the environment's Network
access settings (session title bar → environment → Edit; see
https://code.claude.com/docs/en/cloud-environments#network-access). Credentials there are
lost when the container is reclaimed.

## Trusted environment requirements

- Linux (Ubuntu 22.04+/Debian 12+ tested pattern) or macOS. Linux needs unprivileged user
  namespaces for the sandboxes (default on Ubuntu/Debian; check `unshare -Ur true`).
- git, Python ≥ 3.10, Node ≥ 20 and npm. No other packages.
- A normal user account (not root). Full-disk encryption on.
- `OPENAI_API_KEY` / `CODEX_API_KEY` **unset** in the shell you use.

## Procedure (≈10 minutes, about 2 Codex tasks of quota for the test run)

```sh
git clone https://github.com/mhmadps386/Tel.git && cd Tel
git checkout claude/ai-dev-company-phase-1-2y0h5h
cd ai-dev-company

# 1. Install the pinned Codex CLI, lock it to ChatGPT sign-in, and sign in yourself
scripts/owner-codex-setup.sh            # browser sign-in
# or: scripts/owner-codex-setup.sh --device   (headless: open the shown URL, enter the code)

# 2. Prove the safety rails on your machine (no Codex quota used)
scripts/run-tests.sh                    # expect: orchestrator 45 OK (no skips), demo-app 24/24
./aidc preflight                        # expect: codex_auth_mode "chatgpt",
                                        #         codex_forced_login_method "chatgpt",
                                        #         os_sandbox_available true

# 3. Real workflow: manager -> Codex developer -> independent Codex QA -> manager review
scripts/codex-e2e.sh run-codex-e2e-1

# 4. Hand back the evidence (contains no credentials)
git checkout -b aidc/phase1_5-evidence
git add runs/run-codex-e2e-1 runs/test-evidence && git commit -m "Phase 1.5 real Codex run evidence"
git push -u origin aidc/phase1_5-evidence
```

What `owner-codex-setup.sh` does:

1. Installs `@openai/codex@0.166.0` into `ai-dev-company/.tools/` (git-ignored).
2. Adds `forced_login_method = "chatgpt"` to `~/.codex/config.toml`. Codex then refuses API-key login.
3. Stops if an API-key variable is set.
4. Runs `codex login` (or `--device-auth`). You complete it in the browser; nothing is captured.
5. Verifies `codex login status` reports ChatGPT, then runs `aidc preflight`.

What `codex-e2e.sh` checks before spending any quota: Codex is installed, signed in **with ChatGPT**,
and no API-key variables are set. If Codex hits a plan usage limit, the run halts (exit 3,
`run.halted` with reason `subscription_usage_limit`). It does not retry and never upgrades. After the
limit resets: `./aidc resume --run <id> --note "limit reset"` and `./aidc dispatch --run <id>`.

### Pass criteria for the real run

- `runs/<id>/events.jsonl` shows `task.claimed`/`task.completed` for `dev-1` by `codex-developer` and
  `qa-1` by `codex-qa`, with `codex.exec` entries showing `--sandbox workspace-write` / `read-only`.
- `runs/<id>/codex/*/attempt-*/codex-events.jsonl` exists, which is the raw Codex JSON event stream.
- `aidc review` prints `"accepted": true`, and `evidence/manager-review-dev-1.txt` shows the sandboxed `npm test` passing.
- No `isolation_violation` and no `subscription_usage_limit` halt.

## Native Codex multi-agent mode (optional, interactive)

`.codex/config.toml` defines `developer` and `qa` roles (`max_threads = 2`, `max_depth = 1`,
`job_max_runtime_seconds = 1800`) with the same hardened sandbox and `forced_login_method`.
Codex 0.166.0 accepts it with `--strict-config`. Running `codex` from the repo root and pasting
`agents/manager.md` lets Codex's built-in `spawn_agent`/`wait_agent` delegate to the roles.
`aidc dispatch` remains the deterministic, logged path used for acceptance.
