"""Demonstrate habitat prove: claim → verify → portable proof → card.

Usage (after installing Habitat):

    python examples/prove_run.py

This script creates a temporary habitat, records a trusted action, then uses
the same path as `habitat prove` to export a proof.json and a markdown card.
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from habitat.claims import Claim
from habitat.proof import build_proof
from habitat.proof_card import render_proof_card
from habitat.proof_verify import verify_proof
from habitat.schema import Action, Habitat, Job
from habitat.store import Store
from habitat.verify import verify_claim


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "demo.db"
        store = Store(db)
        now = datetime.now(timezone.utc)

        store.save_habitat(Habitat("demo", "Demo Crew"))
        store.save_job(Job("deploy", "demo", "Deploy service", enabled=True, command="echo deploy"))

        store.save_action(
            Action(
                id="act-001",
                habitat_id="demo",
                timestamp=now,
                actor="agent",
                action="deploy",
                status="ok",
                job_id="deploy",
                details={"target": "production", "version": "1.2.3"},
                run_id="run-42",
            )
        )
        print("✓ Recorded trusted action for run-42")

        claim = Claim.new(
            "demo",
            "deployed v1.2.3 to production",
            job_id="deploy",
            action="deploy",
            expected_status="ok",
        )
        claim.run_id = "run-42"
        store.save_claim(claim)

        verified = verify_claim(store, claim)
        print(f"✓ Claim status: {verified.status}")
        if verified.status != "verified":
            print(json.dumps(verified.evidence, indent=2, default=str))
            store.close()
            return 1

        proof = build_proof(store, verified.id)
        proof_path = Path(tmp) / "proof.json"
        proof_path.write_text(
            json.dumps(proof, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        print(f"✓ Wrote {proof_path}")

        result = verify_proof(proof)
        card = render_proof_card(proof, result)
        card_path = Path(tmp) / "proof.md"
        card_path.write_text(card, encoding="utf-8")
        print(f"✓ Wrote {card_path}")
        print()
        print(card)
        print()
        print("Standalone verification:", "VALID" if result.get("valid") else "INVALID")

        store.close()
        return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
