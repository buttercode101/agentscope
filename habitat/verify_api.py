"""Machine-consumable claim verification and portable proof responses."""
from __future__ import annotations

from typing import Any

from .proof import build_proof
from .verify import verify_claim


def verify_and_prove(
    store: Any,
    claim_id: str,
    evidence_adapter: Any | None = None,
    evidence_query: str | None = None,
    evidence_expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Re-verify a claim, then return its current verdict and proof bundle.

    External evidence cannot be freshly re-verified without the adapter that
    originally supplied it. In that case this function returns the existing
    decision without mutating it, rather than silently downgrading the claim.
    """
    claim = store.get_claim(claim_id)
    if claim is None:
        raise KeyError(f"Unknown claim: {claim_id}")

    evidence = claim.evidence if isinstance(claim.evidence, dict) else {}
    source = evidence.get("source")
    if source and source != "habitat_trusted_ledger" and evidence_adapter is None:
        proof = build_proof(store, claim.id)
        return {
            "claim_id": claim.id,
            "verdict": "inconclusive",
            "stored_verdict": claim.status,
            "verified_at": claim.verified_at.isoformat() if claim.verified_at else None,
            "reverified": False,
            "reverify_reason": "external_evidence_requires_adapter",
            "proof": proof,
        }

    claim = verify_claim(store, claim, evidence_adapter, evidence_query, evidence_expected)
    proof = build_proof(store, claim.id)
    return {
        "claim_id": claim.id,
        "verdict": claim.status,
        "verified_at": claim.verified_at.isoformat() if claim.verified_at else None,
        "reverified": True,
        "proof": proof,
    }


def proof_status(store: Any, claim_id: str) -> dict[str, Any]:
    """Return proof without changing the stored claim decision."""
    proof = build_proof(store, claim_id)
    return {
        "claim_id": claim_id,
        "verdict": proof["claim"]["status"],
        "ledger_integrity": proof["ledger"]["integrity"],
        "content_sha256": proof["content_sha256"],
        "proof": proof,
    }
