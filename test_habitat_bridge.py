import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from agentscope_habitat import load_habitat_snapshot, render_habitat_panel
from habitat.schema import Action, Habitat, Job
from habitat.store import Store


class HabitatBridgeTests(unittest.TestCase):
    def test_missing_database_is_unknown_not_healthy(self):
        with tempfile.TemporaryDirectory() as td:
            result = load_habitat_snapshot(str(Path(td) / "missing.db"))
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "database_missing")
        self.assertIn("UNKNOWN", render_habitat_panel(result))

    def test_reads_habitat_state_and_ledger_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "habitat.db"
            store = Store(db)
            store.save_habitat(Habitat("h1", "Crew Alpha"))
            store.save_job(Job("j1", "h1", "Nightly audit", enabled=True))
            store.close()

            before = db.read_bytes()
            result = load_habitat_snapshot(str(db))
            after = db.read_bytes()

        self.assertTrue(result["available"])
        self.assertEqual(result["name"], "Crew Alpha")
        self.assertEqual(result["jobs_total"], 1)
        self.assertEqual(result["jobs_enabled"], 1)
        self.assertEqual(result["ledger_integrity"], "intact")
        self.assertEqual(before, after)

    def test_tampered_action_ledger_is_reported_as_failed(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "habitat.db"
            store = Store(db)
            store.save_habitat(Habitat("h1", "Crew Alpha"))
            store.save_action(Action(
                "a1", "h1", datetime.now(timezone.utc), "agent",
                "completed_task", "ok",
            ))
            store.close()

            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE action_integrity SET hash=?", ("0" * 64,))
                conn.commit()

            result = load_habitat_snapshot(str(db))

        self.assertTrue(result["available"])
        self.assertEqual(result["ledger_integrity"], "failed")
        self.assertIn("FAILED", render_habitat_panel(result))

    def test_dashboard_escapes_habitat_name(self):
        panel = render_habitat_panel({
            "available": True, "name": "<script>alert(1)</script>",
            "status": "healthy", "jobs_total": 0, "jobs_enabled": 0,
            "active_signals": {}, "claims": {}, "ledger_integrity": "intact",
        })
        self.assertNotIn("<script>", panel)
        self.assertIn("&lt;script&gt;", panel)


if __name__ == "__main__":
    unittest.main()
