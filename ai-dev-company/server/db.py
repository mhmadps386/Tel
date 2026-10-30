"""Postgres persistence for the control plane.

All mission/job state lives here so the web service can restart or crash without
losing anything. Job claiming uses row locks (FOR UPDATE SKIP LOCKED), so two
workers can never take the same job.
"""

import json
import os
import threading

import psycopg
from psycopg.rows import dict_row

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS owner (
    id            INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    password_hash TEXT NOT NULL,
    must_change   BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sessions (
    id_hash     TEXT PRIMARY KEY,
    csrf        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    user_agent  TEXT
);
CREATE TABLE IF NOT EXISTS login_attempts (
    id         BIGSERIAL PRIMARY KEY,
    ip         TEXT NOT NULL,
    ok         BOOLEAN NOT NULL,
    at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS worker_tokens (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    token_hash  TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked     BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS workers (
    id          TEXT PRIMARY KEY,
    token_id    BIGINT REFERENCES worker_tokens(id),
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
    info        JSONB NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS projects (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    disposable  BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS missions (
    id           BIGSERIAL PRIMARY KEY,
    project_id   BIGINT NOT NULL REFERENCES projects(id),
    title        TEXT NOT NULL,
    request      TEXT NOT NULL,
    status       TEXT NOT NULL,
    round        INT NOT NULL DEFAULT 0,
    max_rounds   INT NOT NULL DEFAULT 5 CHECK (max_rounds BETWEEN 1 AND 5),
    plan         JSONB,
    branch       TEXT,
    outcome      JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS jobs (
    id            BIGSERIAL PRIMARY KEY,
    mission_id    BIGINT REFERENCES missions(id),
    kind          TEXT NOT NULL,       -- plan | develop | qa | review | merge | login
    round         INT NOT NULL DEFAULT 0,
    spec          JSONB NOT NULL DEFAULT '{}',
    depends_on    BIGINT[] NOT NULL DEFAULT '{}',
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending|running|done|failed|cancelled
    attempts      INT NOT NULL DEFAULT 0,
    max_attempts  INT NOT NULL DEFAULT 2 CHECK (max_attempts BETWEEN 1 AND 5),
    timeout_s     INT NOT NULL DEFAULT 1800 CHECK (timeout_s BETWEEN 1 AND 14400),
    worker_id     TEXT,
    lease_expires TIMESTAMPTZ,
    result        JSONB,
    errors        JSONB NOT NULL DEFAULT '[]',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    seconds       DOUBLE PRECISION NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs(status);
CREATE TABLE IF NOT EXISTS approvals (
    id          BIGSERIAL PRIMARY KEY,
    mission_id  BIGINT NOT NULL REFERENCES missions(id),
    kind        TEXT NOT NULL,         -- plan | merge
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|rejected
    payload     JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at  TIMESTAMPTZ,
    note        TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    mission_id  BIGINT,
    job_id      BIGINT,
    actor       TEXT NOT NULL,
    kind        TEXT NOT NULL,
    data        JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS events_mission_idx ON events(mission_id);
"""

DEFAULT_SETTINGS = {
    # The loop does nothing until the owner explicitly starts it (unattended execution off).
    "loop": {"state": "paused", "reason": "initial: waiting for owner to start", "auto_continue": False},
    "estop": {"active": False, "reason": None},
    "login_request": {"pending": False},
}

_local = threading.local()


def dsn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def conn():
    """One connection per thread, autocommit off; use `with tx() as c:` for writes."""
    c = getattr(_local, "conn", None)
    if c is None or c.closed:
        c = psycopg.connect(dsn(), row_factory=dict_row, autocommit=False)
        _local.conn = c
    return c


class tx:
    def __enter__(self):
        self.c = conn()
        return self.c

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.c.rollback()
        else:
            self.c.commit()
        return False


def migrate():
    with tx() as c:
        c.execute("SELECT pg_advisory_xact_lock(424242)")
        c.execute(SCHEMA)
        for key, value in DEFAULT_SETTINGS.items():
            c.execute("INSERT INTO settings(key, value) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                      (key, json.dumps(value)))
        c.execute("""INSERT INTO projects(name, description) VALUES
                     ('disposable-demo', 'Disposable copy of the demo web app. Lives only in the worker volume; never pushed or deployed.')
                     ON CONFLICT DO NOTHING""")


def get_setting(c, key):
    row = c.execute("SELECT value FROM settings WHERE key=%s", (key,)).fetchone()
    return row["value"] if row else DEFAULT_SETTINGS.get(key)


def set_setting(c, key, value):
    c.execute("INSERT INTO settings(key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
              (key, json.dumps(value)))


def event(c, actor, _kind, mission_id=None, job_id=None, **data):
    from .redact import redact_obj
    c.execute("INSERT INTO events(actor, kind, mission_id, job_id, data) VALUES (%s,%s,%s,%s,%s)",
              (actor, _kind, mission_id, job_id, json.dumps(redact_obj(data), default=str)))


def j(value):
    return json.dumps(value)
