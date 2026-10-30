"""Owner authentication, sessions, CSRF and worker tokens.

- One owner account. The password is stored only as a scrypt hash. The first password
  comes from AIDC_INITIAL_PASSWORD_HASH (a hash, never a plaintext) and must be changed
  at first login.
- Sessions: 256-bit random id in an HttpOnly, Secure, SameSite=Strict cookie; only its
  SHA-256 is stored. 12 h lifetime. Every state-changing request needs the per-session
  CSRF token in the X-CSRF header.
- Brute force: 5 failures per client IP or 20 failures overall within 15 minutes lock login.
- Worker tokens: random, shown once in the panel, stored as SHA-256.
"""

import base64
import hashlib
import hmac
import os
import secrets

from . import db

SESSION_HOURS = 12
COOKIE = "aidc_session"
SCRYPT = {"n": 2 ** 15, "r": 8, "p": 1}


def hash_password(password):
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, maxmem=64 * 1024 * 1024, dklen=32, **SCRYPT)
    return "scrypt${n}${r}${p}${salt}${digest}".format(
        salt=base64.b64encode(salt).decode(), digest=base64.b64encode(digest).decode(), **SCRYPT)


def verify_password(password, stored):
    try:
        _, n, r, p, salt, digest = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                              maxmem=64 * 1024 * 1024, dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


def sha256(value):
    return hashlib.sha256(value.encode()).hexdigest()


def ensure_owner(c):
    if c.execute("SELECT 1 FROM owner").fetchone():
        return True
    initial = os.environ.get("AIDC_INITIAL_PASSWORD_HASH", "")
    if not initial.startswith("scrypt$"):
        return False  # panel stays locked until the operator sets a hash
    c.execute("INSERT INTO owner(id, password_hash, must_change) VALUES (1, %s, TRUE)", (initial,))
    db.event(c, "system", "owner.initialised")
    return True


def login_locked(c, ip):
    per_ip = c.execute("SELECT count(*) AS n FROM login_attempts WHERE ip=%s AND NOT ok AND at > now() - interval '15 minutes'",
                       (ip,)).fetchone()["n"]
    total = c.execute("SELECT count(*) AS n FROM login_attempts WHERE NOT ok AND at > now() - interval '15 minutes'"
                      ).fetchone()["n"]
    return per_ip >= 5 or total >= 20


def login(c, password, ip, user_agent):
    """Returns (session_id, csrf) or raises PermissionError."""
    if not ensure_owner(c):
        raise PermissionError("panel not initialised")
    if login_locked(c, ip):
        db.event(c, "system", "login.locked", ip=ip)
        c.commit()
        raise PermissionError("too many failed attempts; try again later")
    owner = c.execute("SELECT password_hash FROM owner WHERE id=1").fetchone()
    ok = verify_password(password, owner["password_hash"])
    c.execute("INSERT INTO login_attempts(ip, ok) VALUES (%s, %s)", (ip, ok))
    db.event(c, "system", "login.success" if ok else "login.failure", ip=ip)
    if not ok:
        c.commit()  # the failed attempt must survive the error rollback, or rate limiting never triggers
        raise PermissionError("invalid password")
    sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    c.execute("INSERT INTO sessions(id_hash, csrf, expires_at, user_agent) VALUES (%s,%s, now() + make_interval(hours => %s), %s)",
              (sha256(sid), csrf, SESSION_HOURS, (user_agent or "")[:200]))
    c.execute("DELETE FROM sessions WHERE expires_at < now()")
    return sid, csrf


def session(c, sid):
    if not sid:
        return None
    return c.execute("SELECT id_hash, csrf FROM sessions WHERE id_hash=%s AND expires_at > now()", (sha256(sid),)).fetchone()


def logout(c, sid):
    c.execute("DELETE FROM sessions WHERE id_hash=%s", (sha256(sid or ""),))


def change_password(c, current, new):
    owner = c.execute("SELECT password_hash FROM owner WHERE id=1").fetchone()
    if not verify_password(current, owner["password_hash"]):
        raise PermissionError("current password is wrong")
    if current == new:
        raise ValueError("new password must differ")
    c.execute("UPDATE owner SET password_hash=%s, must_change=FALSE, updated_at=now() WHERE id=1", (hash_password(new),))
    c.execute("DELETE FROM sessions")  # sign out every other session
    db.event(c, "owner", "owner.password_changed")


def create_worker_token(c, name):
    token = "aidcw_" + secrets.token_urlsafe(32)
    c.execute("INSERT INTO worker_tokens(name, token_hash) VALUES (%s, %s)", (name[:60], sha256(token)))
    db.event(c, "owner", "worker_token.created", name=name[:60])
    return token


def worker_from_token(c, token):
    if not token or not token.startswith("aidcw_"):
        return None
    return c.execute("SELECT id, name FROM worker_tokens WHERE token_hash=%s AND NOT revoked", (sha256(token),)).fetchone()
