import json

import pytest

from habitat.events import ingest_event, signature_for
from habitat.schema import Habitat, Job
from habitat.store import Store


def make(tmp_path):
    s = Store(tmp_path / "h.db")
    s.save_habitat(Habitat("h", "H"))
    s.save_job(Job("j", "h", "J", enabled=True, command="echo ok"))
    return s


def test_payload_agent_cannot_be_spoofed_with_transport_secret(tmp_path):
    s = make(tmp_path)
    s.save_agent("privileged", "h", "Privileged", True, ["submit_events"], "agent-secret")
    body = json.dumps({
        "id": "spoof-1", "type": "job.completed", "habitat_id": "h",
        "job_id": "j", "run_id": "r1", "agent_id": "privileged",
    }).encode()
    with pytest.raises(PermissionError, match="agent_secret_required"):
        ingest_event(s, body, signature_for("transport-secret", body), "transport-secret")
    s.close()


def test_explicit_and_payload_agent_ids_must_match(tmp_path):
    s = make(tmp_path)
    s.save_agent("a1", "h", "A1", True, ["submit_events"], "a1-secret")
    s.save_agent("a2", "h", "A2", True, ["submit_events"], "a2-secret")
    body = json.dumps({
        "id": "spoof-2", "type": "job.completed", "habitat_id": "h",
        "job_id": "j", "run_id": "r2", "agent_id": "a2",
    }).encode()
    with pytest.raises(PermissionError, match="agent_identity_mismatch"):
        ingest_event(s, body, signature_for("transport-secret", body), "transport-secret", True, "a1", "a1-secret")
    s.close()


def test_same_event_id_with_different_payload_is_rejected(tmp_path):
    s = make(tmp_path)
    first = json.dumps({
        "id": "replay-1", "type": "job.completed", "habitat_id": "h",
        "job_id": "j", "run_id": "r1",
    }).encode()
    ingest_event(s, first, signature_for("secret", first), "secret")
    conflicting = json.dumps({
        "id": "replay-1", "type": "job.failed", "habitat_id": "h",
        "job_id": "j", "run_id": "r1", "error": "spoofed",
    }).encode()
    with pytest.raises(ValueError, match="event_id_conflict"):
        ingest_event(s, conflicting, signature_for("secret", conflicting), "secret")
    s.close()


def test_secretless_agent_cannot_authenticate_network_event(tmp_path):
    s = make(tmp_path)
    s.save_agent("no-secret", "h", "No Secret", True, ["submit_events"])
    body = json.dumps({
        "id": "secretless-1", "type": "job.completed", "habitat_id": "h",
        "job_id": "j", "run_id": "r3", "agent_id": "no-secret",
    }).encode()
    with pytest.raises(PermissionError, match="agent_not_authorized"):
        ingest_event(s, body, signature_for("secret", body), "secret", True, "no-secret", "secret")
    s.close()
