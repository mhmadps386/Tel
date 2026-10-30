#!/usr/bin/env python3
"""SIMULATED Codex CLI for control-plane tests only. Not an AI model.

- `sandbox ...` is passed through to the REAL Codex binary (SIM_REAL_CODEX), so the worker's
  sandbox self-test exercises genuine OS isolation.
- `login status` / `login --device-auth` simulate ChatGPT device sign-in with a marker file
  in CODEX_HOME (no network, no credentials).
- `exec` behaves per agent role, driven by files in SIM_DIR:
    review-<n>  : decision for the n-th review call ("correct" or "accept"; default accept)
    hang        : if present, develop runs sleep forever (for cancel / estop / crash tests)
"""
import json
import os
import sys
import time

args = sys.argv[1:]
home = os.environ.get("CODEX_HOME", "")
marker = os.path.join(home, "sim-chatgpt-auth")
simdir = os.environ.get("SIM_DIR", "/nonexistent")

if args == ["--version"]:
    print("codex-cli 0.0.0-sim")
    sys.exit(0)
if args[:1] == ["sandbox"]:
    os.execv(os.environ["SIM_REAL_CODEX"], [os.environ["SIM_REAL_CODEX"], *args])
if args[:2] == ["login", "status"]:
    print("Logged in using ChatGPT" if os.path.exists(marker) else "Not logged in")
    sys.exit(0 if os.path.exists(marker) else 1)
if args[:2] == ["login", "--device-auth"]:
    print("Follow these steps to sign in with ChatGPT using device code authorization:", flush=True)
    print("1. Open this link in your browser and sign in to your account", flush=True)
    print("   https://auth.openai.com/codex/device", flush=True)
    print("2. Enter this one-time code (expires in 15 minutes)", flush=True)
    print("   SIMU-1234", flush=True)
    approve = os.path.join(simdir, "approve-login")
    for _ in range(600):
        if os.path.exists(approve):
            open(marker, "w").write("simulated")
            print("Successfully logged in", flush=True)
            sys.exit(0)
        time.sleep(0.1)
    sys.exit(1)

assert args[0] == "exec", args
assert "--dangerously-bypass-approvals-and-sandbox" not in args
for k in ("OPENAI_API_KEY", "CODEX_API_KEY"):
    assert k not in os.environ, f"{k} leaked into the agent environment"
workdir = args[args.index("--cd") + 1]
mode = args[args.index("--sandbox") + 1]
out = args[args.index("--output-last-message") + 1]
prompt = sys.stdin.read()


def write(text):
    with open(out, "w") as fh:
        fh.write(text)


def count(name):
    path = os.path.join(simdir, f"count-{name}")
    n = int(open(path).read()) + 1 if os.path.exists(path) else 1
    open(path, "w").write(str(n))
    return n


if prompt.startswith("You are the AI Manager of a small software team"):
    assert mode == "read-only"
    write(json.dumps({"summary": "SIMULATED plan", "developer_task": "Add NOTES.md describing the change.",
                      "qa_focus": "NOTES.md exists", "acceptance_criteria": ["npm test passes"], "risks": []}))
elif prompt.startswith("You are the developer agent"):
    assert mode == "workspace-write"
    with open(os.path.join(simdir, "dev-pid"), "w") as fh:
        fh.write(str(os.getpid()))
    if os.path.exists(os.path.join(simdir, "hang")):
        time.sleep(3600)
    n = count("develop")
    with open(os.path.join(workdir, "NOTES.md"), "a") as fh:
        fh.write(f"simulated change round {n}\n")
    write(f"SIMULATED developer report round {n}\nRESULT: PASS\n")
elif prompt.startswith("You are the independent QA agent"):
    assert mode == "read-only"
    try:  # read-only must really be read-only: prove a write fails (we are not sandboxed here, so just don't)
        pass
    finally:
        write("SIMULATED QA report: checked NOTES.md\nRESULT: PASS\n")
elif prompt.startswith("You are the AI Manager reviewing"):
    assert mode == "read-only"
    n = count("review")
    path = os.path.join(simdir, f"review-{n}")
    decision = open(path).read().strip() if os.path.exists(path) else "accept"
    write(json.dumps({"decision": decision, "rationale": f"SIMULATED review {n}: {decision}",
                      "correction": "Add a second line to NOTES.md." if decision == "correct" else ""}))
else:
    write("unknown prompt\nRESULT: FAIL\n")
sys.exit(0)
