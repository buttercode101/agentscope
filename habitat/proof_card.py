"""Human-readable proof cards for PRs, tickets, and Slack."""
from __future__ import annotations

from typing import Any


def render_proof_card(proof: dict[str, Any], result: dict[str, Any] | None = None, proof_filename: str = "proof.json") -> str:
    """Return a short markdown card that can be pasted into a PR or message.

    `proof_filename` must be the file actually written for this proof, so
    the embedded verify command never references an unwritten file (UX-06).
    """
    claim = proof.get("claim") or {}
    ledger = proof.get("ledger") or {}
    evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
    result = result or {}

    status = str(claim.get("status") or result.get("verdict") or "unknown").upper()
    claim_text = str(claim.get("claim") or "")
    run_id = claim.get("run_id") or "—"
    job_id = claim.get("job_id") or "—"
    action_id = evidence.get("action_id") or "—"
    source = evidence.get("source") or "—"
    integrity = ledger.get("integrity") or "—"
    digest = proof.get("content_sha256") or "—"
    valid = result.get("valid")
    if valid is None:
        valid = status == "VERIFIED"

    lines = [
        "## Habitat Proof",
        "",
        f"**Claim:** {claim_text}",
        f"**Status:** `{status}`",
        f"**Run / Job:** `{run_id}` / `{job_id}`",
        f"**Evidence:** {source} · action `{action_id}` · ledger `{integrity}`",
        "",
        "```bash",
        f"python tools/verify_proof.py {proof_filename}",
        f"# → {'VALID' if valid else 'INVALID'}",
        "```",
        "",
        f"Digest: `{digest}`",
        "",
        "Assurance: structural · integrity · consistency established inside Habitat's evidence boundary. "
        "External truth and publisher trust are not established by this card alone.",
        "",
    ]
    return "\n".join(lines)
