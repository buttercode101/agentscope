"""Deterministic claim verification with exact run correlation and policy gates."""
from __future__ import annotations

from typing import Any

from .adapters import EvidenceAdapter
from .claims import Claim
from .policy import EvidencePolicy, apply_policy
from .schema import utcnow
from .store import Store


def _matches_expected(data: Any, expected: dict[str, Any] | None) -> bool:
    if not expected:
        return True
    return isinstance(data, dict) and all(data.get(k) == v for k, v in expected.items())


def _finish(claim: Claim, store: Store, policy: EvidencePolicy | None = None) -> Claim:
    if policy and claim.status == "verified":
        decision = apply_policy(policy, claim.evidence)
        claim.evidence = {**claim.evidence, "policy": decision}
        if decision["status"] != "allowed":
            claim.status = "rejected"
    claim.verified_at = utcnow()
    store.save_claim(claim)
    return claim


def verify_claim(
    store: Store,
    claim: Claim,
    evidence_adapter: EvidenceAdapter | None = None,
    evidence_query: str | None = None,
    evidence_expected: dict[str, Any] | None = None,
    policy: EvidencePolicy | None = None,
) -> Claim:
    """Verify a claim, then apply an optional policy as a final non-positive gate.

    Policies can only downgrade a verified result; they can never turn missing or
    rejected evidence into a positive verification.
    """
    if claim.habitat_id != store.habitat().id:
        claim.status = "rejected"
        claim.evidence = {"source": "habitat", "reason": "habitat_mismatch"}
        return _finish(claim, store, policy)
    if not store.verify_action_integrity():
        claim.status = "inconclusive"
        claim.evidence = {"source": "habitat_trusted_ledger", "reason": "action_ledger_integrity_check_failed"}
        return _finish(claim, store, policy)

    has_correlation = bool(claim.run_id or claim.job_id or claim.action)
    matches = store.matching_actions(claim.habitat_id, claim.job_id, claim.action, claim.run_id) if has_correlation else []

    # A claim without a run/job/action correlation has no trustworthy basis in
    # Habitat's action ledger. It must never be verified from an unrelated action.
    if not has_correlation and not evidence_adapter:
        claim.status = "rejected"
        claim.evidence = {"source": "habitat_trusted_ledger", "reason": "claim_requires_correlation_or_external_evidence"}
        return _finish(claim, store, policy)

    # A claim without an explicit run_id may only be positively verified from the
    # trusted ledger when exactly one correlated action exists. The presence of an
    # external evidence adapter must never make an ambiguous trusted action look
    # attributable to this claim.
    if claim.run_id is None and (claim.job_id or claim.action):
        if len(matches) == 1:
            trusted = matches[0] if matches[0].status == claim.expected_status else None
            if trusted:
                claim.status = "verified"
                claim.evidence = {"source": "habitat_trusted_ledger", "action_id": trusted.id, "action": trusted.action, "status": trusted.status, "timestamp": trusted.timestamp.isoformat(), "run_id": trusted.run_id, "legacy_match": True, "details": trusted.details}
            else:
                claim.status = "rejected"
                claim.evidence = {"source": "habitat_trusted_ledger", "reason": "matching_action_has_different_status", "legacy_match": True}
            return _finish(claim, store, policy)
        if len(matches) > 1:
            if not evidence_adapter or not evidence_query:
                claim.status = "inconclusive"
                claim.evidence = {"source": "habitat_trusted_ledger", "reason": "run_id_required_for_ambiguous_trusted_verification"}
                return _finish(claim, store, policy)
            # Continue to external evidence only; do not fall through to an
            # arbitrary trusted action below.
        elif not evidence_adapter or not evidence_query:
            claim.status = "rejected"
            claim.evidence = {"source": "habitat_trusted_ledger", "reason": "no_matching_trusted_action"}
            return _finish(claim, store, policy)

    if claim.run_id is not None or (has_correlation and len(matches) <= 1):
        trusted = next((a for a in matches if a.status == claim.expected_status), None)
        if trusted:
            claim.status = "verified"
            claim.evidence = {"source": "habitat_trusted_ledger", "action_id": trusted.id, "action": trusted.action, "status": trusted.status, "timestamp": trusted.timestamp.isoformat(), "run_id": trusted.run_id, "details": trusted.details}
            return _finish(claim, store, policy)
        if matches:
            claim.status = "rejected"
            claim.evidence = {"source": "habitat_trusted_ledger", "reason": "matching_action_has_different_status", "observed": [{"action": a.action, "status": a.status, "run_id": a.run_id} for a in matches[:5]]}
            return _finish(claim, store, policy)

    if evidence_adapter and evidence_query:
        evidence = evidence_adapter.observe(evidence_query)
        if evidence.observed and evidence.status == claim.expected_status and _matches_expected(evidence.data, evidence_expected):
            claim.status = "verified"
            claim.evidence = {"source": evidence.source, "status": evidence.status, "data": evidence.data, "query": evidence_query, "expected": evidence_expected or {}}
        elif evidence.error:
            claim.status = "inconclusive"
            claim.evidence = {"source": evidence.source, "reason": evidence.error, "query": evidence_query}
        else:
            claim.status = "rejected"
            claim.evidence = {"source": evidence.source, "reason": "external_evidence_did_not_match", "status": evidence.status, "data": evidence.data, "query": evidence_query, "expected": evidence_expected or {}}
    else:
        claim.status = "rejected"
        claim.evidence = {"source": "habitat_trusted_ledger", "reason": "no_matching_trusted_action"}
    return _finish(claim, store, policy)
