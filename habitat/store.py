"""SQLite persistence, migrations, audit and agent identity."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from .claims import Claim
from .schema import Action, Habitat, Job, Signal

SCHEMA_VERSION = 3
PBKDF2_ITERATIONS = 600_000
SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS habitat (id TEXT PRIMARY KEY, name TEXT NOT NULL, model TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS job (id TEXT PRIMARY KEY, habitat_id TEXT NOT NULL, name TEXT NOT NULL, schedule TEXT, enabled INTEGER NOT NULL, command TEXT, last_run_at TEXT, last_status TEXT, failure_streak INTEGER NOT NULL, last_error TEXT);
CREATE TABLE IF NOT EXISTS signal (id TEXT PRIMARY KEY, habitat_id TEXT NOT NULL, job_id TEXT, type TEXT NOT NULL, severity TEXT NOT NULL, code TEXT NOT NULL, message TEXT NOT NULL, detected_at TEXT NOT NULL, resolved_at TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS action (id TEXT PRIMARY KEY, habitat_id TEXT NOT NULL, job_id TEXT, timestamp TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL, details TEXT NOT NULL, run_id TEXT);
CREATE TABLE IF NOT EXISTS claim (id TEXT PRIMARY KEY, habitat_id TEXT NOT NULL, job_id TEXT, claim TEXT NOT NULL, action TEXT, expected_status TEXT NOT NULL, created_at TEXT NOT NULL, verified_at TEXT, status TEXT NOT NULL, evidence TEXT NOT NULL, run_id TEXT);
CREATE TABLE IF NOT EXISTS event (id TEXT PRIMARY KEY, habitat_id TEXT NOT NULL, type TEXT NOT NULL, received_at TEXT NOT NULL, signature_valid INTEGER NOT NULL, payload TEXT NOT NULL, correlation_id TEXT, agent_id TEXT);
CREATE TABLE IF NOT EXISTS agent (id TEXT PRIMARY KEY, habitat_id TEXT NOT NULL, name TEXT NOT NULL, enabled INTEGER NOT NULL, permissions TEXT NOT NULL, secret_hash TEXT, created_at TEXT NOT NULL, last_seen_at TEXT);
CREATE INDEX IF NOT EXISTS idx_action_run ON action(run_id);
CREATE INDEX IF NOT EXISTS idx_action_job_action_run ON action(job_id, action, run_id, status);
CREATE TABLE IF NOT EXISTS action_integrity (seq INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT NOT NULL UNIQUE, prev_hash TEXT, hash TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_claim_run ON claim(run_id);
CREATE INDEX IF NOT EXISTS idx_event_received ON event(received_at);
"""


def _dt(value):
    return datetime.fromisoformat(value) if value else None


