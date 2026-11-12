from datetime import datetime, timezone
import sqlite3

from agentscope_habitat import load_habitat_snapshot
from habitat.schema import Action, Habitat, Job, Signal
from habitat.store import Store


def _seed_database(path):
    store = Store(path)
    store.save_habitat(Habitat(id="h1", name="Read-only bridge fixture"))
    store.save_job(Job(id="j1", habitat_id="h1", name="Fixture job"))
    store.save_signal(
        Signal(
            id="s1",
            habitat_id="h1",
            type="anomaly",
            severity="warning",
            code="fixture",
            message="Fixture signal",
        )
    )
    store.save_action(
        Action(
            id="a1",
            habitat_id="h1",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            actor="agent",
            action="run_job",
            status="ok",
            job_id="j1",
            details={"sample": True},
            run_id="r1",
        )
    )
    store.close()


def test_bridge_reads_healthy_habitat_database_without_mutating_it(tmp_path):
    database = tmp_path / "habitat.db"
    _seed_database(database)
    before = database.read_bytes()

    snapshot = load_habitat_snapshot(database)

    assert snapshot["available"] is True
    assert snapshot["jobs_total"] == 1
    assert snapshot["jobs_enabled"] == 1
    assert snapshot["active_signals"] == {"warning": 1}
    assert snapshot["ledger_integrity"] == "intact"
    assert database.read_bytes() == before


def test_bridge_surfaces_tampered_action_integrity_as_failed(tmp_path):
    database = tmp_path / "habitat.db"
    _seed_database(database)
    connection = sqlite3.connect(database)
    connection.execute("UPDATE action_integrity SET hash = ?", ("0" * 64,))
    connection.commit()
    connection.close()

    snapshot = load_habitat_snapshot(database)

    assert snapshot["available"] is True
    assert snapshot["ledger_integrity"] == "failed"


def test_bridge_reports_incomplete_schema_as_unavailable(tmp_path):
    database = tmp_path / "partial.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE habitat (id TEXT)")
    connection.commit()
    connection.close()

    snapshot = load_habitat_snapshot(database)

    assert snapshot["available"] is False
    assert snapshot["reason"] == "incomplete_schema"


def test_bridge_reports_missing_database_as_unavailable(tmp_path):
    snapshot = load_habitat_snapshot(tmp_path / "missing.db")

    assert snapshot["available"] is False
    assert snapshot["reason"] == "database_missing"
