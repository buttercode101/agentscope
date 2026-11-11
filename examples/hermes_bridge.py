#!/usr/bin/env python3
"""Minimal Hermes → Habitat bridge example.

Hermes (or any agent runner) already produces structured outcomes. This example
shows the smallest useful path:

  1. Record a trusted action for a run.
  2. Bind a claim to that run.
  3. Verify the claim against the Habitat ledger.
  4. Optionally export a portable proof + tip file.

Zero third-party dependencies. Drop this pattern into a Hermes post-action hook
or adapt the event shape to whatever Hermes already emits.
"""
from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from habitat.claims import Claim
from habitat.schema import Action, Habitat, Job
from habitat.store import Store
from habitat.verify import verify_claim
from habitat.proof import build_proof, export_proof
from habitat.proof_card import render_proof_card
from habitat.proof_verify import verify_proof
from habitat.anchor import tip_digest, write_tip_file


def record_and_prove(
    *,
    run_id: str,
    action_name: str,
    claim_text: str,
    status: str = "ok",
    details: dict | None = None,
    db_path: Path | None = None,
    export_dir: Path | None = None,
) -> dict:
    # Use a unique temp directory per invocation for concurrency safety
    if db_path is None:
        unique_suffix = f"{run_id}-{uuid.uuid4().hex[:8]}"
        db_path = Path(tempfile.mkdtemp(prefix=f"habitat-{unique_suffix}-")) / "habitat.db"
    
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    store = Store(db_path)
    now = datetime.now(timezone.utc)

    store.save_habitat(Habitat("hermes-local", "Hermes local", "hermes", now, now))
    store.save_job(Job("hermes-job", "hermes-local", "Hermes job", None, True, None))

    # Use unique action ID per run to prevent replay attacks
    unique_action_id = f"act-{run_id}-{uuid.uuid4().hex[:8]}"
    
    action = Action(
        id=unique_action_id,
        habitat_id="hermes-local",
        timestamp=now,
        actor="agent",
        action=action_name,
        status=status,  # type: ignore[arg-type]
        job_id="hermes-job",
        details=details or {},
        run_id=run_id,
    )
    store.save_action(action)

    # Use unique claim ID per run
    unique_claim_id = f"claim-{run_id}-{uuid.uuid4().hex[:8]}"
    
    claim = Claim(
        id=unique_claim_id,
        habitat_id="hermes-local",
        job_id="hermes-job",
        claim=claim_text,
        action=action_name,
        expected_status=status,
        created_at=now,
        run_id=run_id,
    )
    store.save_claim(claim)
    verify_claim(store, claim)
    claim = store.get_claim(claim.id)

    out = export_dir or db_path.parent
    out.mkdir(parents=True, exist_ok=True)
    proof_path = out / f"proof-{run_id}.json"
    card_path = out / f"proof-{run_id}.md"
    tip_path = out / f"tip-{run_id}.json"

    proof = export_proof(store, claim.id, str(proof_path))
    result = verify_proof(proof)
    card_path.write_text(render_proof_card(proof, result))
    write_tip_file(
        tip_digest(proof),
        tip_path,
        claim_id=claim.id,
        run_id=run_id,
        proof_path=str(proof_path),
    )
    return {
        "claim_id": claim.id,
        "status": claim.status,
        "proof": str(proof_path),
        "card": str(card_path),
        "tip": str(tip_path),
        "verification_valid": result.get("valid"),
    }


if __name__ == "__main__":
    result = record_and_prove(
        run_id="hermes-demo-1",
        action_name="deploy",
        claim_text="Hermes completed a verified deploy action",
        details={"source": "hermes", "env": "demo"},
    )
    print(json.dumps(result, indent=2))
