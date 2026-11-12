from datetime import datetime, timezone

from habitat.backup import backup, restore
from habitat.schema import Action, Habitat
from habitat.store import Store


def _seed_database(path):
    store = Store(path)
    store.save_habitat(Habitat(id="h1", name="Backup fixture"))
    store.save_action(
        Action(
            id="a1",
            habitat_id="h1",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            actor="agent",
            action="run_job",
            status="ok",
            details={"sample": True},
            run_id="r1",
        )
    )
    store.close()


def test_backup_restore_preserves_habitat_data_and_action_integrity(tmp_path):
    source = tmp_path / "source.db"
    archive = tmp_path / "backup.db"
    restored = tmp_path / "restored.db"
    _seed_database(source)

    backup(source, archive)
    restore(archive, restored)

    recovered = Store(restored)
    try:
        assert recovered.habitat().id == "h1"
        assert recovered.verify_action_integrity() is True
        actions = recovered.actions_for_run("r1")
        assert len(actions) == 1
        assert actions[0].id == "a1"
        assert actions[0].details == {"sample": True}
    finally:
        recovered.close()
