import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import generate


class GenerateTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
