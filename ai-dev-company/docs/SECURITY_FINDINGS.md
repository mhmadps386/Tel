# Security findings (Phase 1.5)

## F1 — Telegram bot token committed to a public repository (CRITICAL)

| | |
|---|---|
| Where | `newfile.py`, line 6 (`BOT_TOKEN = "..."`), repository `mhmadps386/Tel` |
| Visibility | **Public**: the GitHub API returns `"private": false, "visibility": "public"` |
| Introduced | commit `62901f1` ("Add files via upload"), 2025-01-03, on `main` |
| Exposure window | since 2025-01-03, about 22 months. Assume it has been harvested: bots scrape GitHub for tokens within minutes |
| Value printed anywhere? | No. Every scan in this work masked it (`scripts/scan-secrets.sh` reports locations only) |

### What was changed (branch `claude/ai-dev-company-phase-1-2y0h5h`)

- `newfile.py` now reads the token from the `TELEGRAM_BOT_TOKEN` environment variable and exits with
  a clear message if it is not set. No other behaviour changed.
- The Phase 1 worktrees that held copies of the old file were removed. No copy of the token remains on
  disk outside `.git`.
- `scripts/scan-secrets.sh` now checks the working tree **and full history** for token-shaped strings
  (Telegram, OpenAI, Anthropic, GitHub, AWS, private keys) without printing values.

`main` still contains the token, because this branch is not merged. Removing the hard-coded value only
stops new exposure. **The token is compromised until the owner revokes it.**

### Owner action: revoke and rotate (≈2 minutes, do this first)

1. In Telegram, open a chat with **@BotFather** (check for the blue verified tick).
2. Send `/mybots`, then choose the bot.
3. Tap **API Token**, then **Revoke current token**. BotFather immediately invalidates the old token
   and shows a new one. (Typing `/revoke` and picking the bot does the same.)
4. Do **not** paste the new token into chat, an issue, a commit or a file in the repo. Store it in one of:
   - your shell/session only: `export TELEGRAM_BOT_TOKEN='…'` (typed by you, not committed), or
   - Railway: **Service → Variables → New Variable** `TELEGRAM_BOT_TOKEN` (the platform encrypts it), or
   - a local `.env` file that is listed in `.gitignore`.
5. Restart the bot. Anything still holding the old token will now fail to authenticate.
6. Check the bot for misuse while it was exposed: bot description/commands changed by someone else
   (`/mybots` → Edit Bot), unexpected webhooks (`getWebhookInfo` with the **new** token), unknown
   chats or groups the bot was added to.

### Git history

The token is in the history of `main` (commit `62901f1`). Removing it requires rewriting `main`, which
means a force-push. That is destructive to a shared branch, so it **was not done** and needs the owner's
explicit approval. Once the token is revoked, the copy in history is useless, so revocation is the real fix.
If the owner also wants it out of history:

```sh
# on a fresh clone, after revoking the token
pip install git-filter-repo
printf '%s\n' 'regex:[0-9]{8,10}:[A-Za-z0-9_-]{35}==>REMOVED_TELEGRAM_TOKEN' > /tmp/replacements.txt
git filter-repo --replace-text /tmp/replacements.txt
git push --force --all && git push --force --tags
```

Forks, clones and GitHub's cached views may keep the old commit. For full removal from GitHub, contact
GitHub Support after the force-push. None of this is needed for safety once the token is revoked.

Also recommended: enable **Secret scanning** and **Push protection** for the repo
(Settings → Code security). Both are free for public repositories.

## F2 — Agent isolation was instruction-based (HIGH) — fixed

Phase 1 QA agent wrote a stray file outside its workspace (`/home/user/api.test.js`). Fixed by OS-level
enforcement; see `docs/ISOLATION.md`. A regression test writes to that same location and is blocked
(`test_new_file_outside_workspace_blocked`).

## F3 — Codex `workspace-write` also allows `/tmp` by default (MEDIUM) — fixed

Found while writing the negative tests. With default settings, Codex's sandbox allowed writes to `/tmp`
and `$TMPDIR`, which are shared with the host and with other tasks. The runner and `.codex/config.toml`
now set `exclude_slash_tmp = true` and `exclude_tmpdir_env_var = true`. Codex then reports
`sandbox: workspace-write [workdir]`, and a test proves `/tmp` writes are blocked.

## F4 — Paid-billing fallback (MEDIUM) — closed

Codex's official `forced_login_method = "chatgpt"` setting is now applied by the runner (`-c`), the
project config and the owner setup script. With it, `codex login --with-api-key` is refused by Codex
itself ("API key login is disabled. Use ChatGPT login instead."). `aidc dispatch` additionally refuses
API-key mode and strips `OPENAI_API_KEY`/`CODEX_API_KEY` from the agent environment. Separately, an
`exec` run with a fake `OPENAI_API_KEY` set sent no credentials at all (HTTP 401 "Missing bearer").
