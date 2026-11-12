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

    def test_landing_has_keyboard_navigation_affordances(self):
        root = Path(__file__).resolve().parent
        index = (root / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="skip-link"', index)
        self.assertIn('id="main-content"', index)
        self.assertIn(':focus-visible', index)
        self.assertIn('prefers-reduced-motion', index)

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

    def test_empty_mcp_source_is_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "mcp.jsonl"
            p.write_text("")
            findings = generate.source_health({"mcp_jsonl": str(p)})
            self.assertTrue(any("UNKNOWN" in item[1] and "empty" in item[1] for item in findings))

    def test_whitespace_only_mcp_source_is_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "mcp.jsonl"
            p.write_text("   \n\t\n")
            findings = generate.source_health({"mcp_jsonl": str(p)})
            self.assertTrue(any("UNKNOWN" in item[1] and "empty" in item[1] for item in findings))

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


    def test_proof_index_wraps_long_digest_metadata(self):
        root = Path(__file__).resolve().parent
        proofs = (root / "site" / "proofs.html").read_text(encoding="utf-8")
        self.assertIn(".meta{color:var(--mut);font-size:12px;overflow-wrap:anywhere}", proofs)


    def test_public_pages_share_the_product_design_system_and_accessibility(self):
        root = Path(__file__).resolve().parent
        index = (root / "site" / "index.html").read_text(encoding="utf-8")
        demo = (root / "site" / "demo.html").read_text(encoding="utf-8")
        proofs = (root / "site" / "proofs.html").read_text(encoding="utf-8")

        for page in (index, demo, proofs):
            self.assertIn("--bg:#f4f5f1", page)
            self.assertIn("#536f59", page)
            self.assertIn("Inter,ui-sans-serif,system-ui", page)
            self.assertIn("prefers-reduced-motion", page)
            self.assertIn(":focus-visible", page)

        self.assertIn('href="#dashboard-main"', demo)
        self.assertIn('id="dashboard-main"', demo)
        self.assertIn('href="#proof-main"', proofs)
        self.assertIn('id="proof-main"', proofs)
        self.assertIn("data-days", demo)
        self.assertIn("document.querySelectorAll('.filter')", demo)
        self.assertIn("crypto.subtle.digest", proofs)

    def test_generated_dashboard_uses_shared_ui_and_keyboard_landmarks(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = json.loads(json.dumps(generate.DEFAULT_CONFIG))
            cfg["sources"] = {key: None for key in cfg["sources"]}
            cfg["sources"]["leads_label"] = "Active items"
            output = Path(td) / "dashboard.html"

            generate.build(cfg, str(output))
            rendered = output.read_text(encoding="utf-8")

            self.assertIn("--bg:#f4f5f1", rendered)
            self.assertIn("--acc:#536f59", rendered)
            self.assertIn('class="skip-link"', rendered)
            self.assertIn('id="dashboard-main"', rendered)
            self.assertIn('role="group" aria-label="Time range filter"', rendered)
            self.assertIn("Copy status summary", rendered)
            self.assertIn("prefers-reduced-motion", rendered)


    def test_demo_mobile_tables_keep_cadence_and_action_status_visible(self):
        root = Path(__file__).resolve().parent
        demo = (root / "site" / "demo.html").read_text(encoding="utf-8")
        self.assertIn('class="table-scroll" role="region"', demo)
        self.assertNotIn(".table th:nth-child(2),.table td:nth-child(2){display:none}", demo)
        self.assertNotIn(".act span:last-child{display:none}", demo)
        self.assertIn('aria-pressed="true"', demo)
        self.assertIn("setAttribute('aria-pressed','false')", demo)
        self.assertIn("setAttribute('aria-pressed','true')", demo)

    def test_proof_explorer_checks_manifest_pinned_digest_and_handles_bad_ledger(self):
        root = Path(__file__).resolve().parent
        proofs = (root / "site" / "proofs.html").read_text(encoding="utf-8")
        self.assertIn("async function verify(bundle,expectedDigest)", proofs)
        self.assertIn("Manifest-pinned content hash mismatch", proofs)
        self.assertIn("Embedded content hash mismatch", proofs)
        self.assertIn('bundle.ledger&&bundle.ledger.integrity', proofs)
        self.assertIn("Proof URL must remain on this site", proofs)
        self.assertIn("Proof could not be verified:", proofs)


if __name__ == "__main__":
    unittest.main()
