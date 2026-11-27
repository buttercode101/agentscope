import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import generate


class SourceDiagnosticsTests(unittest.TestCase):
    def test_reports_ready_sources_without_mutating_them(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "jobs.json").write_text(json.dumps({"jobs": []}), encoding="utf-8")
            db = root / "executions.db"
            with sqlite3.connect(db) as connection:
                connection.execute("CREATE TABLE executions (job_id TEXT, status TEXT, started_at TEXT, finished_at TEXT, error TEXT)")
            sessions = root / "sessions"
            sessions.mkdir()
            (sessions / "session.json").write_text("{}", encoding="utf-8")
            mcp = root / "tools.jsonl"
            mcp.write_text('{"tool":"search","ok":true}\n', encoding="utf-8")
            before = db.stat().st_size

            rows = generate.source_diagnostics({
                "cron_jobs_glob": str(root / "jobs*.json"),
                "executions_db": str(db),
                "sessions_dir": str(sessions),
                "mcp_jsonl": str(mcp),
                "leads_db": None,
                "habitat_db": None,
            })

            by_key = {row["key"]: row for row in rows}
            self.assertEqual(by_key["cron_jobs_glob"]["status"], "ready")
            self.assertEqual(by_key["executions_db"]["status"], "ready")
            self.assertEqual(by_key["sessions_dir"]["status"], "ready")
            self.assertEqual(by_key["mcp_jsonl"]["status"], "ready")
            self.assertEqual(by_key["leads_db"]["status"], "not configured")
            self.assertEqual(db.stat().st_size, before)

    def test_missing_configured_core_sources_are_actionable_errors(self):
        with tempfile.TemporaryDirectory() as td:
            missing = str(Path(td) / "not-here")
            rows = generate.source_diagnostics({
                "cron_jobs_glob": missing + "*.json",
                "executions_db": missing + ".db",
                "sessions_dir": missing + "-sessions",
            })
            self.assertEqual([row["status"] for row in rows[:3]], ["missing", "missing", "missing"])
            self.assertTrue(all(row["detail"] for row in rows))

    def test_execution_database_without_required_schema_is_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "executions.db"
            with sqlite3.connect(db) as connection:
                connection.execute("CREATE TABLE unrelated (id TEXT)")
            rows = generate.source_diagnostics({"executions_db": str(db)})
            row = next(item for item in rows if item["key"] == "executions_db")
            self.assertEqual(row["status"], "invalid")
            self.assertIn("executions table", row["detail"])
            findings = generate.source_health({"executions_db": str(db)})
            self.assertTrue(any("run health is UNKNOWN" in item[1] for item in findings))

    def test_malformed_job_json_is_not_reported_ready(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "jobs.json"
            path.write_text("{broken", encoding="utf-8")
            rows = generate.source_diagnostics({"cron_jobs_glob": str(path)})
            row = next(item for item in rows if item["key"] == "cron_jobs_glob")
            self.assertEqual(row["status"], "invalid")
            self.assertIn("valid job-definition JSON", row["detail"])

    def test_empty_and_invalid_mcp_jsonl_are_not_reported_ready(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tools.jsonl"
            path.write_text("  \n", encoding="utf-8")
            empty = generate.source_diagnostics({"mcp_jsonl": str(path)})
            self.assertEqual(next(row for row in empty if row["key"] == "mcp_jsonl")["status"], "empty")
            path.write_text("not-json\n", encoding="utf-8")
            invalid = generate.source_diagnostics({"mcp_jsonl": str(path)})
            self.assertEqual(next(row for row in invalid if row["key"] == "mcp_jsonl")["status"], "invalid")

    def test_cli_check_does_not_generate_dashboard(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "config.json"
            config.write_text(json.dumps({"sources": {
                "cron_jobs_glob": str(root / "missing*.json"),
                "executions_db": None,
                "sessions_dir": None,
            }}), encoding="utf-8")
            output = root / "must-not-exist.html"
            result = subprocess.run(
                [sys.executable, str(Path(generate.__file__)), "--config", str(config),
                 "--check", "--output", str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("ACTION REQUIRED", result.stdout)
            self.assertIn("Scheduled job definitions", result.stdout)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
