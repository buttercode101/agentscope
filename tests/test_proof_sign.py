import hashlib
import json

import pytest

from habitat.proof_sign import generate_keypair, sign_proof, verify_signed_proof


def _digest(bundle):
    digest_input = dict(bundle)
    digest_input.pop("generated_at", None)
    return hashlib.sha256(json.dumps(digest_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def test_signed_proof_round_trip():
    pytest.importorskip("cryptography")
    private, _ = generate_keypair()
    bundle = {
        "proof_version": "1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "content_sha256": "abc",
        "claim": {"id": "c1", "status": "verified"},
    }
    signed = sign_proof(bundle, private, "test-key", "agent-1")
    assert signed["signature"]["algorithm"] == "Ed25519"
    assert signed["signature"]["key_id"] == "test-key"
    assert signed["signature"]["agent_id"] == "agent-1"
    assert verify_signed_proof(signed)


def test_signed_proof_tamper_is_rejected():
    pytest.importorskip("cryptography")
    private, _ = generate_keypair()
    signed = sign_proof({"proof_version": "1", "content_sha256": "abc"}, private)
    signed["content_sha256"] = "changed"
    assert not verify_signed_proof(signed)


def test_signed_proof_preserves_full_bundle_content():
    pytest.importorskip("cryptography")
    private, _ = generate_keypair()
    bundle = {
        "proof_version": "1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "claim": {"id": "c1", "status": "verified"},
        "ledger": {"integrity": "intact", "actions": []},
    }
    bundle["content_sha256"] = _digest(bundle)
    signed = sign_proof(bundle, private, "test-key")
    assert signed["content_sha256"] == bundle["content_sha256"]
    assert verify_signed_proof(signed)
