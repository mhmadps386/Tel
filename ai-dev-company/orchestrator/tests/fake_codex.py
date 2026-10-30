#!/usr/bin/env python3
"""Stand-in for the Codex CLI used only by the orchestrator's own tests.

Behaviour is driven by FAKE_CODEX_AUTH (chatgpt|api_key|none) and FAKE_CODEX_MODE
(ok|qa_fail|sleep|limit|crash). It never contacts any network service.
"""
import os
import sys
import time

args = sys.argv[1:]
if args == ["--version"]:
    print("codex-cli 0.0.0-fake")
    sys.exit(0)
if args[:2] == ["login", "status"]:
    auth = os.environ.get("FAKE_CODEX_AUTH", "chatgpt")
    print({"chatgpt": "Logged in using ChatGPT", "api_key": "Logged in using an API key - sk-***",
           "none": "Not logged in"}[auth])
    sys.exit(0 if auth != "none" else 1)
if args[:2] == ["features", "list"]:
    print("multi_agent                              stable             true")
    sys.exit(0)
assert args[0] == "exec", args
assert "--dangerously-bypass-approvals-and-sandbox" not in args
for k in ("OPENAI_API_KEY", "CODEX_API_KEY"):
    assert k not in os.environ, f"{k} leaked into the agent environment"
workdir = args[args.index("--cd") + 1]
sandbox = args[args.index("--sandbox") + 1]
out = args[args.index("--output-last-message") + 1]
prompt = sys.stdin.read()
mode = os.environ.get("FAKE_CODEX_MODE", "ok")
counter = os.environ.get("FAKE_CODEX_COUNTER")
if counter:
    n = int(open(counter).read() or 0) + 1 if os.path.exists(counter) else 1
    open(counter, "w").write(str(n))
    if os.environ.get("FAKE_CODEX_FAIL_FIRST") and n == 1:
        mode = "crash"
print('{"type":"thread.started"}', flush=True)
if mode == "sleep":
    time.sleep(60)
if mode == "limit":
    print("ERROR: You've hit your usage limit. Upgrade your plan or try again later.")
    sys.exit(1)
if mode == "crash":
    sys.exit(3)
if sandbox == "workspace-write":
    with open(os.path.join(workdir, "feature.txt"), "w") as fh:
        fh.write("implemented\n")
role = "QA" if "QA agent" in prompt else "Developer"
verdict = "FAIL" if mode == "qa_fail" and role == "QA" else "PASS"
with open(out, "w") as fh:
    fh.write(f"{role} finished the task in {sandbox} mode.\n\nRESULT: {verdict}\n")
sys.exit(0)
