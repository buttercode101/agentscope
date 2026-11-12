from datetime import datetime, timedelta, timezone
import json
import sqlite3
from pathlib import Path

import generate

root = Path(__file__).resolve().parents[1]
site = root / "site"
fixtures = root / ".browser-fixtures"
fixtures.mkdir(exist_ok=True)

now = datetime.now(timezone.utc)
jobs_path = fixtures / "jobs.json"
jobs_path.write_text(json.dumps([{
    "id": "job-disabled",
    "name": "Disabled required job",
    "schedule": {"display": "every 6h"},
    "enabled": False,
    "required": True,
    "created_at": (now - timedelta(days=3)).isoformat(),
}], ensure_ascii=False), encoding="utf-8")

db_path = fixtures / "executions.db"
if db_path.exists():
    db_path.unlink()
with sqlite3.connect(db_path) as db:
    db.execute("""CREATE TABLE executions (
        job_id TEXT, status TEXT, started_at TEXT, finished_at TEXT, error TEXT
    )""")
    db.executemany(
        "INSERT INTO executions VALUES (?, ?, ?, ?, ?)",
        [
            ("job-disabled", "succeeded", (now - timedelta(days=2)).isoformat(), None, None),
            ("job-disabled", "succeeded", (now - timedelta(hours=2)).isoformat(), None, None),
        ],
    )

cfg = json.loads(json.dumps(generate.DEFAULT_CONFIG))
cfg["title"] = "Browser acceptance dashboard"
cfg["theme"] = "light"
cfg["sources"] = {key: None for key in cfg["sources"]}
cfg["sources"]["cron_jobs_glob"] = str(jobs_path)
cfg["sources"]["executions_db"] = str(db_path)
generate.build(cfg, str(site / "generated-dashboard-test.html"))
