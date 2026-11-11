from habitat.schema import Action, Habitat, utcnow
from habitat.store import Store


def make(tmp_path):
    store = Store(tmp_path / "h.db")
    store.save_habitat(Habitat("h", "H"))
    store.save_action(Action("a", "h", utcnow(), "agent", "run_job", "ok", "j", {}, "r1"))
    return store


def test_integrity_table_deletion_is_detected_on_restart(tmp_path):
    store = make(tmp_path)
    assert store.verify_action_integrity()
    store.conn.execute("DELETE FROM action_integrity")
    store.conn.commit()
    assert not store.verify_action_integrity()
    store.close()

    reopened = Store(tmp_path / "h.db")
    assert not reopened.verify_action_integrity()
    assert reopened.conn.execute("SELECT COUNT(*) FROM action_integrity").fetchone()[0] == 0
    reopened.close()


def test_integrity_marker_is_persisted_after_initial_bootstrap(tmp_path):
    store = make(tmp_path)
    marker = store.conn.execute(
        "SELECT value FROM schema_meta WHERE key='action_integrity_initialized'"
    ).fetchone()
    assert marker[0] == "1"
    store.close()
