import pytest

crypto = pytest.importorskip("cryptography")

from habitat.proof_sign import generate_keypair, sign_proof
from habitat.trust import TrustedKey, TrustRegistry


def test_signed_proof_can_be_bound_to_agent():
    private, public = generate_keypair()
    bundle = {"claim": {"id": "c1"}, "verdict": "verified", "content_sha256": "abc"}
    signed = sign_proof(bundle, private, key_id="k1", agent_id="agent-1")
    registry = TrustRegistry([TrustedKey("k1", public, agent_id="agent-1")])
    assert registry.verify(signed)
    assert not registry.verify(signed, agent_id="agent-2")
