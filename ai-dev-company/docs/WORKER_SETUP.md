# Connect an execution worker and sign in to Codex (owner, ≈15 minutes)

Railway hosts only the private control panel and its database. **Agents never run on Railway**:
Railway containers cannot create user namespaces, so neither Codex's sandbox nor ours can start there
(`runs/phase1_6/evidence/railway-sandbox-probe.txt`). Agents run on an **execution worker**: a machine you
control, which connects out to the panel over HTTPS. No inbound ports are opened.

## Requirements for the worker host

- Linux with unprivileged user namespaces: Ubuntu 22.04+/Debian 12 desktop, server or VM; Windows via
  **WSL2 Ubuntu**; macOS via a Linux VM (OrbStack, UTM or Multipass). Check with `unshare -Ur true`, which must succeed.
- git, Python 3.10+, Node 20+ and npm, installed system-wide (not only under `$HOME`, which the sandbox hides).
- Outbound HTTPS to `aidc-web-staging.up.railway.app`, `auth.openai.com` and `chatgpt.com`.
- `OPENAI_API_KEY` / `CODEX_API_KEY` **unset**.

## Steps

1. **Panel: set your own password.** Open the panel URL, sign in with the initial password I gave you,
   and choose a new one (12+ characters). The initial password stops working immediately.
2. **Panel: create a worker token.** Execution workers → *Create worker token*. It is shown once.
3. **Worker host:**
   ```sh
   git clone https://github.com/mhmadps386/Tel.git && cd Tel/ai-dev-company
   git checkout claude/ai-dev-company-phase-1-2y0h5h
   mkdir -p ~/.aidc-worker && chmod 700 ~/.aidc-worker
   nano ~/.aidc-worker/token          # paste the token, save
   chmod 600 ~/.aidc-worker/token
   AIDC_SERVER_URL=https://aidc-web-staging.up.railway.app scripts/run-worker.sh
   ```
   `run-worker.sh` refuses to start unless user namespaces work and the full sandbox test suite passes
   with no skips. It installs the pinned Codex CLI 0.166.0 into `.tools/`.
4. **Panel:** the worker appears as *online* with **OS sandbox OK** and Codex auth `none`.
5. **Panel: Start Codex sign-in (device code).** The worker runs the official `codex login --device-auth`.
   The panel then shows `https://auth.openai.com/codex/device` and a one-time code. Open the link, sign in
   to **your ChatGPT account on OpenAI's site**, and enter the code. If OpenAI reports that device-code
   sign-in is disabled for your account or workspace, enable it in your ChatGPT security settings (or ask
   the workspace admin). The panel never sees your password or tokens. Codex stores its credentials in
   `~/.aidc-worker/codex/auth.json` (file mode 0600, inside a 0700 directory) on your machine only,
   locked by `forced_login_method = "chatgpt"`.
6. **Check:** the worker shows Codex auth **chatgpt**. Restart the worker (Ctrl-C, run step 3 again): it
   must still show `chatgpt`, which shows the credentials survive restarts.

## First real mission (uses a few Codex tasks from your ChatGPT plan)

1. *New development task* → project `disposable-demo` → e.g. title "Add due dates to tasks", request
   "Tasks accept an optional dueDate (YYYY-MM-DD, validated, 400 on bad input); the dashboard shows it; add tests."
2. The AI Manager (Codex, read-only) writes a plan. **Approve the plan** under *Pending approvals*.
3. Press **Start / resume loop**. The developer agent (Codex, workspace-write) works, then the QA agent
   (Codex, read-only) reviews independently, and the manager re-runs the tests in the OS sandbox and decides.
   If it asks for corrections, a new round starts automatically (at most 5).
4. When the manager accepts, **approve the merge**. This merges only into the worker's local disposable
   repository; nothing is pushed or deployed.

Controls: **Pause** (finish the current step, start nothing new), **EMERGENCY STOP** (kill the running agent
now, block all work), *Cancel* on a mission. *Auto-continue* (off by default) lets the loop move to the next
approved mission without asking. Leave it off until you approve unattended execution.

## Revoking access

- Worker: panel → Execution workers → *Revoke* next to the token. The worker is refused on its next request.
- Codex: on the worker host, `CODEX_HOME=~/.aidc-worker/codex .tools/node_modules/.bin/codex logout`.
