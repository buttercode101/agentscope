"""Read-only bridge from AgentScope to Habitat's local evidence database."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from habitat.schema import Action
from habitat.store import Store


def _read_json_object(value):
    decoded = json.loads(value or "{}")
    return decoded if isinstance(decoded, dict) else {}


def _verify_ledger(conn):
    marker = conn.execute(
        "SELECT value FROM schema_meta WHERE key='action_integrity_initialized'"
    ).fetchone()
    if not marker or marker[0] != "1":
        return "unknown"
    rows = conn.execute(
        "SELECT ai.seq, ai.action_id, ai.prev_hash, ai.hash, a.* "
        "FROM action_integrity ai JOIN action a ON a.id=ai.action_id ORDER BY ai.seq"
    ).fetchall()
    action_count = conn.execute("SELECT COUNT(*) FROM action").fetchone()[0]
    if len(rows) != action_count:
        return "failed"
    previous = None
    for row in rows:
        try:
            action = Action(
                row["id"], row["habitat_id"], datetime.fromisoformat(row["timestamp"]),
                row["actor"], row["action"], row["status"], row["job_id"],
                _read_json_object(row["details"]), row["run_id"],
            )
            if row["prev_hash"] != previous or row["hash"] != Store._action_hash(action, previous):
                return "failed"
            previous = row["hash"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return "failed"
    return "intact"


def load_habitat_snapshot(database_path):
    """Return a bounded, read-only operational summary; never mutate Habitat state."""
    if not database_path:
        return None
    path = Path(database_path).expanduser()
    if not path.is_file():
        return {"available": False, "reason": "database_missing", "path": str(path)}
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=2)
        conn.row_factory = sqlite3.Row
        try:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            required = {"habitat", "job", "signal", "claim", "action", "action_integrity", "schema_meta"}
            if not required.issubset(tables):
                return {"available": False, "reason": "incomplete_schema", "path": str(path)}
            habitat = conn.execute(
                "SELECT id, name, status, model, updated_at FROM habitat LIMIT 1"
            ).fetchone()
            if habitat is None:
                return {"available": False, "reason": "not_initialized", "path": str(path)}
            jobs = conn.execute(
                "SELECT COUNT(*) total, SUM(CASE WHEN enabled=1 THEN 1 ELSE 0 END) enabled "
                "FROM job WHERE habitat_id=?", (habitat["id"],)
            ).fetchone()
            signals = conn.execute(
                "SELECT severity, COUNT(*) total FROM signal WHERE habitat_id=? "
                "AND resolved_at IS NULL GROUP BY severity", (habitat["id"],)
            ).fetchall()
            claims = conn.execute(
                "SELECT status, COUNT(*) total FROM claim WHERE habitat_id=? GROUP BY status",
                (habitat["id"],)
            ).fetchall()
            return {
                "available": True,
                "name": habitat["name"],
                "status": habitat["status"],
                "model": habitat["model"],
                "updated_at": habitat["updated_at"],
                "jobs_total": jobs["total"] or 0,
                "jobs_enabled": jobs["enabled"] or 0,
                "active_signals": {row["severity"]: row["total"] for row in signals},
                "claims": {row["status"]: row["total"] for row in claims},
                "ledger_integrity": _verify_ledger(conn),
            }
        finally:
            conn.close()
    except (OSError, sqlite3.Error, ValueError) as exc:
        return {"available": False, "reason": "database_unreadable", "detail": str(exc)[:160], "path": str(path)}


def render_habitat_panel(snapshot):
    """Render an escaped, read-only Habitat summary for the generated dashboard."""
    if snapshot is None:
        return ""
    import html

    esc = html.escape
    if not snapshot.get("available"):
        reason = snapshot.get("reason", "unknown")
        return (
            '<div class="panel attn"><h2>Habitat evidence runtime</h2>'
            '<div class="anom"><span class="badge" style="color:#b91c1c;background:#fee2e2">UNKNOWN</span> '
            'Habitat state unavailable (' + esc(reason) + '). No assurance status is inferred.</div></div>'
        )
    claims = snapshot.get("claims", {})
    signals = snapshot.get("active_signals", {})
    signal_count = sum(signals.values())
    ledger = snapshot.get("ledger_integrity", "unknown")
    ledger_label = {"intact": "INTACT", "failed": "FAILED", "unknown": "UNKNOWN"}.get(ledger, "UNKNOWN")
    ledger_color = "#15803d" if ledger == "intact" else "#b91c1c"
    return (
        '<div class="panel"><h2>Habitat evidence runtime</h2>'
        '<div class="anom"><strong>' + esc(snapshot.get("name", "Habitat")) + '</strong> · runtime '
        + esc(snapshot.get("status", "unknown")) + ' · '
        + str(snapshot.get("jobs_enabled", 0)) + '/' + str(snapshot.get("jobs_total", 0)) + ' jobs enabled</div>'
        '<div class="anom">Active signals: ' + str(signal_count)
        + ' · Claims recorded: ' + str(sum(claims.values()))
        + ' (verified ' + str(claims.get("verified", 0))
        + ', rejected ' + str(claims.get("rejected", 0))
        + ', inconclusive ' + str(claims.get("inconclusive", 0)) + ')</div>'
        '<div class="anom">Action ledger: <span class="badge" style="color:' + ledger_color
        + ';background:#e5e7eb">' + ledger_label + '</span>'
        + (' · Active critical signals: ' + str(signals.get("critical", 0)) if signals.get("critical") else '')
        + (' · Active warnings: ' + str(signals.get("warning", 0)) if signals.get("warning") else '')
        + '</div><div class="mut" style="font-size:11px;margin-top:8px">Read-only snapshot. Recorded claim verdicts are not independently re-verified by this dashboard.</div></div>'
    )
