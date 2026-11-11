"""Reason-code -> human explanation map (DESIGN_SYSTEM §2.3).

Single source of truth for verdict explanations, consumed by the CLI
(`verify`, `prove`) so a negative verdict is never a dead end. Each entry
names what the verdict means and what would change it.
"""
from __future__ import annotations

REASON_EXPLANATIONS: dict[str, dict[str, str]] = {
    "no_matching_trusted_action": {
        "meaning": "No recorded action matches this claim (wrong or missing run_id).",
        "next_action": "Record the action first (habitat run, habitat demo, or POST /v1/events), or pass the correct --run-id.",
        "what_would_change": "A trusted action with this run_id, action and status recorded in the local ledger.",
    },
    "run_id_required_for_ambiguous_trusted_verification": {
        "meaning": "Multiple recorded actions match this claim; the run is ambiguous.",
        "next_action": "Pass --run-id <id> to pin the claim to one run.",
        "what_would_change": "An explicit --run-id selecting exactly one of the matching actions.",
    },
    "action_ledger_integrity_check_failed": {
        "meaning": "The local hash chain over recorded actions does not verify.",
        "next_action": "Run habitat doctor. Do not export proofs from this ledger.",
        "what_would_change": "A ledger whose action hash chain verifies again (restore a clean backup if needed).",
    },
    "matching_action_has_different_status": {
        "meaning": "A matching action exists, but its status differs from the claim's expected status.",
        "next_action": "See observed vs expected in the evidence; adjust the claim or the expected status.",
        "what_would_change": "A matching action recorded with the expected status.",
    },
    "claim_requires_correlation_or_external_evidence": {
        "meaning": "The claim has no run, job or action correlation and no external evidence was supplied.",
        "next_action": "Pass --run-id (or --job/--action), or supply external evidence.",
        "what_would_change": "Correlation to a recorded action, or explicit external evidence that matches.",
    },
    "habitat_mismatch": {
        "meaning": "The claim belongs to a different Habitat than this database.",
        "next_action": "Use the database that the claim was created in, or create the claim in this Habitat.",
        "what_would_change": "A claim whose habitat_id matches this database.",
    },
    "external_evidence_did_not_match": {
        "meaning": "External evidence was observed, but it does not match the claim's expected status or data.",
        "next_action": "See observed vs expected above; adjust the claim or supply different evidence.",
        "what_would_change": "External evidence matching the expected status and data.",
    },
    "not_initialized": {
        "meaning": "No Habitat database has been initialized.",
        "next_action": "Run: habitat init --config examples/simple.yaml",
        "what_would_change": "An initialized Habitat database (habitat init).",
    },
}

BOUNDARY_SENTENCES: dict[str, str] = {
    "verified": "This shows the claim matches evidence in the local ledger. It does not prove the claim is true in the world.",
    "inconclusive": "This shows the evidence is insufficient — here is what would change the verdict: see next_action.",
    "rejected": "This shows the evidence does not support the claim. The claim and the evidence are both shown above.",
    "demo": "This is sample demo data, not a live verification. Run tools/verify_proof.py for the real verdict.",
}


def explain_reason(reason: str | None) -> dict[str, str] | None:
    """Return {reason, meaning, next_action, what_would_change} or None."""
    if not reason:
        return None
    entry = REASON_EXPLANATIONS.get(reason)
    if not entry:
        return None
    return {"reason": reason, **entry}


def boundary_sentence(verdict: str | None) -> str | None:
    if not verdict:
        return None
    return BOUNDARY_SENTENCES.get(verdict)
