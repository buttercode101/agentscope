"""End-to-end demonstration of Habitat's accountability loop.

This script:
1. Creates a temporary Habitat and records trusted actions
2. Creates and verifies a claim against the ledger
3. Exports a portable proof bundle
4. Verifies the proof with the standalone verifier (no DB access)

It is intentionally self-contained so a newcomer can run:

    python examples/full_proof_flow.py

and see the full claim → evidence → proof → independent verification path.
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from habitat.claims import Claim
from habitat.proof import build_proof
from habitat.proof_verify import verify_proof
from habitat.schema import Action, Habitat, Job
from habitat.store import Store
from habitat.verify import verify_claim


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "demo.db"
        store = Store(db_path)

        now = datetime.now(timezone.utc)
        store.save_habitat(Habitat("demo", "Demo Crew", "local", now, now))
        store.save_job(Job("deploy", "demo", "Deploy service", enabled=True, command="echo deploy"))

        # Record a trusted action
        action = Action(
            id="act-001",
            habitat_id="demo",
            timestamp=now,
            actor="worker-1",
            action="deploy",
            status="ok",
            job_id="deploy",
            details={"target": "production", "version": "1.2.3"},
            run_id="run-42",
        )
        store.save_action(action)
        print("✓ Recorded trusted action")

        # Create and verify a claim bound to the same run
        claim = Claim.new(
            habitat_id="demo",
            claim="production deployment of version 1.2.3 completed successfully",
            job_id="deploy",
            action="deploy",
            expected_status="ok",
        )
        claim.run_id = "run-42"
        store.save_claim(claim)

        verified = verify_claim(store, claim)
        print(f"✓ Claim status: {verified.status}")
        assert verified.status == "verified", verified.evidence

        # Build a portable proof
        proof = build_proof(store, verified.id)
        proof_path = Path(tmp) / "proof.json"
        proof_path.write_text(
            json.dumps(proof, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        print(f"✓ Wrote portable proof → {proof_path}")

        # Independent verification (no database)
        result = verify_proof(proof)
        print("✓ Standalone verification result:")
        print(json.dumps(result, indent=2, sort_keys=True))

        store.close()

        if result.get("valid"):
            print("\nSUCCESS — the proof is independently verifiable.")
            return 0

        print("\nFAILURE — proof did not verify.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
