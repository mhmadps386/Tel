# Owner setup: Codex with a ChatGPT subscription

Only the account owner signs in, on a machine they trust. This project never asks for,
reads, copies, logs or stores passwords or OAuth tokens. `aidc` only reads the **mode**
reported by `codex login status`.

## 1. Install (pinned version)

```sh
npm install -g @openai/codex@0.166.0     # or a project-local install: npm i @openai/codex@0.166.0
codex --version                          # expect: codex-cli 0.166.0
```

## 2. Sign in with ChatGPT (the owner does this)

```sh
codex login                  # opens the browser; choose "Sign in with ChatGPT"
# headless machine:
codex login --device-auth    # shows a URL + one-time code to open on your phone or laptop
codex login status           # expect: "Logged in using ChatGPT"
```

Codex stores its credentials in `~/.codex/` on that machine. That folder is outside this
repository and must never be committed or copied.

Do **not** run `codex login --with-api-key`. `aidc dispatch` refuses to start when Codex
reports API-key auth, because that would bill per token.

## 3. Check and run

```sh
./aidc preflight            # codex_auth_mode must be "chatgpt"
./aidc dispatch --run <id>  # runs ready tasks through `codex exec` in isolated worktrees
```

If Codex reports a usage limit, the run halts (`run.halted` in `events.jsonl`) and nothing
retries or upgrades. Wait for the limit to reset, then run `./aidc resume --run <id> --note "limit reset"`.

## Native Codex multi-agent mode (optional)

`.codex/config.toml` defines `developer` and `qa` agent roles (`[agents.*]`) with
`max_threads = 2`, `max_depth = 1` and `job_max_runtime_seconds = 1800`. Codex 0.166.0
loads it with `--strict-config`. With this project trusted in Codex, the owner can start an
interactive manager session with `codex` from the repo root, paste `agents/manager.md`, and
Codex's built-in `spawn_agent`/`wait_agent` tools will delegate to the two roles.
`aidc dispatch` is the deterministic, logged path. The native mode is for interactive use.
