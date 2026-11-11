"""Portable, deterministic proof bundles for Habitat claim decisions.

A proof bundle is deliberately small: it carries the claim, verdict, evidence,
relevant trusted actions, ledger-integrity result, and a content hash. It does
not pretend to be a cryptographic attestation of the outside world; it proves
what Habitat observed and whether its own evidence chain was intact.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .schema import utcnow
from .proof_verify import MAX_PROOF_ACTIONS, MAX_PROOF_BYTES


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _action_dict(action: Any) -> dict[str, Any]:
    return {
        "id": action.id,
        "habitat_id": action.habitat_id,
        "job_id": action.job_id,
        "timestamp": action.timestamp.isoformat(),
        "actor": action.actor,
        "action": action.action,
        "status": action.status,
        "details": action.details,
        "run_id": action.run_id,
    }


def build_proof(store: Any, claim_id: str) -> dict[str, Any]:
    """Build a portable proof bundle for one stored claim.

    The bundle is deterministic except for ``generated_at``. The hash covers
    every field except that timestamp and the optional signature, so the same
    observed evidence produces the same content digest whether or not a
    signature is subsequently attached.
    """
    claim = store.get_claim(claim_id)
    if claim is None:
        raise KeyError(f"Unknown claim: {claim_id}")

    integrity_ok = store.verify_action_integrity()
    if claim.run_id:
        actions = store.actions_for_run(claim.run_id)
    else:
        actions = store.matching_actions(claim.habitat_id, claim.job_id, claim.action)
    if len(actions) > MAX_PROOF_ACTIONS:
        raise ValueError(f"proof bundle exceeds maximum of {MAX_PROOF_ACTIONS} actions")
    actions = sorted(actions, key=lambda a: (a.timestamp, a.id))

    bundle: dict[str, Any] = {
        "proof_version": "1",
        "generated_at": utcnow().isoformat(),
        "claim": {
            "id": claim.id,
            "habitat_id": claim.habitat_id,
            "job_id": claim.job_id,
            "claim": claim.claim,
            "action": claim.action,
            "expected_status": claim.expected_status,
            "created_at": claim.created_at.isoformat(),
            "verified_at": claim.verified_at.isoformat() if claim.verified_at else None,
            "status": claim.status,
            "evidence": claim.evidence,
            "run_id": claim.run_id,
        },
        "ledger": {
            "integrity": "intact" if integrity_ok else "failed",
            "actions": [_action_dict(a) for a in actions],
        },
    }
    digest_input = dict(bundle)
    digest_input.pop("generated_at")
    bundle["content_sha256"] = hashlib.sha256(_canonical(digest_input).encode()).hexdigest()
    if len(_canonical(bundle).encode("utf-8")) > MAX_PROOF_BYTES:
        raise ValueError(f"proof bundle exceeds maximum size of {MAX_PROOF_BYTES} bytes")
    return bundle


def export_proof(store: Any, claim_id: str, path: str) -> dict[str, Any]:
    """Write a proof bundle as UTF-8 JSON and return the bundle."""
    bundle = build_proof(store, claim_id)
    raw = json.dumps(bundle, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    if len(raw) > MAX_PROOF_BYTES:
        raise ValueError(f"proof bundle exceeds maximum size of {MAX_PROOF_BYTES} bytes")
    with open(path, "wb") as handle:
        handle.write(raw)
    return bundle
