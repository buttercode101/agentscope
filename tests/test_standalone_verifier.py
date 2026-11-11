import hashlib
import json
import subprocess
import sys
from pathlib import Path

from habitat.proof_verify import verify_proof

ROOT = Path(__file__).resolve().parents[1]
STANDALONE = ROOT / "tools" / "verify_proof.py"


def _bundle():
    bundle = {
        "proof_version": "1", "generated_at": "2026-01-01T00:00:00+00:00",
        "claim": {"id": "c1", "habitat_id": "h1", "job_id": "j1", "claim": "deploy happened", "action": "deploy", "expected_status": "ok", "created_at": "2026-01-01T00:00:00+00:00", "verified_at": "2026-01-01T00:00:01+00:00", "status": "verified", "run_id": "r1", "evidence": {"source": "habitat_trusted_ledger", "status": "ok", "action_id": "a1"}},
        "ledger": {"integrity": "intact", "actions": [{"id": "a1", "habitat_id": "h1", "job_id": "j1", "timestamp": "2026-01-01T00:00:00+00:00", "actor": "agent", "action": "deploy", "status": "ok", "details": {}, "run_id": "r1"}]},
    }
    digest_input = dict(bundle); digest_input.pop("generated_at")
    bundle["content_sha256"] = hashlib.sha256(json.dumps(digest_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return bundle


def _run_standalone(bundle, tmp_path):
    path = tmp_path / "proof.json"; path.write_text(json.dumps(bundle), encoding="utf-8")
    completed = subprocess.run([sys.executable, str(STANDALONE), str(path)], capture_output=True, text=True, check=False)
    return completed.returncode, json.loads(completed.stdout)


def test_standalone_matches_canonical_on_valid_bundle(tmp_path):
    bundle = _bundle(); canonical = verify_proof(bundle); code, standalone = _run_standalone(bundle, tmp_path)
    assert code == 0; assert standalone == canonical


def test_standalone_preserves_signature_boundary(tmp_path):
    bundle = _bundle(); bundle["signature"] = {"algorithm": "Ed25519", "key_id": "k1", "agent_id": "a1", "public_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", "signature": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="}
    bundle["content_sha256"] = hashlib.sha256(json.dumps({k: v for k, v in bundle.items() if k not in {"generated_at", "content_sha256", "signature"}}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    canonical = verify_proof(bundle); code, standalone = _run_standalone(bundle, tmp_path)
    assert standalone["content_sha256"] == canonical["content_sha256"]
    assert standalone["assurance"]["publisher_trust"] == canonical["assurance"]["publisher_trust"]
    assert standalone["assurance"]["external_truth"] == canonical["assurance"]["external_truth"]
    # Both verifiers perform the same cryptographic check when the optional
    # dependency is present; an invalid signature must fail closed.
    assert standalone == canonical
    assert code == (0 if canonical["valid"] else 1)
    assert standalone["assurance"]["signature"] in {"invalid", "present-unverified"}



def test_standalone_matches_canonical_on_tampered_bundle(tmp_path):
    bundle = _bundle(); bundle["claim"]["action"] = "delete"; canonical = verify_proof(bundle); code, standalone = _run_standalone(bundle, tmp_path)
    assert code == 1; assert standalone == canonical
