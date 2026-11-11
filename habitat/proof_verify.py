"""Dependency-light verification of exported Habitat proof bundles.

The verifier separates structural validity, content integrity, internal
consistency, cryptographic signature validity, publisher trust, and external
truth. A valid bundle is never treated as proof that the outside world is true.

CRITICAL: This verifier MUST catch all tampering. No exceptions.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_PROOF_BYTES = 16 * 1024 * 1024
MAX_PROOF_ACTIONS = 10_000


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _date_time(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except ValueError:
        return False


def _finite_json_numbers(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _finite_json_numbers(v) for k, v in value.items())
    if isinstance(value, list):
        return all(_finite_json_numbers(v) for v in value)
    return True


def _validate_structure(bundle: dict[str, Any], errors: list[str]) -> None:
    allowed = {"proof_version", "generated_at", "claim", "ledger", "content_sha256", "signature"}
    required = {"proof_version", "generated_at", "claim", "ledger", "content_sha256"}
    unknown = sorted(set(bundle) - allowed)
    missing = sorted(required - set(bundle))
    if unknown:
        errors.append("unknown fields: " + ", ".join(unknown))
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
    if not _finite_json_numbers(bundle):
        errors.append("non-finite JSON numbers are not allowed")
    if bundle.get("proof_version") != "1":
        errors.append("unsupported proof_version")
    if not _date_time(bundle.get("generated_at")):
        errors.append("generated_at must be an ISO-8601 date-time with timezone")
    if not isinstance(bundle.get("content_sha256"), str) or len(bundle.get("content_sha256", "")) != 64 or any(c not in "0123456789abcdef" for c in bundle.get("content_sha256", "")):
        errors.append("content_sha256 must be 64 lowercase hexadecimal characters")

    claim = bundle.get("claim")
    ledger = bundle.get("ledger")
    claim_required = {"id", "habitat_id", "job_id", "claim", "action", "expected_status", "created_at", "verified_at", "status", "evidence", "run_id"}
    claim_allowed = claim_required
    if not isinstance(claim, dict):
        errors.append("claim must be an object")
    else:
        if set(claim) - claim_allowed:
            errors.append("claim contains unknown fields")
        if claim_required - set(claim):
            errors.append("claim is missing required fields")
        for field in ("id", "habitat_id", "claim", "expected_status", "status"):
            if not isinstance(claim.get(field), str):
                errors.append(f"claim.{field} must be a string")
        if not isinstance(claim.get("evidence"), dict):
            errors.append("claim.evidence must be an object")
        for field in ("job_id", "action", "run_id"):
            if claim.get(field) is not None and not isinstance(claim.get(field), str):
                errors.append(f"claim.{field} must be a string or null")
        if not _date_time(claim.get("created_at")):
            errors.append("claim.created_at must be an ISO-8601 date-time with timezone")
        if claim.get("verified_at") is not None and not _date_time(claim.get("verified_at")):
            errors.append("claim.verified_at must be an ISO-8601 date-time with timezone or null")

    if not isinstance(ledger, dict):
        errors.append("ledger must be an object")
    else:
        if set(ledger) != {"integrity", "actions"}:
            errors.append("ledger must contain exactly integrity and actions")
        if ledger.get("integrity") not in {"intact", "failed"}:
            errors.append("ledger.integrity must be 'intact' or 'failed'")
        actions = ledger.get("actions")
        if not isinstance(actions, list):
            errors.append("ledger.actions must be an array")
        else:
            if len(actions) > MAX_PROOF_ACTIONS:
                errors.append(f"ledger.actions exceeds maximum of {MAX_PROOF_ACTIONS}")
            required_action = {"id", "habitat_id", "job_id", "timestamp", "actor", "action", "status", "details", "run_id"}
            for index, action in enumerate(actions[:MAX_PROOF_ACTIONS]):
                if not isinstance(action, dict):
                    errors.append(f"ledger.actions[{index}] must be an object")
                    continue
                if set(action) != required_action:
                    errors.append(f"ledger.actions[{index}] has invalid fields")
                for field in ("id", "habitat_id", "actor", "action", "status"):
                    if not isinstance(action.get(field), str):
                        errors.append(f"ledger.actions[{index}].{field} must be a string")
                if not isinstance(action.get("details"), dict):
                    errors.append(f"ledger.actions[{index}].details must be an object")
                for field in ("job_id", "run_id"):
                    if action.get(field) is not None and not isinstance(action.get(field), str):
                        errors.append(f"ledger.actions[{index}].{field} must be a string or null")
                if not _date_time(action.get("timestamp")):
                    errors.append(f"ledger.actions[{index}].timestamp must be an ISO-8601 date-time with timezone")

    if "signature" in bundle:
        signature = bundle["signature"]
        if not isinstance(signature, dict):
            errors.append("signature must be an object")
        else:
            required_sig = {"algorithm", "key_id", "agent_id", "public_key", "signature"}
            if set(signature) != required_sig:
                errors.append("signature has invalid fields")
            if signature.get("algorithm") != "Ed25519":
                errors.append("signature.algorithm must be 'Ed25519'")
            for field in ("key_id", "agent_id"):
                if signature.get(field) is not None and not isinstance(signature.get(field), str):
                    errors.append(f"signature.{field} must be a string or null")
            for field in ("public_key", "signature"):
                if not isinstance(signature.get(field), str) or not signature.get(field):
                    errors.append(f"signature.{field} must be a non-empty string")


def _validate_relationships(claim: dict[str, Any], ledger: dict[str, Any], errors: list[str]) -> None:
    actions = ledger.get("actions")
    if not isinstance(actions, list):
        return
    claim_habitat = claim.get("habitat_id")
    claim_job = claim.get("job_id")
    claim_run = claim.get("run_id")
    claim_action = claim.get("action")
    expected_status = claim.get("expected_status")
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        if action.get("habitat_id") != claim_habitat:
            errors.append(f"ledger.actions[{index}] habitat_id does not match claim")
        if claim_job is not None and action.get("job_id") != claim_job:
            errors.append(f"ledger.actions[{index}] job_id does not match claim")
        if claim_run is not None and action.get("run_id") != claim_run:
            errors.append(f"ledger.actions[{index}] run_id does not match claim")
    evidence = claim.get("evidence")
    if not isinstance(evidence, dict):
        return
    if claim.get("status") == "verified":
        if not evidence:
            errors.append("verified claim must include evidence")
        else:
            source = evidence.get("source")
            if not isinstance(source, str) or not source:
                errors.append("verified claim evidence must identify a source")
            evidence_status = evidence.get("status")
            if evidence_status != expected_status:
                errors.append("verified claim evidence status does not match claim.expected_status")
            if source == "habitat_trusted_ledger" and not evidence.get("action_id"):
                errors.append("trusted-ledger verification must identify evidence.action_id")
    evidence_action_id = evidence.get("action_id")
    if evidence_action_id is None:
        return
    matched = next((a for a in actions if isinstance(a, dict) and a.get("id") == evidence_action_id), None)
    if matched is None:
        errors.append("claim evidence action_id is absent from ledger.actions")
        return
    if claim_action is not None and matched.get("action") != claim_action:
        errors.append("claim evidence action does not match claim.action")
    if expected_status is not None and matched.get("status") != expected_status:
        errors.append("claim evidence action status does not match claim.expected_status")
    if claim_run is not None and matched.get("run_id") != claim_run:
        errors.append("claim evidence action run_id does not match claim.run_id")


def _verify_signature(bundle: dict[str, Any]) -> str:
    """Report signature state without elevating an embedded key to publisher trust.

    A successful cryptographic check against the public key *carried in the
    bundle* only proves the signature is well-formed for that key material. It
    does not establish that the key is trusted by the verifier. Publisher trust
    requires an explicit TrustRegistry (see habitat.trust). Therefore the
    standalone / unconfigured path must never return "verified".
    """
    signature = bundle.get("signature")
    if signature is None:
        return "absent"
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        public_raw = base64.b64decode(signature["public_key"], validate=True)
        sig_raw = base64.b64decode(signature["signature"], validate=True)
        if len(public_raw) != 32 or len(sig_raw) != 64:
            return "invalid"
        unsigned = dict(bundle)
        unsigned.pop("signature", None)
        Ed25519PublicKey.from_public_bytes(public_raw).verify(sig_raw, _canonical(unsigned).encode("utf-8"))
        # Crypto OK against the embedded key only. Without a TrustRegistry this
        # remains present-unverified (publisher trust is a separate layer).
        return "present-unverified"
    except ImportError:
        return "present-unverified"
    except Exception:
        return "invalid"


def verify_proof(bundle: dict[str, Any]) -> dict[str, Any]:
    """Verify a decoded Habitat proof bundle and report assurance boundaries.

    CRITICAL: This function MUST catch all tampering. No exceptions.
    """
    errors: list[str] = []
    structure_errors: list[str] = []
    _validate_structure(bundle, structure_errors)
    errors.extend(structure_errors)

    # ALWAYS verify content_sha256 regardless of structure errors
    expected = bundle.get("content_sha256")
    actual = None
    if isinstance(expected, str):
        digest_input = dict(bundle)
        digest_input.pop("generated_at", None)
        digest_input.pop("content_sha256", None)
        digest_input.pop("signature", None)
        try:
            actual = hashlib.sha256(_canonical(digest_input).encode()).hexdigest()
        except (TypeError, ValueError):
            actual = None
            errors.append("content_sha256 computation failed")
        if actual is not None and actual != expected:
            errors.append("content_sha256 mismatch - proof has been tampered with")

    claim = bundle.get("claim")
    ledger = bundle.get("ledger")
    relationship_errors_before = len(errors)
    if isinstance(claim, dict) and isinstance(ledger, dict):
        _validate_relationships(claim, ledger, errors)
    verdict = claim.get("status") if isinstance(claim, dict) else None
    integrity = ledger.get("integrity") if isinstance(ledger, dict) else None
    if verdict == "verified" and integrity != "intact":
        errors.append("verified claim cannot have failed ledger integrity")

    # Signature verification - but don't let it override content integrity
    signature_state = _verify_signature(bundle) if not any(e.startswith("signature") for e in structure_errors) else "invalid"
    if signature_state == "invalid":
        errors.append("signature verification failed")

    # A proof is valid ONLY if: no errors, content integrity, relationships valid
    relationship_valid = len(errors) == relationship_errors_before
    content_valid = isinstance(actual, str) and actual == expected
    structural_valid = not structure_errors
    valid = structural_valid and content_valid and relationship_valid

    return {
        "valid": valid,
        "content_sha256": actual,
        "verdict": verdict,
        "ledger_integrity": integrity,
        "errors": errors,
        "scope": "bundle-integrity-and-internal-consistency",
        "authenticity": "cryptographic-signature" if signature_state == "verified" else "not-established",
        "assurance": {
            "structural_validity": structural_valid,
            "content_integrity": content_valid,
            "internal_consistency": relationship_valid and not (verdict == "verified" and integrity != "intact"),
            "signature": signature_state,
            "publisher_trust": "not-assessed",
            "external_truth": "not-established",
        },
    }


def verify_file(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if path.stat().st_size > MAX_PROOF_BYTES:
        return {"valid": False, "errors": [f"proof bundle exceeds maximum size of {MAX_PROOF_BYTES} bytes"]}
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("invalid_json_constant")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return {"valid": False, "errors": [str(exc)]}
    if not isinstance(value, dict):
        return {"valid": False, "errors": ["proof bundle must be a JSON object"]}
    return verify_proof(value)
