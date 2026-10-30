"""AI Manager control loop (state machine over the database).

Mission lifecycle:
  planning --(plan job: Codex manager analyses the request)--> awaiting_plan_approval
  awaiting_plan_approval --(owner approves)--> approved  [= owner-approved backlog]
  approved --(loop running, no other active mission)--> in_progress (round 1)
  each round: develop -> qa (independent, read-only) -> review (tests re-run in the
              OS sandbox + Codex manager reads the QA report)
      review accepts and objective checks pass -> awaiting_merge_approval
      review asks for corrections and round < max_rounds -> next round (correction task)
      otherwise -> needs_owner
  awaiting_merge_approval --(owner approves)--> merging --> completed  (local disposable repo only)
  any --(owner cancels)--> cancelled ; job out of attempts -> failed

Nothing here merges, pushes or deploys on its own: merge jobs are only created from
an owner approval, and they act on the worker's local disposable repository.
"""

from . import db

ACTIVE = ("in_progress", "merging")
MAX_ROUNDS = 5
TIMEOUTS = {"plan": 900, "develop": 1800, "qa": 1200, "review": 1200, "merge": 300, "login": 960}
ATTEMPTS = {"plan": 2, "develop": 2, "qa": 2, "review": 2, "merge": 1, "login": 1}


