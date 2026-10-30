"""Safety policy: isolated workspaces, refused operations, auth-mode guard."""

import os
import re
import subprocess

BRANCH_PREFIX = "aidc/"

# Codex is only ever started with these sandbox modes. danger-full-access and the
# --dangerously-bypass-* flags are never passed.
ALLOWED_SANDBOXES = ("read-only", "workspace-write")

# Text in agent output that means the subscription quota is exhausted. When seen,
# the run halts instead of retrying (and never falls back to paid API usage).
USAGE_LIMIT_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"usage limit",
        r"rate limit",
        r"quota",
        r"too many requests",
        r"\b429\b",
        r"upgrade (your )?plan",
        r"purchase more credits",
    )
]


class PolicyError(Exception):
    pass


def hits_usage_limit(text):
    return any(p.search(text or "") for p in USAGE_LIMIT_PATTERNS)


def ensure_inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    if os.path.commonpath([path, root]) != root:
        raise PolicyError(f"{path} is outside the allowed root {root}")
    return path


def safe_branch(run_id, task_id):
    name = f"{BRANCH_PREFIX}{run_id}/{task_id}"
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", name) or ".." in name:
        raise PolicyError(f"unsafe branch name {name!r}")
    return name


def create_worktree(repo_root, worktrees_root, run_id, task_id, base="HEAD"):
    """Create an isolated git worktree on a fresh aidc/* branch. Never touches existing branches."""
    branch = safe_branch(run_id, task_id)
    path = ensure_inside(os.path.join(worktrees_root, run_id, task_id), worktrees_root)
    if os.path.exists(path):
        raise PolicyError(f"worktree path already exists: {path}")
    subprocess.run(["git", "-C", repo_root, "worktree", "add", "-b", branch, path, base],
                   check=True, capture_output=True, text=True, timeout=60)
    return path, branch


def codex_auth_mode(codex_bin="codex", timeout_s=30):
    """Return 'chatgpt', 'api_key', 'none' or 'unknown' from `codex login status`.

    Only the status line is inspected; tokens are never read.
    """
    try:
        proc = subprocess.run([codex_bin, "login", "status"], capture_output=True, text=True, timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    out = (proc.stdout + proc.stderr).lower()
    if "not logged in" in out:
        return "none"
    if "chatgpt" in out:
        return "chatgpt"
    if "api key" in out or "api_key" in out:
        return "api_key"
    return "unknown"


def require_subscription_auth(mode):
    """Phase 1 rule: only ChatGPT-subscription auth may run agents. API keys would bill per token."""
    if mode == "chatgpt":
        return
    if mode == "api_key":
        raise PolicyError("Codex is authenticated with an API key (paid usage). Phase 1 only allows "
                          "ChatGPT subscription sign-in. Run `codex logout` then `codex login`.")
    raise PolicyError(f"Codex is not signed in with a ChatGPT subscription (mode={mode}). "
                      "The account owner must run `codex login` on the trusted machine.")
