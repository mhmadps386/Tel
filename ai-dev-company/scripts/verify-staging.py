#!/usr/bin/env python3
"""Black-box privacy/auth checks against a deployed control panel. Prints evidence; never prints secrets.

  scripts/verify-staging.py https://<panel> [--initial-password-file FILE]
"""
import argparse
import http.cookiejar
import json
import ssl
import sys
import urllib.error
import urllib.request

p = argparse.ArgumentParser()
p.add_argument("url")
p.add_argument("--initial-password-file")
args = p.parse_args()
base = args.url.rstrip("/")
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),
                                     urllib.request.HTTPSHandler(context=ssl.create_default_context()))
results = []


def req(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"} if body is not None else {}
    h.update(headers or {})
    r = urllib.request.Request(base + path, data=data, method=method, headers=h)
    try:
        with opener.open(r, timeout=30) as res:
            return res.status, {k.lower(): v for k, v in res.headers.items()}, res.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


s, h, b = req("GET", "/")
check("GET / serves login shell over HTTPS", s == 200 and base.startswith("https://"), f"status={s}")
for header in ("Content-Security-Policy", "Strict-Transport-Security", "X-Frame-Options", "X-Content-Type-Options",
               "Referrer-Policy", "X-Robots-Tag"):
    check(f"header {header}", header.lower() in h, h.get(header.lower(), "")[:60])
check("no inline script in HTML", b"<script>" not in b)
s, h, b = req("GET", "/healthz")
check("/healthz reveals nothing but ok", s == 200 and json.loads(b) == {"ok": True}, b.decode()[:40])
for method, path in (("GET", "/api/state"), ("POST", "/api/missions"), ("POST", "/api/control"),
                     ("POST", "/api/approvals/1"), ("POST", "/api/worker-tokens")):
    s, _, _ = req(method, path, {} if method == "POST" else None)
    check(f"anonymous {method} {path} refused", s == 401, f"status={s}")
for path in ("/worker/heartbeat", "/worker/claim", "/worker/jobs/1/result", "/worker/login"):
    s, _, _ = req("POST", path, {})
    check(f"worker endpoint {path} without token refused", s == 401, f"status={s}")
    s, _, _ = req("POST", path, {}, {"Authorization": "Bearer aidcw_forged_token_value_for_testing_only"})
    check(f"worker endpoint {path} with forged token refused", s == 401, f"status={s}")
s, _, b = req("POST", "/api/login", {"password": "definitely-not-the-password"})
check("wrong password refused", s == 403, f"status={s}")
s, _, _ = req("GET", "/nonexistent")
check("unknown path 404 without detail", s == 404)
http_base = base.replace("https://", "http://")
try:
    with urllib.request.urlopen(http_base + "/healthz", timeout=15) as res:
        check("plain HTTP redirected to HTTPS", res.geturl().startswith("https://"), res.geturl())
except Exception as e:  # noqa: BLE001
    check("plain HTTP not served", True, type(e).__name__)

if args.initial_password_file:
    pw = open(args.initial_password_file).read().strip()
    s, h, _ = req("POST", "/api/login", {"password": pw})
    cookie = h.get("set-cookie", "")
    check("initial password signs in", s == 200)
    check("session cookie HttpOnly+Secure+SameSite=Strict",
          all(x in cookie for x in ("HttpOnly", "Secure", "SameSite=Strict")))
    s, _, b = req("GET", "/api/state")
    st = json.loads(b)
    check("must change initial password", st.get("must_change_password") is True)
    s, _, _ = req("POST", "/api/missions", {"project_id": 1, "title": "x", "request": "y"}, {"X-CSRF": st["csrf"]})
    check("panel locked until password changed", s == 403, f"status={s}")
    s, _, _ = req("POST", "/api/control", {"action": "pause"}, {"X-CSRF": "wrong"})
    check("CSRF token enforced", s == 403, f"status={s}")
    blob = json.dumps(st)
    check("state contains no secrets", not any(x in blob for x in ("postgres://", "postgresql://", "scrypt$", "sk-", "aidcw_")))
    check("loop starts paused (no unattended execution)", st["loop"]["state"] == "paused", st["loop"]["state"])
    check("estop inactive", st["estop"]["active"] is False)
    req("POST", "/api/logout", {}, {"X-CSRF": st["csrf"]})
    s, _, _ = req("GET", "/api/state")
    check("logout ends the session", s == 401)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
