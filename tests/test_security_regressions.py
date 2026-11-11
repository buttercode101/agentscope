import hashlib
import json
from datetime import datetime, timezone

import pytest

from habitat.claims import Claim
from habitat.events import ingest_event, signature_for
from habitat.schema import Action, Habitat, Job
from habitat.server import HabitatHTTPServer, _AuthRateLimiter, make_handler
from habitat.store import PBKDF2_ITERATIONS, Store
from habitat.verify import verify_claim


def make(tmp_path):
    store = Store(tmp_path / "security.db")
    store.save_habitat(Habitat("h", "H"))
    store.save_job(Job("j", "h", "J", enabled=True, command="echo ok"))
    return store


def test_agent_secret_uses_salted_slow_hash(tmp_path):
    store = make(tmp_path)
    store.save_agent("a", "h", "A", True, ["submit_events"], "correct-secret")
    row = store.conn.execute("SELECT secret_hash FROM agent WHERE id='a'").fetchone()
    stored = row[0]
    assert stored.startswith("pbkdf2_sha256$")
    assert f"${PBKDF2_ITERATIONS}$" in stored
    assert stored != Store.hash_secret("correct-secret")
    assert store.authenticate_agent("a", "correct-secret", "submit_events") is True
    assert store.authenticate_agent("a", "wrong-secret", "submit_events") is False
    store.close()


def test_legacy_sha256_agent_secret_is_upgraded_on_success(tmp_path):
    store = make(tmp_path)
    legacy = hashlib.sha256(b"legacy-secret").hexdigest()
    store.conn.execute(
        "INSERT INTO agent VALUES (?,?,?,?,?,?,?,?)",
        ("legacy", "h", "Legacy", 1, json.dumps(["submit_events"]), legacy, "2026-01-01T00:00:00+00:00", None),
    )
    store.conn.commit()
    assert store.authenticate_agent("legacy", "legacy-secret", "submit_events") is True
    upgraded = store.conn.execute("SELECT secret_hash FROM agent WHERE id='legacy'").fetchone()[0]
    assert upgraded.startswith("pbkdf2_sha256$")
    assert upgraded != legacy
    store.close()


def test_non_standard_json_numbers_are_rejected(tmp_path):
    store = make(tmp_path)
    body = b'{"id":"nan-1","type":"job.completed","habitat_id":"h","job_id":"j","run_id":NaN}'
    with pytest.raises(ValueError, match="invalid_json"):
        ingest_event(store, body, signature_for("secret", body), "secret")
    store.close()


def test_ambiguous_legacy_claim_never_selects_arbitrary_trusted_action(tmp_path):
    store = make(tmp_path)
    timestamp = datetime.now(timezone.utc)
    store.save_action(Action("a1", "h", timestamp, "agent", "deploy", "ok", "j", {}, "run-1"))
    store.save_action(Action("a2", "h", timestamp, "agent", "deploy", "ok", "j", {}, "run-2"))

    class ExternalEvidence:
        def observe(self, query):
            return type("Evidence", (), {
                "source": "external",
                "observed": True,
                "status": "ok",
                "data": {"verified": True},
                "error": None,
            })()

    claim = Claim.new("h", "deployment externally verified", job_id="j", action="deploy")
    result = verify_claim(store, claim, ExternalEvidence(), "deployment")
    assert result.status == "verified"
    assert result.evidence["source"] == "external"
    assert "action_id" not in result.evidence
    store.close()


def test_uncorrelated_claim_cannot_verify_from_unrelated_action(tmp_path):
    store = make(tmp_path)
    timestamp = datetime.now(timezone.utc)
    store.save_action(Action("a1", "h", timestamp, "agent", "deploy", "ok", "j", {}, "run-1"))
    claim = Claim.new("h", "some unrelated assertion")
    result = verify_claim(store, claim)
    assert result.status == "rejected"
    assert result.evidence["reason"] == "claim_requires_correlation_or_external_evidence"
    store.close()


def test_auth_rate_limiter_blocks_after_threshold_and_expires():
    limiter = _AuthRateLimiter(max_failures=3, window_seconds=60, max_keys=2)
    key = ("server", "203.0.113.10")
    assert limiter.blocked(key, now=100) is False
    assert limiter.record_failure(key, now=100) is False
    assert limiter.record_failure(key, now=101) is False
    assert limiter.record_failure(key, now=102) is True
    assert limiter.blocked(key, now=103) is True
    assert limiter.blocked(key, now=161) is False


def test_auth_rate_limiter_success_clears_failures():
    limiter = _AuthRateLimiter(max_failures=2, window_seconds=60)
    key = ("agent", "203.0.113.11")
    limiter.record_failure(key, now=100)
    limiter.clear(key)
    assert limiter.blocked(key, now=101) is False


def test_auth_rate_limiter_bounds_tracked_keys():
    limiter = _AuthRateLimiter(max_failures=2, window_seconds=60, max_keys=2)
    limiter.record_failure(("agent", "203.0.113.1"), now=1)
    limiter.record_failure(("agent", "203.0.113.2"), now=2)
    limiter.record_failure(("agent", "203.0.113.3"), now=3)
    assert len(limiter._failures) <= 2


def test_http_server_drops_connections_when_cap_is_reached():
    handler = make_handler(":memory:", None, protect_remote=False)
    server = HabitatHTTPServer(("127.0.0.1", 0), handler, max_connections=1)

    class FakeRequest:
        closed = False

        def close(self):
            self.closed = True

    request = FakeRequest()
    assert server._connection_slots.acquire(blocking=False) is True
    try:
        server.process_request(request, ("127.0.0.1", 12345))
        assert request.closed is True
    finally:
        server._connection_slots.release()
        server.server_close()
