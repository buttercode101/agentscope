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


def _unicode_verifiable_bundle():
    from habitat.proof import _canonical

    bundle = {
        "proof_version": "1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "claim": {
            "id": "c1",
            "habitat_id": "h1",
            "job_id": None,
            "claim": "Déploiement réussi — 東京",
            "action": None,
            "expected_status": "ok",
            "created_at": "2026-01-01T00:00:00+00:00",
            "verified_at": None,
            "status": "inconclusive",
            "evidence": {"source": "external", "data": {"summary": "café"}},
            "run_id": None,
        },
        "ledger": {"integrity": "intact", "actions": []},
    }
    digest_input = dict(bundle)
    digest_input.pop("generated_at")
    bundle["content_sha256"] = hashlib.sha256(_canonical(digest_input).encode()).hexdigest()
    return bundle


def test_unicode_signed_bundle_uses_same_canonicalization_as_verifier():
    from habitat.proof_verify import verify_proof

    pytest.importorskip("cryptography")
    private, _ = generate_keypair()
    signed = sign_proof(_unicode_verifiable_bundle(), private, "test-key", "agent-1")

    assert verify_signed_proof(signed)
    result = verify_proof(signed)
    assert result["valid"] is True
    assert result["assurance"]["signature"] == "present-unverified"
    assert result["assurance"]["publisher_trust"] == "not-assessed"


def test_signing_install_extra_is_declared_and_matches_error_hint():
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert any(item.startswith("cryptography") for item in project["optional-dependencies"]["signing"])
    source = (root / "habitat" / "proof_sign.py").read_text(encoding="utf-8")
    assert "pip install 'agentscope[signing]'" in source
    assert "pip install 'habitat[signing]'" not in source
