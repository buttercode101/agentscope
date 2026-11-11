import hashlib
import hmac
import json
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from habitat.events import ingest_event
from habitat.schema import Action, Habitat, Job
from habitat.server import _is_loopback_host, serve
from habitat.store import Store


def test_non_loopback_listener_requires_secret():
    with tempfile.TemporaryDirectory() as d:
        try:
            serve(Path(d) / "state.db", host="0.0.0.0", port=0, secret=None)
        except ValueError as exc:
            assert "server secret" in str(exc)
        else:
            raise AssertionError("non-loopback listener must require a secret")


def test_loopback_detection_is_strict():
    assert _is_loopback_host("127.0.0.1")
    assert _is_loopback_host("::1")
    assert _is_loopback_host("localhost")
    assert not _is_loopback_host("0.0.0.0")
    assert not _is_loopback_host("192.168.1.10")


def test_concurrent_action_writers_preserve_integrity_chain():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "state.db"
        Store(path).close()
        barrier = threading.Barrier(8)

        def writer(index):
            store = Store(path)
            try:
                barrier.wait()
                store.save_action(Action(f"a{index}", "h", datetime.now(timezone.utc), "agent", "test", "ok", "j", {}, f"r{index}"))
            finally:
                store.close()

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        store = Store(path)
        try:
            assert len(store.actions(100)) == 8
            assert store.verify_action_integrity() is True
        finally:
            store.close()


def test_exact_claim_and_run_queries_are_not_recent_history_windows():
    with tempfile.TemporaryDirectory() as d:
        store = Store(Path(d) / "state.db")
        try:
            store.save_action(Action("old", "h", datetime(2026, 1, 1, tzinfo=timezone.utc), "agent", "deploy", "ok", "j", {}, "run-old"))
            assert [a.id for a in store.actions_for_run("run-old")] == ["old"]
            assert [a.id for a in store.matching_actions("h", "j", "deploy", "run-old")] == ["old"]
        finally:
            store.close()


def test_event_ingestion_rolls_back_if_derived_action_fails(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        store = Store(Path(d) / "state.db")
        try:
            store.save_habitat(Habitat("h", "H"))
            store.save_job(Job("j", "h", "J"))
            payload = {"id": "e1", "type": "job.completed", "habitat_id": "h", "job_id": "j", "run_id": "r1"}
            body = json.dumps(payload, separators=(",", ":")).encode()
            secret = "secret"
            signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

            def fail(_action):
                raise RuntimeError("simulated write failure")

            monkeypatch.setattr(store, "save_action", fail)
            try:
                ingest_event(store, body, signature, secret)
            except RuntimeError:
                pass
            else:
                raise AssertionError("expected derived-action failure")
            assert store.events() == []
        finally:
            store.close()
