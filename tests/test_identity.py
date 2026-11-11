from datetime import datetime, timezone, timedelta

import pytest

from habitat.identity import AgentIdentity, require_active
from habitat.trust import TrustedKey, TrustRegistry


def test_identity_disable_enable_and_revoke():
    now = datetime.now(timezone.utc)
    identity = AgentIdentity("agent-1", "worker", created_at=now)
    assert identity.usable
    disabled = identity.disable(now)
    assert not disabled.usable
    with pytest.raises(PermissionError):
        require_active(disabled)
    enabled = disabled.enable()
    assert enabled.usable
    revoked = enabled.revoke(now)
    assert not revoked.usable
    with pytest.raises(ValueError):
        revoked.enable()


def test_trusted_key_can_be_bound_to_specific_agent():
    registry = TrustRegistry([TrustedKey("k1", "pub", agent_id="agent-1")])
    assert registry.is_trusted("k1", "pub", agent_id="agent-1")
    assert not registry.is_trusted("k1", "pub", agent_id="agent-2")


def test_expired_key_is_not_trusted():
    expiry = datetime.now(timezone.utc) - timedelta(seconds=1)
    registry = TrustRegistry([TrustedKey("k1", "pub", expires_at=expiry)])
    assert not registry.is_trusted("k1", "pub")
