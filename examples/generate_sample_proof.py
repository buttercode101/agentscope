"""Generate a deterministic sample proof fixture for CI and docs.

Writes:
  examples/fixtures/sample_proof.json

Uses fixed timestamps and claim ID so the content digest is stable across runs
on the same code. Run:

    pip install -e .
    python examples/generate_sample_proof.py

Then commit the fixture and let verify-proof.yml re-check it on every push.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from habitat.claims import Claim
from habitat.proof import build_proof
from habitat.proof_verify import verify_proof
from habitat.schema import Action, Habitat, Job
from habitat.store import Store

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "fixtures" / "sample_proof.json"

FIXED_TS = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
FIXED_CLAIM_ID = "00000000-0000-4000-8000-000000000001"
FIXED_ACTION_ID = "act-001"
FIXED_RUN_ID = "run-42"


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "fixture.db")
        store.save_habitat(Habitat("demo", "Demo Crew"))
        store.save_job(
            Job("deploy", "demo", "Deploy service", enabled=True, command="echo deploy")
        )
        store.save_action(
            Action(
                id=FIXED_ACTION_ID,
                habitat_id="demo",
                timestamp=FIXED_TS,
                actor="agent",
                action="deploy",
                status="ok",
                job_id="deploy",
                details={"target": "production", "version": "1.2.3"},
                run_id=FIXED_RUN_ID,
            )
        )

        claim = Claim(
            id=FIXED_CLAIM_ID,
            habitat_id="demo",
            job_id="deploy",
            claim="deployed v1.2.3 to production",
            action="deploy",
            expected_status="ok",
            created_at=FIXED_TS,
            status="pending",
            evidence={},
            run_id=FIXED_RUN_ID,
        )
        store.save_claim(claim)

        from habitat.verify import verify_claim

        verified = verify_claim(store, claim)
        if verified.status != "verified":
            print(json.dumps(verified.evidence, indent=2, default=str), file=sys.stderr)
            store.close()
            return 1

        verified.verified_at = FIXED_TS
        store.save_claim(verified)

        proof = build_proof(store, verified.id)
        proof["generated_at"] = FIXED_TS.isoformat()

        result = verify_proof(proof)
        if not result.get("valid"):
            print(json.dumps(result, indent=2), file=sys.stderr)
            store.close()
            return 1

        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(
            json.dumps(proof, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        store.close()

        print(f"Wrote {OUT.relative_to(ROOT)}")
        print(f"content_sha256: {proof['content_sha256']}")
        print("Standalone verification: VALID")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