def _json_object(value: str, field: str) -> dict[str, Any]:
    """Decode persisted JSON and fail with a useful storage error."""
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"corrupt_json:{field}") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError(f"invalid_json_object:{field}")
    return decoded


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=10000")
        self._transaction_depth = 0
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    @contextmanager
    def transaction(self, immediate=False):
        """Run a group of writes atomically; nested calls reuse the transaction."""
        outer = self._transaction_depth == 0
        if outer:
            self.conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        self._transaction_depth += 1
        try:
            yield self
            if outer:
                self.conn.commit()
        except Exception:
            if outer:
                self.conn.rollback()
            raise
        finally:
            self._transaction_depth -= 1

    def _migrate(self):
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(event)")}
        if "agent_id" not in cols:
            self.conn.execute("ALTER TABLE event ADD COLUMN agent_id TEXT")
        self.conn.execute("INSERT OR IGNORE INTO schema_meta(key,value) VALUES('version','1')")
        self.conn.execute("UPDATE schema_meta SET value=? WHERE key='version'", (str(SCHEMA_VERSION),))
        marker = self.conn.execute("SELECT value FROM schema_meta WHERE key='action_integrity_initialized'").fetchone()
        if marker is None:
            self._bootstrap_action_integrity()
            self.conn.execute("INSERT INTO schema_meta(key,value) VALUES('action_integrity_initialized','1')")

    def close(self):
        self.conn.close()

    @staticmethod
    def _action_payload(a):
        return {"id": a.id, "habitat_id": a.habitat_id, "job_id": a.job_id, "timestamp": a.timestamp.isoformat(), "actor": a.actor, "action": a.action, "status": a.status, "details": a.details, "run_id": a.run_id}

    @classmethod
    def _action_hash(cls, a, prev_hash):
        payload = {"prev_hash": prev_hash, "action": cls._action_payload(a)}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

    def _bootstrap_action_integrity(self):
        if self.conn.execute("SELECT 1 FROM action_integrity LIMIT 1").fetchone():
            return
        rows = self.conn.execute("SELECT * FROM action ORDER BY timestamp,id").fetchall()
        prev = None
        for r in rows:
            a = Action(r["id"], r["habitat_id"], _dt(r["timestamp"]), r["actor"], r["action"], r["status"], r["job_id"], _json_object(r["details"], "action.details"), r["run_id"])
            digest = self._action_hash(a, prev)
            self.conn.execute("INSERT INTO action_integrity(action_id,prev_hash,hash) VALUES(?,?,?)", (a.id, prev, digest))
            prev = digest

    def close_and_commit(self):
        self.conn.commit()
        self.close()

    def save_habitat(self, h):
        self.conn.execute("INSERT OR REPLACE INTO habitat VALUES (?,?,?,?,?,?)", (h.id, h.name, h.model, h.created_at.isoformat(), h.updated_at.isoformat(), h.status))
        if self._transaction_depth == 0:
            self.conn.commit()

    def save_job(self, j):
        self.conn.execute("INSERT OR REPLACE INTO job VALUES (?,?,?,?,?,?,?,?,?,?)", (j.id, j.habitat_id, j.name, j.schedule, int(j.enabled), j.command, j.last_run_at.isoformat() if j.last_run_at else None, j.last_status, j.failure_streak, j.last_error))
        if self._transaction_depth == 0:
            self.conn.commit()

    def save_signal(self, s):
        self.conn.execute("INSERT OR REPLACE INTO signal VALUES (?,?,?,?,?,?,?,?,?,?)", (s.id, s.habitat_id, s.job_id, s.type, s.severity, s.code, s.message, s.detected_at.isoformat(), s.resolved_at.isoformat() if s.resolved_at else None, json.dumps(s.data)))
        if self._transaction_depth == 0:
            self.conn.commit()

    def save_action(self, a):
        outer = self._transaction_depth == 0
        if outer:
            self.conn.execute("BEGIN IMMEDIATE")
        try:
            prev = self.conn.execute("SELECT hash FROM action_integrity ORDER BY seq DESC LIMIT 1").fetchone()
            prev_hash = prev[0] if prev else None
            digest = self._action_hash(a, prev_hash)
            self.conn.execute("INSERT INTO action VALUES (?,?,?,?,?,?,?,?,?)", (a.id, a.habitat_id, a.job_id, a.timestamp.isoformat(), a.actor, a.action, a.status, json.dumps(a.details), a.run_id))
            self.conn.execute("INSERT INTO action_integrity(action_id,prev_hash,hash) VALUES(?,?,?)", (a.id, prev_hash, digest))
            if outer:
                self.conn.commit()
        except Exception:
            if outer:
                self.conn.rollback()
            raise

    def habitat(self):
        r = self.conn.execute("SELECT * FROM habitat LIMIT 1").fetchone()
        if not r:
            raise RuntimeError("No Habitat initialized")
        return Habitat(r["id"], r["name"], r["model"], _dt(r["created_at"]), _dt(r["updated_at"]), r["status"])

    def jobs(self):
        return [Job(r["id"], r["habitat_id"], r["name"], r["schedule"], bool(r["enabled"]), r["command"], _dt(r["last_run_at"]), r["last_status"], r["failure_streak"], r["last_error"]) for r in self.conn.execute("SELECT * FROM job ORDER BY name")]

    def signals(self):
        return [Signal(r["id"], r["habitat_id"], r["type"], r["severity"], r["code"], r["message"], r["job_id"], _dt(r["detected_at"]), _dt(r["resolved_at"]), _json_object(r["data"], "signal.data")) for r in self.conn.execute("SELECT * FROM signal ORDER BY detected_at DESC")]

    def actions(self, limit=50):
        return [Action(r["id"], r["habitat_id"], _dt(r["timestamp"]), r["actor"], r["action"], r["status"], r["job_id"], _json_object(r["details"], "action.details"), r["run_id"]) for r in self.conn.execute("SELECT * FROM action ORDER BY timestamp DESC LIMIT ?", (limit,))]

    def actions_for_run(self, run_id):
        if not run_id:
            return []
        return [Action(r["id"], r["habitat_id"], _dt(r["timestamp"]), r["actor"], r["action"], r["status"], r["job_id"], _json_object(r["details"], "action.details"), r["run_id"]) for r in self.conn.execute("SELECT * FROM action WHERE run_id=? ORDER BY timestamp,id", (run_id,))]

    def matching_actions(self, habitat_id, job_id=None, action=None, run_id=None, limit=5000):
        clauses = ["habitat_id=?"]
        params: list[Any] = [habitat_id]
        if job_id is not None:
            clauses.append("job_id=?"); params.append(job_id)
        if action is not None:
            clauses.append("action=?"); params.append(action)
        if run_id is not None:
            clauses.append("run_id=?"); params.append(run_id)
        sql = "SELECT * FROM action WHERE " + " AND ".join(clauses) + " ORDER BY timestamp,id LIMIT ?"
        params.append(limit)
        return [Action(r["id"], r["habitat_id"], _dt(r["timestamp"]), r["actor"], r["action"], r["status"], r["job_id"], _json_object(r["details"], "action.details"), r["run_id"]) for r in self.conn.execute(sql, params)]

    def get_claim(self, claim_id):
        r = self.conn.execute("SELECT * FROM claim WHERE id=?", (claim_id,)).fetchone()
        if not r:
            return None
        return Claim(r["id"], r["habitat_id"], r["job_id"], r["claim"], r["action"], r["expected_status"], _dt(r["created_at"]), _dt(r["verified_at"]), r["status"], _json_object(r["evidence"], "claim.evidence"), r["run_id"])

    def save_claim(self, c):
        self.conn.execute("INSERT OR REPLACE INTO claim VALUES (?,?,?,?,?,?,?,?,?,?,?)", (c.id, c.habitat_id, c.job_id, c.claim, c.action, c.expected_status, c.created_at.isoformat(), c.verified_at.isoformat() if c.verified_at else None, c.status, json.dumps(c.evidence), c.run_id))
        if self._transaction_depth == 0:
            self.conn.commit()

    def claims(self, limit=100):
        return [Claim(r["id"], r["habitat_id"], r["job_id"], r["claim"], r["action"], r["expected_status"], _dt(r["created_at"]), _dt(r["verified_at"]), r["status"], _json_object(r["evidence"], "claim.evidence"), r["run_id"]) for r in self.conn.execute("SELECT * FROM claim ORDER BY created_at DESC LIMIT ?", (limit,))]

    def save_event(self, event_id, habitat_id, event_type, received_at, signature_valid, payload, agent_id=None):
        outer = self._transaction_depth == 0
        if outer:
            self.conn.execute("BEGIN IMMEDIATE")
        try:
            existing = self.conn.execute("SELECT habitat_id,type,payload,agent_id FROM event WHERE id=?", (event_id,)).fetchone()
            if existing:
                same = existing["habitat_id"] == habitat_id and existing["type"] == event_type and json.loads(existing["payload"]) == payload and existing["agent_id"] == agent_id
                if outer:
                    self.conn.commit()
                if not same:
                    raise ValueError("event_id_conflict")
                return False
            cur = self.conn.execute("INSERT INTO event VALUES (?,?,?,?,?,?,?,?)", (event_id, habitat_id, event_type, received_at, int(signature_valid), json.dumps(payload, sort_keys=True, allow_nan=False), payload.get("correlation_id") or payload.get("run_id"), agent_id))
            if outer:
                self.conn.commit()
            return cur.rowcount == 1
        except Exception:
            if outer:
                self.conn.rollback()
            raise

    def events(self, limit=100):
        return [{"id": r["id"], "habitat_id": r["habitat_id"], "type": r["type"], "received_at": r["received_at"], "signature_valid": bool(r["signature_valid"]), "payload": _json_object(r["payload"], "event.payload"), "correlation_id": r["correlation_id"], "agent_id": r["agent_id"]} for r in self.conn.execute("SELECT * FROM event ORDER BY received_at DESC LIMIT ?", (limit,))]

    def active_signals(self, limit=100):
        return [x for x in self.signals() if x.resolved_at is None][:limit]

    @staticmethod
    def hash_secret(secret):
        """Return a versioned, salted password-style hash for agent secrets."""
        if not isinstance(secret, str) or not secret:
            raise ValueError("agent secret must be non-empty")
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"

    @staticmethod
    def _verify_secret(secret, stored):
        if not isinstance(secret, str) or not stored:
            return False, False
        if stored.startswith("pbkdf2_sha256$"):
            try:
                algorithm, iterations_raw, salt_hex, digest_hex = stored.split("$", 3)
                iterations = int(iterations_raw)
                if algorithm != "pbkdf2_sha256" or iterations < 100_000 or iterations > 2_000_000:
                    return False, False
                salt = bytes.fromhex(salt_hex)
                expected = bytes.fromhex(digest_hex)
                candidate = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations)
                return hmac.compare_digest(candidate, expected), False
            except (TypeError, ValueError):
                return False, False
        # Backward-compatible verification for databases created before the
        # hardened format. Successful legacy authentication is upgraded in place.
        if len(stored) == 64:
            candidate = hashlib.sha256(secret.encode("utf-8")).hexdigest()
            return hmac.compare_digest(candidate, stored), True
        return False, False

    def save_agent(self, agent_id, habitat_id, name, enabled=True, permissions=None, secret=None):
        self.conn.execute("INSERT OR REPLACE INTO agent VALUES (?,?,?,?,?,?,?,?)", (agent_id, habitat_id, name, int(enabled), json.dumps(sorted(permissions or [])), self.hash_secret(secret) if secret else None, datetime.now().astimezone().isoformat(), None))
        if self._transaction_depth == 0:
            self.conn.commit()

    def agents(self):
        return [{"id": r["id"], "habitat_id": r["habitat_id"], "name": r["name"], "enabled": bool(r["enabled"]), "permissions": json.loads(r["permissions"]), "created_at": r["created_at"], "last_seen_at": r["last_seen_at"]} for r in self.conn.execute("SELECT * FROM agent ORDER BY name")]

    def authenticate_agent(self, agent_id, secret, permission):
        r = self.conn.execute("SELECT * FROM agent WHERE id=?", (agent_id,)).fetchone()
        if not r or not r["enabled"]:
            return False
        perms = json.loads(r["permissions"])
        if permission not in perms and "*" not in perms:
            return False
        if not r["secret_hash"]:
            return False
        valid, legacy = self._verify_secret(secret, r["secret_hash"])
        if not valid:
            return False
        if legacy:
            self.conn.execute("UPDATE agent SET secret_hash=? WHERE id=?", (self.hash_secret(secret), agent_id))
        self.conn.execute("UPDATE agent SET last_seen_at=? WHERE id=?", (datetime.now().astimezone().isoformat(), agent_id))
        if self._transaction_depth == 0:
            self.conn.commit()
        return True

    def verify_action_integrity(self):
        marker = self.conn.execute("SELECT value FROM schema_meta WHERE key='action_integrity_initialized'").fetchone()
        if not marker or marker[0] != "1":
            return False
        rows = self.conn.execute("SELECT ai.seq,ai.action_id,ai.prev_hash,ai.hash,a.* FROM action_integrity ai JOIN action a ON a.id=ai.action_id ORDER BY ai.seq").fetchall()
        prev = None
        if not rows and self.conn.execute("SELECT 1 FROM action LIMIT 1").fetchone():
            return False
        if rows and len(rows) != self.conn.execute("SELECT COUNT(*) FROM action").fetchone()[0]:
            return False
        for r in rows:
            a = Action(r["id"], r["habitat_id"], _dt(r["timestamp"]), r["actor"], r["action"], r["status"], r["job_id"], _json_object(r["details"], "action.details"), r["run_id"])
            if r["prev_hash"] != prev or r["hash"] != self._action_hash(a, prev):
                return False
            prev = r["hash"]
        return True