def add_job(c, kind, mission_id=None, round_=0, spec=None, depends_on=()):
    row = c.execute(
        "INSERT INTO jobs(mission_id, kind, round, spec, depends_on, timeout_s, max_attempts) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (mission_id, kind, round_, db.j(spec or {}), list(depends_on), TIMEOUTS[kind], ATTEMPTS[kind])).fetchone()
    db.event(c, "manager", "job.created", mission_id, row["id"], kind=kind, round=round_)
    return row["id"]


def set_mission(c, mission_id, status, **fields):
    prev = c.execute("SELECT status FROM missions WHERE id=%s", (mission_id,)).fetchone()["status"]
    sets = ["status=%s", "updated_at=now()"]
    vals = [status]
    for k, v in fields.items():
        sets.append(f"{k}=%s")
        vals.append(db.j(v) if k in ("plan", "outcome") else v)
    c.execute(f"UPDATE missions SET {', '.join(sets)} WHERE id=%s", (*vals, mission_id))
    db.event(c, "manager", "mission.status", mission_id, status=status, previous=prev)
    if prev in ACTIVE and status not in ACTIVE:
        after_mission_settled(c)


# -- owner actions -----------------------------------------------------------

def submit_mission(c, project_id, title, request):
    if not title.strip() or not request.strip():
        raise ValueError("title and request are required")
    if len(title) > 200 or len(request) > 8000:
        raise ValueError("title or request too long")
    project = c.execute("SELECT id, disposable FROM projects WHERE id=%s", (project_id,)).fetchone()
    if not project or not project["disposable"]:
        raise ValueError("missions may only target a disposable project")
    m = c.execute("INSERT INTO missions(project_id, title, request, status, max_rounds) VALUES (%s,%s,%s,'planning',%s) "
                  "RETURNING id", (project_id, title.strip(), request.strip(), MAX_ROUNDS)).fetchone()
    db.event(c, "owner", "mission.submitted", m["id"], title=title)
    add_job(c, "plan", m["id"], 0, {"title": title, "request": request})
    return m["id"]


def decide_approval(c, approval_id, approve, note=""):
    a = c.execute("SELECT * FROM approvals WHERE id=%s FOR UPDATE", (approval_id,)).fetchone()
    if not a or a["status"] != "pending":
        raise ValueError("approval not found or already decided")
    status = "approved" if approve else "rejected"
    c.execute("UPDATE approvals SET status=%s, decided_at=now(), note=%s WHERE id=%s", (status, note[:500], approval_id))
    db.event(c, "owner", f"approval.{status}", a["mission_id"], approval=approval_id, kind=a["kind"], note=note[:500])
    m = c.execute("SELECT * FROM missions WHERE id=%s FOR UPDATE", (a["mission_id"],)).fetchone()
    if a["kind"] == "plan":
        set_mission(c, m["id"], "approved" if approve else "rejected")
    elif a["kind"] == "merge":
        if approve:
            set_mission(c, m["id"], "merging")
            add_job(c, "merge", m["id"], m["round"], {"branch": m["branch"]})
        else:
            set_mission(c, m["id"], "rejected")
    tick(c)


def cancel_mission(c, mission_id, reason="owner cancelled"):
    m = c.execute("SELECT * FROM missions WHERE id=%s FOR UPDATE", (mission_id,)).fetchone()
    if not m:
        raise ValueError("mission not found")
    if m["status"] in ("completed", "cancelled", "rejected", "failed"):
        raise ValueError(f"mission already {m['status']}")
    c.execute("UPDATE jobs SET status='cancelled', finished_at=now() WHERE mission_id=%s AND status IN ('pending','running')",
              (mission_id,))
    c.execute("UPDATE approvals SET status='rejected', decided_at=now(), note='mission cancelled' "
              "WHERE mission_id=%s AND status='pending'", (mission_id,))
    set_mission(c, mission_id, "cancelled", outcome={"reason": reason})


def set_loop(c, state, reason, auto_continue=None):
    loop = db.get_setting(c, "loop")
    loop["state"], loop["reason"] = state, reason
    if auto_continue is not None:
        loop["auto_continue"] = bool(auto_continue)
    db.set_setting(c, "loop", loop)
    db.event(c, "owner" if reason.startswith("owner") else "manager", f"loop.{state}", reason=reason,
             auto_continue=loop["auto_continue"])


def emergency_stop(c, reason):
    db.set_setting(c, "estop", {"active": True, "reason": reason})
    set_loop(c, "paused", f"emergency stop: {reason}")
    for job in c.execute("SELECT * FROM jobs WHERE status='running' FOR UPDATE").fetchall():
        _release(c, job, "emergency stop")
    db.event(c, "owner" if reason.startswith("owner") else "manager", "estop.activated", reason=reason)


def clear_emergency_stop(c):
    db.set_setting(c, "estop", {"active": False, "reason": None})
    db.event(c, "owner", "estop.cleared")


# -- worker interaction ------------------------------------------------------

def claim(c, worker_id, capabilities):
    """Give the worker the next runnable job, or None. Agent jobs need a healthy sandbox and ChatGPT auth."""
    tick(c)
    estop = db.get_setting(c, "estop")["active"]
    loop = db.get_setting(c, "loop")
    if estop:
        return None
    kinds = []
    if capabilities.get("login_ok"):
        kinds.append("login")
    if capabilities.get("repo_ok"):
        kinds.append("merge")           # owner already approved each merge job
    agent_ready = capabilities.get("sandbox_ok") and capabilities.get("auth_mode") == "chatgpt"
    if agent_ready and loop["state"] == "running":
        kinds += ["plan", "develop", "qa", "review"]
    elif agent_ready:
        kinds.append("plan")            # planning only proposes; nothing executes before approval
    if not kinds:
        return None
    job = c.execute(
        """SELECT j.* FROM jobs j WHERE j.status='pending' AND j.kind = ANY(%s)
           AND NOT EXISTS (SELECT 1 FROM jobs d WHERE d.id = ANY(j.depends_on) AND d.status <> 'done')
           ORDER BY (j.kind='login') DESC, j.id LIMIT 1 FOR UPDATE SKIP LOCKED""", (kinds,)).fetchone()
    if not job:
        return None
    c.execute("""UPDATE jobs SET status='running', attempts=attempts+1, worker_id=%s, started_at=now(),
                 lease_expires=now() + make_interval(secs => timeout_s + 300) WHERE id=%s""", (worker_id, job["id"]))
    db.event(c, worker_id, "job.claimed", job["mission_id"], job["id"], kind=job["kind"], attempt=job["attempts"] + 1)
    job = c.execute("SELECT * FROM jobs WHERE id=%s", (job["id"],)).fetchone()
    return _job_payload(c, job)


def _job_payload(c, job):
    payload = {k: job[k] for k in ("id", "mission_id", "kind", "round", "spec", "timeout_s", "attempts")}
    if job["mission_id"]:
        m = c.execute("SELECT id, title, request, plan, branch, round FROM missions WHERE id=%s",
                      (job["mission_id"],)).fetchone()
        payload["mission"] = m
    return payload


def submit_result(c, worker_id, job_id, body):
    job = c.execute("SELECT * FROM jobs WHERE id=%s FOR UPDATE", (job_id,)).fetchone()
    if not job or job["worker_id"] != worker_id or job["status"] != "running":
        return False  # cancelled, released or not ours: the result is discarded
    seconds = float(body.get("seconds") or 0)
    if body.get("isolation_violation"):
        _fail(c, job, "isolation violation reported by worker", seconds, retry=False)
        emergency_stop(c, f"isolation violation in job {job_id}")
        return True
    if body.get("usage_limit"):
        _fail(c, job, "subscription usage limit reached", seconds, retry=False)
        set_loop(c, "paused", "subscription usage limit reached: waiting for quota reset (no paid fallback)")
        return True
    if not body.get("ok"):
        _fail(c, job, (body.get("error") or "job failed")[:500], seconds, retry=bool(body.get("retryable", True)))
        return True
    result = body.get("result") or {}
    c.execute("""UPDATE jobs SET status='done', result=%s, finished_at=now(), lease_expires=NULL,
                 seconds=seconds+%s WHERE id=%s""", (db.j(result), seconds, job_id))
    db.event(c, worker_id, "job.done", job["mission_id"], job_id, kind=job["kind"], seconds=round(seconds, 1),
             verdict=result.get("verdict"), summary=(result.get("summary") or "")[:300])
    _advance(c, job, result)
    tick(c)
    return True


def _fail(c, job, error, seconds, retry=True):
    errors = job["errors"] + [{"attempt": job["attempts"], "error": error}]
    if retry and job["attempts"] < job["max_attempts"]:
        c.execute("""UPDATE jobs SET status='pending', worker_id=NULL, lease_expires=NULL, errors=%s,
                     seconds=seconds+%s WHERE id=%s""", (db.j(errors), seconds, job["id"]))
        db.event(c, "manager", "job.retry_scheduled", job["mission_id"], job["id"], error=error,
                 attempt=job["attempts"], max_attempts=job["max_attempts"])
        return
    c.execute("""UPDATE jobs SET status='failed', finished_at=now(), lease_expires=NULL, errors=%s,
                 seconds=seconds+%s WHERE id=%s""", (db.j(errors), seconds, job["id"]))
    db.event(c, "manager", "job.failed", job["mission_id"], job["id"], error=error, attempt=job["attempts"])
    if job["mission_id"] and job["kind"] != "login":
        set_mission(c, job["mission_id"], "failed", outcome={"failed_job": job["id"], "error": error})


def _release(c, job, reason):
    """Return a running job to the queue without judging it (attempt still counts)."""
    errors = job["errors"] + [{"attempt": job["attempts"], "error": f"released: {reason}"}]
    if job["attempts"] < job["max_attempts"]:
        c.execute("UPDATE jobs SET status='pending', worker_id=NULL, lease_expires=NULL, errors=%s WHERE id=%s",
                  (db.j(errors), job["id"]))
        db.event(c, "manager", "job.released", job["mission_id"], job["id"], reason=reason)
    else:
        _fail(c, job, f"released ({reason}) with no attempts left", 0, retry=False)


def _advance(c, job, result):
    mid = job["mission_id"]
    if job["kind"] == "login" or mid is None:
        return
    m = c.execute("SELECT * FROM missions WHERE id=%s FOR UPDATE", (mid,)).fetchone()
    if m["status"] in ("cancelled", "rejected", "failed"):
        return
    if job["kind"] == "plan":
        set_mission(c, mid, "awaiting_plan_approval", plan=result.get("plan"))
        c.execute("INSERT INTO approvals(mission_id, kind, payload) VALUES (%s,'plan',%s)",
                  (mid, db.j({"plan": result.get("plan")})))
    elif job["kind"] == "develop":
        c.execute("UPDATE missions SET branch=%s, updated_at=now() WHERE id=%s", (result.get("branch"), mid))
        add_job(c, "qa", mid, job["round"], {"branch": result.get("branch"), "dev_job": job["id"]}, [job["id"]])
    elif job["kind"] == "qa":
        dev = c.execute("SELECT id, result FROM jobs WHERE id=%s", (job["spec"]["dev_job"],)).fetchone()
        add_job(c, "review", mid, job["round"],
                {"branch": job["spec"]["branch"], "dev_job": dev["id"], "qa_job": job["id"],
                 "dev_report": (dev["result"] or {}).get("report", "")[:20000],
                 "dev_verdict": (dev["result"] or {}).get("verdict"),
                 "qa_report": result.get("report", "")[:20000], "qa_verdict": result.get("verdict")}, [job["id"]])
    elif job["kind"] == "review":
        _decide_round(c, m, job, result)
    elif job["kind"] == "merge":
        set_mission(c, mid, "completed", outcome={"merged_commit": result.get("commit"), "round": m["round"]})


def objective_checks(review_spec, result):
    tests = result.get("tests") or {}
    return {
        "developer_reported_pass": review_spec.get("dev_verdict") == "pass",
        "qa_reported_pass": review_spec.get("qa_verdict") == "pass",
        "tests_rerun_in_sandbox_pass": tests.get("exit_code") == 0 and not tests.get("timed_out"),
        "manager_decision_accept": (result.get("decision") or {}).get("decision") == "accept",
    }


def _decide_round(c, m, job, result):
    checks = objective_checks(job["spec"], result)
    decision = result.get("decision") or {}
    db.event(c, "manager", "review.decision", m["id"], job["id"], round=job["round"], checks=checks,
             decision=decision.get("decision"), rationale=(decision.get("rationale") or "")[:1000])
    if all(checks.values()):
        set_mission(c, m["id"], "awaiting_merge_approval",
                    outcome={"round": job["round"], "checks": checks, "tests": result.get("tests")})
        c.execute("INSERT INTO approvals(mission_id, kind, payload) VALUES (%s,'merge',%s)",
                  (m["id"], db.j({"branch": m["branch"], "round": job["round"], "checks": checks,
                                  "tests": result.get("tests"), "rationale": decision.get("rationale"),
                                  "diffstat": result.get("diffstat")})))
        return
    if job["round"] >= m["max_rounds"]:
        set_mission(c, m["id"], "needs_owner", outcome={"reason": f"not accepted after {job['round']} rounds",
                                                        "checks": checks})
        return
    correction = decision.get("correction") or (
        "The independent QA review or the re-run tests did not pass. Fix every issue in this QA report and make "
        "all tests pass:\n" + job["spec"].get("qa_report", "")[:8000])
    next_round = job["round"] + 1
    c.execute("UPDATE missions SET round=%s, updated_at=now() WHERE id=%s", (next_round, m["id"]))
    db.event(c, "manager", "correction.assigned", m["id"], round=next_round, correction=correction[:2000])
    add_job(c, "develop", m["id"], next_round, {"instructions": correction, "base_branch": m["branch"],
                                                "correction": True})


def tick(c):
    """Housekeeping: expire leases, start the next approved mission when allowed."""
    for job in c.execute("SELECT * FROM jobs WHERE status='running' AND lease_expires < now() FOR UPDATE SKIP LOCKED"):
        _release(c, job, "lease expired (worker lost)")
    estop = db.get_setting(c, "estop")["active"]
    loop = db.get_setting(c, "loop")
    if estop or loop["state"] != "running":
        return
    if c.execute("SELECT 1 FROM missions WHERE status = ANY(%s) LIMIT 1", (list(ACTIVE),)).fetchone():
        return
    nxt = c.execute("SELECT * FROM missions WHERE status='approved' ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED").fetchone()
    if not nxt:
        return
    plan = nxt["plan"] or {}
    c.execute("UPDATE missions SET round=1, updated_at=now() WHERE id=%s", (nxt["id"],))
    set_mission(c, nxt["id"], "in_progress")
    add_job(c, "develop", nxt["id"], 1, {"instructions": plan.get("developer_task") or nxt["request"],
                                         "acceptance": plan.get("acceptance_criteria", []),
                                         "base_branch": None, "correction": False})


def after_mission_settled(c):
    """Called when a mission leaves the active set: stop unless the owner enabled auto-continue."""
    loop = db.get_setting(c, "loop")
    if loop["state"] == "running" and not loop.get("auto_continue"):
        set_loop(c, "paused", "manager: mission finished; auto-continue is off, waiting for owner")
