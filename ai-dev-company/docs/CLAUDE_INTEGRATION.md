# Claude integration (optional in Phase 1, not activated)

## What is officially permitted with a Claude Max subscription

- **Claude Code itself** (CLI, desktop, web, IDE) supports signing in with a Pro or Max plan.
  Usage counts against the plan's limits. Using its built-in features, including subagents,
  worktrees and `claude -p` headless runs **by the subscriber, for their own work**, is the
  product being used as intended. The Phase 1 demo run used exactly this: Claude Code's own
  subagent feature inside an official Claude Code session.
- **Third-party products and automated harnesses** built on the Claude Agent SDK or the API
  are expected to authenticate with an **API key** (Claude Console, or Bedrock/Vertex),
  not with a consumer subscription login. Anthropic's terms do not allow offering
  subscription-authenticated (claude.ai login) access inside third-party products.

So this project does **not** contain code that launches Claude under a subscription login
on its own. Before any Phase 2 automation of Claude, the supervisor should re-check the current
Anthropic docs and consumer terms, which change faster than this note.

## How an authorised Claude API connection would plug in later (not enabled)

The board is runner-agnostic. A `claude_runner.py` would mirror `codex_runner.py`:

1. It would only be enabled by an explicit flag, e.g. `aidc dispatch --runner claude-api --allow-paid-api`,
   plus a per-run spend cap. Without both, it refuses to start.
2. It would read the key from the environment (`ANTHROPIC_API_KEY`) or a secret manager. The key would
   never be written to the board, the run log or the repo.
3. It would run the Claude Agent SDK in the same isolated worktree with the same timeout, bounded
   retries and halt-on-limit behaviour, and log token usage per task in `events.jsonl`.
4. It would use a Console workspace with a monthly spend limit set in the Anthropic Console as the
   final backstop.

No API key exists in this environment (`./aidc preflight` reports `ANTHROPIC_API_KEY: false`),
and no Claude API runner is present in the code.
