"""Secure structured event ingestion."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid

from .claims import Claim
from .schema import Action, utcnow
from .store import Store
from .verify import verify_claim

MAX_EVENT_BYTES = 256 * 1024
ALLOWED_TYPES = {"agent.heartbeat", "job.started", "job.completed", "job.failed", "claim.submitted"}
PERMISSIONS = {"agent.heartbeat": "submit_events", "job.started": "submit_events", "job.completed": "submit_events", "job.failed": "submit_events", "claim.submitted": "submit_claims"}


def signature_for(secret, body):
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def valid_signature(secret, body, supplied):
    if not secret or not supplied:
        return False
    normalized = supplied.removeprefix("sha256=").strip()
    if len(normalized) != 64:
        return False
    try:
        int(normalized, 16)
    except ValueError:
        return False
    return hmac.compare_digest(signature_for(secret, body), normalized)


def _reject_constant(value):
    raise ValueError(f"non_standard_json_number:{value}")


def _validate(p, store):
    eid, typ, hid = p.get("id"), p.get("type"), p.get("habitat_id")
    if not isinstance(eid, str) or not eid.strip() or len(eid) > 200:
        raise ValueError("invalid_id")
    if typ not in ALLOWED_TYPES:
        raise ValueError("unsupported_event_type")
    if not isinstance(hid, str) or not hid:
        raise ValueError("missing_habitat_id")
    if store.habitat().id != hid:
        raise ValueError("habitat_id_mismatch")
    if typ == "agent.heartbeat":
        return eid, typ, hid
    if typ == "claim.submitted":
        if not isinstance(p.get("claim"), str) or not p["claim"].strip():
            raise ValueError("missing_claim")
        if p.get("job_id") is not None and not isinstance(p["job_id"], str):
            raise ValueError("invalid_job_id")
    else:
        if not isinstance(p.get("job_id"), str):
            raise ValueError("missing_job_id")
        if not any(j.id == p["job_id"] for j in store.jobs()):
            raise ValueError("unknown_job_id")
    return eid, typ, hid


def ingest_event(store, body, signature, secret, require_signature=True, agent_id=None, agent_secret=None):
    if len(body) > MAX_EVENT_BYTES:
        raise ValueError("event_too_large")
    try:
        p = json.loads(body.decode("utf-8"), parse_constant=_reject_constant)
    except Exception as exc:
        raise ValueError("invalid_json") from exc
    if not isinstance(p, dict):
        raise ValueError("event_must_be_object")
    eid, typ, hid = _validate(p, store)
    ok = valid_signature(secret or "", body, signature)
    if require_signature and not ok:
        raise PermissionError("invalid_signature")
    payload_agent = p.get("agent_id")
    if payload_agent is not None and not isinstance(payload_agent, str):
        raise ValueError("invalid_agent_id")
    if agent_id is not None and payload_agent is not None and payload_agent != agent_id:
        raise PermissionError("agent_identity_mismatch")
    declared_agent = payload_agent or agent_id

    # Event acceptance, agent last-seen state, derived actions/jobs, and claims
    # are one transaction. A downstream failure must not leave a duplicate event
    # that causes the retry to be discarded while its side effects are missing.
    with store.transaction(immediate=True):
        if declared_agent:
            if not agent_secret:
                raise PermissionError("agent_secret_required")
            if not store.authenticate_agent(declared_agent, agent_secret, PERMISSIONS[typ]):
                raise PermissionError("agent_not_authorized")
        inserted = store.save_event(eid, hid, typ, utcnow().isoformat(), ok, p, declared_agent)
        result = {"accepted": True, "duplicate": not inserted, "id": eid, "type": typ}
        if not inserted:
            return result
        correlation = p.get("correlation_id") or p.get("run_id") or eid
        if typ == "agent.heartbeat":
            result["agent_id"] = declared_agent
            result["heartbeat"] = True
            return result
        if typ in {"job.completed", "job.failed"}:
            job = next(j for j in store.jobs() if j.id == p["job_id"])
            status = "ok" if typ == "job.completed" else "failed"
            now = utcnow()
            store.save_action(Action(str(uuid.uuid4()), hid, now, declared_agent or "agent", "run_job", status, job.id, {"source": "event", "event_id": eid, "payload": p}, correlation))
            job.last_run_at = now
            job.last_status = status
            job.last_error = p.get("error") if status == "failed" else None
            job.failure_streak = job.failure_streak + 1 if status == "failed" else 0
            store.save_job(job)
            result.update(job_status=status, run_id=correlation)
        elif typ == "job.started":
            job = next(j for j in store.jobs() if j.id == p["job_id"])
            job.last_status = "running"
            job.last_run_at = utcnow()
            store.save_job(job)
            result.update(job_status="running", run_id=correlation)
        else:
            c = Claim.new(hid, p["claim"], p.get("job_id"), p.get("action"), p.get("expected_status", "ok"))
            c.run_id = p.get("run_id") or p.get("correlation_id")
            if c.job_id and not c.run_id:
                c.status = "inconclusive"
                c.evidence = {"source": "habitat", "reason": "run_id_required_for_network_claim"}
                c.verified_at = utcnow()
                store.save_claim(c)
            else:
                store.save_claim(c)
                verify_claim(store, c, None, None, p.get("evidence_expected"))
            result.update(claim_id=c.id, claim_status=c.status)
        return result
