import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import generate


class GenerateTests(unittest.TestCase):
    def test_parse_ts_normalizes_utc_and_local_timestamps(self):
        t = generate.parse_ts("2026-09-25T00:00:00Z")
        self.assertIsNotNone(t)
        self.assertIsNone(generate.parse_ts("not-a-timestamp"))

    def test_never_run_dated_job_is_flagged_after_grace(self):
        old = "2026-09-20T00:00:00"
        jobs = [{"name":"new-job","schedule":"every 6h","enabled":True,"required":True,"created_at":old,"id":"new"}]
        rows = []
        result = generate.anomalies(jobs, rows, never_run_grace_hours=24)
        self.assertTrue(any("never run" in item[1] for item in result))

    def test_disabled_optional_job_is_not_anomaly(self):
        jobs = [{"name":"paused-job","schedule":"daily","enabled":False,"required":False,"created_at":"","id":"paused"}]
        result = generate.anomalies(jobs, [])
        self.assertTrue(any(item[0] == "ok" for item in result))

    def test_humanize_known_errors(self):
        self.assertEqual(generate.humanize("failed", "429 rate limit"), "Failed – rate limited")
        self.assertEqual(generate.humanize("failed", "401 unauthorized"), "Failed – credentials rejected")
        self.assertEqual(generate.humanize("succeeded"), "Completed")

    def test_success_rates_uses_most_recent_rows(self):
        rows = [
            {"job_id": "a", "status": "succeeded"},
            {"job_id": "a", "status": "failed"},
            {"job_id": "a", "status": "succeeded"},
            {"job_id": "a", "status": "succeeded"},
        ]
        stats = generate.success_rates(rows, min_runs=3)
        self.assertEqual(stats["a"]["total"], 4)
        self.assertEqual(stats["a"]["ok"], 3)
        self.assertEqual(stats["a"]["rate"], 75)

    def test_recent_executions_handles_missing_optional_columns(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "executions.db"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE executions (job_id TEXT, status TEXT, started_at TEXT)")
            conn.execute("INSERT INTO executions VALUES ('job-1','succeeded','2026-09-24T08:00:00')")
            conn.commit()
            conn.close()

            rows = generate.recent_executions(str(db))
            self.assertEqual(rows[0]["job_id"], "job-1")
            self.assertEqual(rows[0]["status"], "succeeded")
            self.assertIsNone(rows[0]["error"])

    def test_web_assets_are_present_and_linked(self):
        root = Path(__file__).resolve().parent
        index = (root / "site" / "index.html").read_text(encoding="utf-8")
        demo = (root / "site" / "demo.html").read_text(encoding="utf-8")
        self.assertIn('href="/demo.html"', index)
        self.assertIn("Sample data", demo)
        self.assertNotIn("undefined", index.lower())
        self.assertNotIn("undefined", demo.lower())

    def test_mcp_source_lives_under_sources_config(self):
        self.assertIn("mcp_jsonl", generate.DEFAULT_CONFIG["sources"])
        self.assertNotIn("mcp_jsonl", {k:v for k,v in generate.DEFAULT_CONFIG.items() if k != "sources"})

    def test_missing_core_sources_are_unknown_not_all_clear(self):
        with tempfile.TemporaryDirectory() as td:
            missing = str(Path(td) / "missing")
            findings = generate.source_health({
                "cron_jobs_glob": missing + "*.json",
                "executions_db": missing + ".db",
                "sessions_dir": missing + "-sessions",
                "mcp_jsonl": missing + ".jsonl",
            })
            messages = " ".join(item[1] for item in findings)
            self.assertIn("UNKNOWN", messages)
            self.assertEqual(len(findings), 4)

    def test_legacy_top_level_ack_db_is_migrated(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.json"
            p.write_text(json.dumps({"ack_db": str(Path(td) / "acks.db")}))
            cfg = generate.load_config(str(p))
            self.assertEqual(cfg["sources"]["ack_db"], str(Path(td) / "acks.db"))

    def test_load_cron_jobs_deduplicates_by_name(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "jobs.json"
            p.write_text(json.dumps({"jobs": [
                {"name": "A", "enabled": True, "schedule": {"display": "daily"}},
                {"name": "A", "enabled": False, "schedule": {"display": "daily"}},
                {"name": "B", "enabled": True, "schedule": {"display": "every 6h"}},
            ]}))
            jobs = generate.load_cron_jobs(str(p))
            self.assertEqual([j["name"] for j in jobs], ["A", "B"])

    def test_anomalies_detect_overdue_job(self):
        jobs = [{"name": "Digest", "id": "j1", "enabled": True, "schedule": "every 1h"}]
        old = (generate.datetime.now() - generate.timedelta(hours=4)).isoformat()
        anomalies = generate.anomalies(jobs, [{"job_id": "j1", "status": "succeeded", "started_at": old}])
        self.assertTrue(any("overdue" in item[1] for item in anomalies))

    def test_anomalies_do_not_flag_old_failure_after_success(self):
        jobs = [{"name": "Digest", "id": "j1", "enabled": True, "schedule": "daily"}]
        rows = [
            {"job_id": "j1", "status": "succeeded", "started_at": "2026-09-24T08:00:00"},
            {"job_id": "j1", "status": "failed", "started_at": "2026-09-23T08:00:00", "error": "auth"},
            {"job_id": "j1", "status": "failed", "started_at": "2026-09-22T08:00:00", "error": "auth"},
        ]
        anomalies = generate.anomalies(jobs, rows)
        self.assertFalse(any("auth failing" in item[1] for item in anomalies))


    def test_missing_source_cannot_be_acknowledged_into_all_clear(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            missing = str(root / "missing")
            ack_db = root / "acks.db"
            conn = sqlite3.connect(ack_db)
            conn.execute("CREATE TABLE acks(key TEXT PRIMARY KEY, ts TEXT)")
            finding = generate.source_health({"cron_jobs_glob": missing + "*.json"})[0]
            conn.execute("INSERT INTO acks VALUES (?,?)", (finding[2], "2026-10-05T00:00:00"))
            conn.commit()
            conn.close()
            cfg = json.loads(json.dumps(generate.DEFAULT_CONFIG))
            cfg["sources"] = {
                "cron_jobs_glob": missing + "*.json",
                "executions_db": None,
                "sessions_dir": None,
                "leads_db": None,
                "leads_query": None,
                "leads_label": "Active items",
                "mcp_jsonl": None,
                "ack_db": str(ack_db),
            }
            out = root / "dashboard.html"
            generate.build(cfg, str(out))
            rendered = out.read_text(encoding="utf-8")
            self.assertIn("UNKNOWN", rendered)
            self.assertNotIn("All clear", rendered)


if __name__ == "__main__":
    unittest.main()
