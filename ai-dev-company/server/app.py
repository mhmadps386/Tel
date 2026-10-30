"""AI Dev Company control panel (HTTP server).

Owner routes (session cookie + CSRF): /api/*
Worker routes (Bearer worker token): /worker/*
Public: GET / (login page shell), GET /healthz (no data).

The panel never executes agent code. Agents run only on a separate execution worker
that polls /worker/* over HTTPS with its own revocable token.
"""

import json
import os
import re
import sys
import time
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import auth, db, manager
from .redact import redact_obj

STATIC = os.path.join(os.path.dirname(__file__), "static")
MAX_BODY = 64 * 1024
WORKER_STALE_S = 60

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                               "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000",
    "X-Robots-Tag": "noindex, nofollow",
    "Cache-Control": "no-store",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class HttpError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


class Handler(BaseHTTPRequestHandler):
    server_version = "aidc"
    sys_version = ""

    # -- plumbing ------------------------------------------------------------

    def log_message(self, fmt, *args):  # no request bodies or cookies in logs
        sys.stderr.write("%s %s\n" % (self.command, re.sub(r"\?.*", "", self.path)))

    def client_ip(self):
        fwd = self.headers.get("X-Forwarded-For", "")
        return (fwd.split(",")[0].strip() or self.client_address[0])[:64]

    def send(self, status, body, content_type="application/json", extra_headers=None):
        data = body if isinstance(body, bytes) else json.dumps(redact_obj(body), default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for k, v in {**SECURITY_HEADERS, **(extra_headers or {})}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise HttpError(413, "body too large")
        if not length:
            return {}
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            raise HttpError(415, "JSON only")
        try:
            return json.loads(self.rfile.read(length))
        except ValueError:
            raise HttpError(400, "invalid JSON") from None

    def cookie(self):
        jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return jar[auth.COOKIE].value if auth.COOKIE in jar else None

    def owner_session(self, c, write):
        sess = auth.session(c, self.cookie())
        if not sess:
            raise HttpError(401, "login required")
        if write and not auth.hmac.compare_digest(self.headers.get("X-CSRF", ""), sess["csrf"]):
            raise HttpError(403, "bad CSRF token")
        return sess

    def worker(self, c):
        token = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        tok = auth.worker_from_token(c, token)
        if not tok:
            raise HttpError(401, "invalid worker token")
        worker_id = (self.headers.get("X-Worker-Id") or f"worker-{tok['id']}")[:60]
        if not re.fullmatch(r"[A-Za-z0-9._-]+", worker_id):
            raise HttpError(400, "bad worker id")
        return worker_id, tok

    def route(self, method):
        path = self.path.split("?", 1)[0]
        try:
            if method == "GET" and path in ("/", "/index.html"):
                return self.static("index.html", "text/html; charset=utf-8")
            if method == "GET" and path in ("/app.js", "/app.css"):
                return self.static(path[1:], "application/javascript" if path.endswith(".js") else "text/css")
            if method == "GET" and path == "/healthz":
                with db.tx() as c:
                    c.execute("SELECT 1")
                return self.send(200, {"ok": True})
            if path.startswith("/api/"):
                return self.api(method, path)
            if path.startswith("/worker/"):
                return self.worker_api(method, path)
            raise HttpError(404, "not found")
        except HttpError as e:
            self.send(e.status, {"error": e.message})
        except (ValueError, PermissionError) as e:
            self.send(400 if isinstance(e, ValueError) else 403, {"error": str(e)})
        except Exception as e:  # never leak internals
            import traceback; traceback.print_exc()
            self.send(500, {"error": "internal error"})

    def static(self, name, ctype):
        with open(os.path.join(STATIC, name), "rb") as fh:
            self.send(200, fh.read(), ctype)

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    # -- owner API -------------------------------------------------------------

    def api(self, method, path):
        if method == "POST" and path == "/api/login":
            data = self.body()
            with db.tx() as c:
                sid, csrf = auth.login(c, str(data.get("password", ""))[:200], self.client_ip(),
                                       self.headers.get("User-Agent"))
            cookie = f"{auth.COOKIE}={sid}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age={auth.SESSION_HOURS * 3600}"
            return self.send(200, {"ok": True}, extra_headers={"Set-Cookie": cookie})
        write = method == "POST"
        with db.tx() as c:
            sess = self.owner_session(c, write)
            owner = c.execute("SELECT must_change FROM owner WHERE id=1").fetchone()
            if method == "GET" and path == "/api/state":
                return self.send(200, state(c, sess["csrf"], owner["must_change"]))
            data = self.body() if write else {}
            if path == "/api/logout":
                auth.logout(c, self.cookie())
                return self.send(200, {"ok": True},
                                 extra_headers={"Set-Cookie": f"{auth.COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict"})
            if path == "/api/password":
                auth.change_password(c, str(data.get("current", "")), str(data.get("new", "")))
                return self.send(200, {"ok": True})
            if owner["must_change"]:
                raise HttpError(403, "change the initial password first")
            if path == "/api/missions":
                mid = manager.submit_mission(c, int(data.get("project_id", 0)), str(data.get("title", "")),
                                             str(data.get("request", "")))
                return self.send(200, {"mission_id": mid})
            m = re.fullmatch(r"/api/missions/(\d+)/cancel", path)
            if m:
                manager.cancel_mission(c, int(m.group(1)))
                return self.send(200, {"ok": True})
            m = re.fullmatch(r"/api/approvals/(\d+)", path)
            if m:
                manager.decide_approval(c, int(m.group(1)), data.get("decision") == "approve", str(data.get("note", "")))
                return self.send(200, {"ok": True})
            if path == "/api/control":
                return self.send(200, control(c, str(data.get("action", "")), data))
            m = re.fullmatch(r"/api/worker-tokens/(\d+)/revoke", path)
            if m:
                c.execute("UPDATE worker_tokens SET revoked=TRUE WHERE id=%s", (int(m.group(1)),))
                db.event(c, "owner", "worker_token.revoked", token_id=int(m.group(1)))
                return self.send(200, {"ok": True})
            if path == "/api/worker-tokens":
                token = auth.create_worker_token(c, str(data.get("name") or "worker"))
                return self.send(200, {"token": token, "note": "shown once; store it on the worker host only"})
            raise HttpError(404, "not found")

    # -- worker API ------------------------------------------------------------

    def worker_api(self, method, path):
        if method != "POST":
            raise HttpError(405, "POST only")
        data = self.body()
        with db.tx() as c:
            worker_id, tok = self.worker(c)
            if path == "/worker/heartbeat":
                return self.send(200, heartbeat(c, worker_id, tok, data))
            if path == "/worker/claim":
                return self.send(200, {"job": manager.claim(c, worker_id, data.get("capabilities") or {})})
            m = re.fullmatch(r"/worker/jobs/(\d+)/result", path)
            if m:
                accepted = manager.submit_result(c, worker_id, int(m.group(1)), data)
                return self.send(200 if accepted else 409, {"accepted": accepted})
            m = re.fullmatch(r"/worker/jobs/(\d+)/event", path)
            if m:
                job = c.execute("SELECT mission_id, worker_id FROM jobs WHERE id=%s", (int(m.group(1)),)).fetchone()
                if not job or job["worker_id"] != worker_id:
                    raise HttpError(409, "not your job")
                db.event(c, worker_id, "agent." + re.sub(r"[^a-z_.]", "", str(data.get("kind", "note")))[:40],
                         job["mission_id"], int(m.group(1)), message=str(data.get("message", ""))[:2000])
                return self.send(200, {"ok": True})
            if path == "/worker/login":
                return self.send(200, login_update(c, worker_id, data))
            raise HttpError(404, "not found")


# -- views and controls -----------------------------------------------------------

def control(c, action, data):
    if action == "start":
        if db.get_setting(c, "estop")["active"]:
            raise ValueError("clear the emergency stop first")
        manager.set_loop(c, "running", "owner started the manager loop", data.get("auto_continue"))
    elif action == "pause":
        manager.set_loop(c, "paused", "owner paused the manager loop")
    elif action == "estop":
        manager.emergency_stop(c, "owner pressed emergency stop")
    elif action == "clear_estop":
        manager.clear_emergency_stop(c)
    elif action == "auto_continue":
        loop = db.get_setting(c, "loop")
        manager.set_loop(c, loop["state"], f"owner set auto-continue {'on' if data.get('value') else 'off'}",
                         bool(data.get("value")))
    elif action == "codex_login":
        if c.execute("SELECT 1 FROM jobs WHERE kind='login' AND status IN ('pending','running')").fetchone():
            raise ValueError("a sign-in is already in progress")
        db.set_setting(c, "login_request", {"pending": True, "requested_at": time.time()})
        manager.add_job(c, "login")
        db.event(c, "owner", "codex.login_requested")
    else:
        raise ValueError("unknown action")
    return {"ok": True}


def heartbeat(c, worker_id, tok, data):
    info = {k: data.get(k) for k in ("version", "host", "sandbox_ok", "sandbox_detail", "auth_mode",
                                      "forced_login_method", "codex_version", "current_job", "repo_ok", "load")}
    c.execute("""INSERT INTO workers(id, token_id, last_seen, info) VALUES (%s,%s,now(),%s)
                 ON CONFLICT (id) DO UPDATE SET last_seen=now(), info=EXCLUDED.info, token_id=EXCLUDED.token_id""",
              (worker_id, tok["id"], db.j(redact_obj(info))))
    current = data.get("current_job")
    # Crash recovery: a job the server thinks this worker holds, but the worker no longer runs
    # (worker restarted or crashed), goes straight back to the queue. The 15 s grace avoids racing a fresh claim.
    for job in c.execute("""SELECT * FROM jobs WHERE worker_id=%s AND status='running' AND id <> %s
                            AND started_at < now() - interval '15 seconds' FOR UPDATE""",
                         (worker_id, current or 0)).fetchall():
        manager._release(c, job, "worker restarted or lost the job")
    running = c.execute("SELECT id FROM jobs WHERE worker_id=%s AND status='running'", (worker_id,)).fetchall()
    stop = []
    if current and current not in {r["id"] for r in running}:
        stop.append(current)  # cancelled, released or reassigned: kill it
    estop = db.get_setting(c, "estop")
    if estop["active"] and current:
        stop.append(current)
    manager.tick(c)
    return {"stop_jobs": sorted(set(stop)), "estop": estop["active"], "loop": db.get_setting(c, "loop")["state"]}


def login_update(c, worker_id, data):
    """Worker relays the official device-code prompt (URL + one-time code) so the owner can finish sign-in."""
    job = c.execute("SELECT id FROM jobs WHERE kind='login' AND status='running' AND worker_id=%s", (worker_id,)).fetchone()
    if not job:
        raise HttpError(409, "no sign-in in progress")
    url = str(data.get("verification_url") or "")
    if url and not re.fullmatch(r"https://(auth\.openai\.com|chatgpt\.com)/[A-Za-z0-9/_.?=&-]*", url):
        raise HttpError(400, "unexpected sign-in URL")
    code = str(data.get("user_code") or "")
    if code and not re.fullmatch(r"[A-Z0-9-]{4,16}", code):
        raise HttpError(400, "unexpected code format")
    db.set_setting(c, "login_request", {"pending": True, "job_id": job["id"], "verification_url": url,
                                        "user_code": code, "status": str(data.get("status", ""))[:200],
                                        "expires_in_s": int(data.get("expires_in_s") or 900), "at": time.time()})
    db.event(c, worker_id, "codex.login_prompt", job_id=job["id"], status=str(data.get("status", ""))[:200])
    return {"ok": True}


def state(c, csrf, must_change):
    workers = c.execute("SELECT id, extract(epoch FROM now()-last_seen) AS age_s, info FROM workers ORDER BY last_seen DESC LIMIT 5").fetchall()
    for w in workers:
        w["online"] = w["age_s"] < WORKER_STALE_S
    missions = c.execute("SELECT id, project_id, title, status, round, max_rounds, branch, plan, outcome, created_at, updated_at "
                         "FROM missions ORDER BY id DESC LIMIT 30").fetchall()
    jobs = c.execute("SELECT id, mission_id, kind, round, status, attempts, max_attempts, worker_id, started_at, finished_at, "
                     "seconds, errors, result->>'verdict' AS verdict, result->>'summary' AS summary, result->'tests' AS tests "
                     "FROM jobs ORDER BY id DESC LIMIT 60").fetchall()
    events = c.execute("SELECT id, at, mission_id, job_id, actor, kind, data FROM events ORDER BY id DESC LIMIT 120").fetchall()
    approvals = c.execute("SELECT a.id, a.mission_id, a.kind, a.payload, a.created_at, m.title FROM approvals a "
                          "JOIN missions m ON m.id=a.mission_id WHERE a.status='pending' ORDER BY a.id").fetchall()
    usage = c.execute("""SELECT count(*) FILTER (WHERE kind IN ('plan','develop','qa','review')) AS agent_jobs,
                                count(*) FILTER (WHERE status='failed') AS failed_jobs,
                                coalesce(sum(attempts),0) AS attempts,
                                coalesce(sum(seconds) FILTER (WHERE kind IN ('plan','develop','qa','review')),0) AS agent_seconds,
                                coalesce(sum(seconds) FILTER (WHERE kind IN ('plan','develop','qa','review')
                                                               AND finished_at > now() - interval '24 hours'),0) AS agent_seconds_24h
                         FROM jobs""").fetchone()
    login = db.get_setting(c, "login_request")
    if login.get("at") and time.time() - login["at"] > login.get("expires_in_s", 900):
        login = {"pending": False, "status": "expired"}
    return {
        "csrf": csrf, "must_change_password": must_change,
        "loop": db.get_setting(c, "loop"), "estop": db.get_setting(c, "estop"), "login": login,
        "projects": c.execute("SELECT id, name, description, disposable FROM projects ORDER BY id").fetchall(),
        "worker_tokens": c.execute("SELECT id, name, created_at, revoked FROM worker_tokens ORDER BY id").fetchall(),
        "workers": workers, "missions": missions, "jobs": jobs, "events": events, "approvals": approvals,
        "usage": {**usage, "paid_api_calls": 0,
                  "infrastructure": {"railway_services": ["aidc-web", "Postgres"],
                                     "note": "Railway bills by measured CPU/RAM/egress; see the Railway dashboard for exact figures."}},
        "server_time": time.time(),
    }


def main():
    db.migrate()
    with db.tx() as c:
        if not auth.ensure_owner(c):
            sys.stderr.write("WARNING: no owner yet; set AIDC_INITIAL_PASSWORD_HASH (scrypt hash) to enable login\n")
    port = int(os.environ.get("PORT", "8080"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    httpd.daemon_threads = True
    sys.stderr.write(f"aidc control panel listening on :{port}\n")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
