"""Deep integrity tests for the trusted action ledger."""
from __future__ import annotations

from datetime import datetime, timezone

from habitat.schema import Action, Habitat, Job
from habitat.store import Store


def make_store(tmp_path):
    store = Store(tmp_path / "ledger.db")
    store.save_habitat(Habitat("h", "Test Habitat", "local", datetime.now(timezone.utc), datetime.now(timezone.utc)))
    store.save_job(Job("j", "h", "Test Job", enabled=True, command="echo ok"))
    return store


def _action(action_id: str, run_id: str = "run-1", action: str = "deploy", status: str = "ok") -> Action:
    return Action(
        id=action_id,
        habitat_id="h",
        timestamp=datetime.now(timezone.utc),
        actor="agent",
        action=action,
        status=status,
        job_id="j",
        details={},
        run_id=run_id,
    )


def test_fresh_store_has_valid_integrity(tmp_path):
    store = make_store(tmp_path)
    assert store.verify_action_integrity() is True
    store.close()


def test_single_action_chain_is_valid(tmp_path):
    store = make_store(tmp_path)
    store.save_action(_action("a1"))
    assert store.verify_action_integrity() is True
    store.close()


def test_multi_action_chain_is_valid(tmp_path):
    store = make_store(tmp_path)
    store.save_action(_action("a1"))
    store.save_action(_action("a2"))
    store.save_action(_action("a3", run_id="run-2"))
    assert store.verify_action_integrity() is True
    store.close()


def test_tampered_hash_is_detected(tmp_path):
    store = make_store(tmp_path)
    store.save_action(_action("a1"))
    assert store.verify_action_integrity() is True

    store.conn.execute(
        "UPDATE action_integrity SET hash = 'deadbeef' WHERE action_id = 'a1'"
    )
    store.conn.commit()
    assert store.verify_action_integrity() is False
    store.close()


def test_tampered_prev_hash_is_detected(tmp_path):
    store = make_store(tmp_path)
    store.save_action(_action("a1"))
    store.save_action(_action("a2"))
    assert store.verify_action_integrity() is True

    store.conn.execute(
        "UPDATE action_integrity SET prev_hash = '0000' WHERE action_id = 'a2'"
    )
    store.conn.commit()
    assert store.verify_action_integrity() is False
    store.close()


def test_deleted_action_breaks_chain(tmp_path):
    store = make_store(tmp_path)
    store.save_action(_action("a1"))
    store.save_action(_action("a2"))
    assert store.verify_action_integrity() is True

    store.conn.execute("DELETE FROM action WHERE id = 'a1'")
    store.conn.commit()
    assert store.verify_action_integrity() is False
    store.close()


def test_missing_integrity_row_is_detected(tmp_path):
    store = make_store(tmp_path)
    store.save_action(_action("a1"))
    assert store.verify_action_integrity() is True

    # Remove the integrity record for an existing action. The chain must fail.
    store.conn.execute(
        "DELETE FROM action_integrity WHERE action_id = 'a1'"
    )
    store.conn.commit()
    assert store.verify_action_integrity() is False
    store.close()


def test_modified_action_payload_breaks_hash(tmp_path):
    store = make_store(tmp_path)
    store.save_action(_action("a1", status="ok"))
    assert store.verify_action_integrity() is True

    # Mutate the underlying action after it was hashed
    store.conn.execute("UPDATE action SET status = 'failed' WHERE id = 'a1'")
    store.conn.commit()
    assert store.verify_action_integrity() is False
    store.close()


def test_integrity_survives_reopen(tmp_path):
    db_path = tmp_path / "ledger.db"
    store = Store(db_path)
    store.save_habitat(Habitat("h", "Test Habitat", "local", datetime.now(timezone.utc), datetime.now(timezone.utc)))
    store.save_job(Job("j", "h", "Test Job", enabled=True, command="echo ok"))
    store.save_action(_action("a1"))
    store.save_action(_action("a2"))
    assert store.verify_action_integrity() is True
    store.close()

    # Re-open and re-check
    store2 = Store(db_path)
    assert store2.verify_action_integrity() is True
    store2.close()
