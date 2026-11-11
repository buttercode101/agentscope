import pytest
from datetime import datetime, timezone, timedelta

from habitat.proof_sign import generate_keypair, sign_proof
from habitat.trust import TrustRegistry, TrustedKey

pytest.importorskip("cryptography")


def test_registry_requires_explicit_key_trust():
    private, public = generate_keypair()
    bundle = sign_proof({"proof_version": "1", "content_sha256": "abc"}, private, "agent-key")
    registry = TrustRegistry([TrustedKey("agent-key", public)])
    assert registry.verify(bundle)


def test_registry_rejects_revoked_or_expired_key():
    private, public = generate_keypair()
    bundle = sign_proof({"proof_version": "1"}, private, "agent-key")
    registry = TrustRegistry([TrustedKey("agent-key", public, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))])
    assert not registry.verify(bundle)
    registry.add(TrustedKey("agent-key", public))
    assert registry.verify(bundle)
    registry.revoke("agent-key")
    assert not registry.verify(bundle)


def test_registry_enforces_bound_agent_identity():
    private, public = generate_keypair()
    bundle = sign_proof({"proof_version": "1"}, private, "agent-key", agent_id="agent-a")
    registry = TrustRegistry([TrustedKey("agent-key", public, agent_id="agent-a")])
    assert registry.verify(bundle)
    assert not registry.verify(bundle, agent_id="agent-b")


def test_registry_rejects_key_bound_to_different_signed_agent():
    private, public = generate_keypair()
    bundle = sign_proof({"proof_version": "1"}, private, "agent-key", agent_id="agent-b")
    registry = TrustRegistry([TrustedKey("agent-key", public, agent_id="agent-a")])
    assert not registry.verify(bundle)


def test_registry_does_not_trust_unbound_embedded_agent_attribution():
    private, public = generate_keypair()
    bundle = sign_proof({"proof_version": "1"}, private, "agent-key", agent_id="agent-a")
    registry = TrustRegistry([TrustedKey("agent-key", public)])
    assert not registry.verify(bundle)
    assert registry.verify(sign_proof({"proof_version": "1"}, private, "agent-key"))
