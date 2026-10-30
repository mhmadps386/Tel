# Agent isolation (OS-enforced)

Phase 1 relied on instructions ("only write inside your worktree"), and a QA agent broke them once.
Phase 1.5 enforces the boundary in the kernel. Agents cannot write outside their area even if they try.

## Two enforcement layers

| Who runs | Enforcement | Writable | Network | Credentials visible |
|---|---|---|---|---|
| **Codex agents** (`aidc dispatch`) | Codex's official Linux sandbox (bubblewrap + seccomp) on every model-issued command, with config forced by the runner | developer: its worktree only; QA: nothing (`read-only`) | off | n/a (commands sandboxed) |
| **Verification and hand-driven commands** (`aidc review`, `aidc sandbox-exec`) | `aidc.sandbox` (bubblewrap): read-only root, tmpfs over `$HOME`, `/root` and the repo, private `/tmp`, new user/pid/net/ipc/uts namespaces, uid 1000, `--clearenv`, die-with-parent, rlimits | the given workdir (+ explicit `--writable`) | off unless `--network` | none (`$HOME` and `/root` replaced by empty tmpfs) |

Plus two orchestrator-level guards:

- **Isolation canary.** Before and after each Codex task, the runner snapshots `git status` of the
  manager's checkout (excluding `runs/`, `.aidc-worktrees/` and `.tools/`). Any difference marks the task
  failed and halts the run with `isolation_violation`. This guards against sandbox failures or misconfiguration.
- **No orphans.** Agents get `PR_SET_PDEATHSIG=SIGKILL` and their own process group. A crashed
  orchestrator takes its agents with it, and a timeout, cancel or halt kills the whole tree.

The runner forces this Codex config on every run:

```
approval_policy="never"                                  # escalations are refused, never auto-approved
forced_login_method="chatgpt"                            # no API-key billing
sandbox_workspace_write.network_access=false
sandbox_workspace_write.exclude_slash_tmp=true           # default would allow /tmp (finding F3)
sandbox_workspace_write.exclude_tmpdir_env_var=true
--sandbox workspace-write | read-only                    # danger-full-access and --dangerously-* flags are rejected
```

## Hand-driven agents (the Phase 1 Claude subagents)

A chat-session subagent's file tools act directly on the host, so `aidc` cannot sandbox them.
`aidc claim` on a **developer** task therefore now fails unless the caller passes `--unsandboxed-ack`,
and that acknowledgement is written to the run log (`policy.unsandboxed_claim`). The recommended
path for any write task is `aidc dispatch` (Codex sandbox). To use Claude Code agents for write tasks in
future, run them in an OS-sandboxed environment: a separate container or VM per agent, or Claude
Code's own sandboxing/permission settings. That needs a supervisor decision; it is not enabled here.

## Negative tests (all real, nothing mocked)

`orchestrator/tests/test_sandbox.py`:

| Test | Attempt | Expected and observed |
|---|---|---|
| `test_write_to_parent_project_blocked` | overwrite a file in the parent project | `Read-only file system`, file unchanged |
| `test_new_file_outside_workspace_blocked` | create files in the parent project, a sibling dir, `/home/user/` (the Phase 1 incident path) and `/etc` | all fail, nothing created on the host |
| `test_hidden_paths_are_read_only` | write next to the workspace inside the hidden repo tree | `Read-only file system` (not a silent write into a throwaway overlay) |
| `test_refuses_broad_writable_roots` | make `/` or `$HOME` the workdir | refused before launch |
| `test_symlink_escape_blocked` | symlink out of the workspace and write through it | blocked |
| `test_delete_outside_workspace_blocked` | `rm` a file outside | blocked, file still there |
| `test_credentials_hidden` | read a decoy `auth.json` and list `$HOME` | not visible |
| `test_network_blocked` | TCP connect to the egress proxy (reachable from the host) | connection refused |
| `test_runs_unprivileged_with_private_pids` | `id -u`, look for a host pid | uid 1000, host pids invisible |
| `test_environment_scrubbed` | dump env | host secrets and API-key vars absent |
| `test_timeout_kills_sandbox` / `test_file_size_limit` | `sleep 60` / write 5 MB with a 1 MB cap | killed / capped |
| `CodexSandboxTest.test_codex_workspace_write_blocks_outside_writes` | via `codex sandbox` with the runner's config: write outside and to `/tmp` | blocked |
| `CodexSandboxTest.test_codex_read_only_blocks_workspace_writes` | QA mode writing in its own checkout | blocked |

`orchestrator/tests/test_integration.py::test_isolation_violation_halts_run`: an agent that escapes
(simulated) is detected by the canary; the task fails and the run halts.

## Known limits

- Linux only (bubblewrap). On macOS, Codex uses Seatbelt; `aidc.sandbox` would need a Seatbelt or container backend.
- The sandbox needs unprivileged user namespaces. If they are unavailable, `aidc.sandbox` fails closed
  (`SandboxUnavailable`) instead of running unsandboxed.
- The Codex harness process itself (as opposed to the commands it runs) is not wrapped. It needs network
  access to OpenAI and writes to `~/.codex`. Bubblewrap cannot be nested in this container: the inner
  `--proc` mount is refused, so wrapping it would break Codex's own sandbox. The canary covers this gap.
  A per-run container or VM would close it fully (Phase 2 option).
