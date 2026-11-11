"""Agent identity lifecycle primitives.

Identity is intentionally separate from authorization. A stable agent ID identifies
an actor; permissions and signing-key trust decide what that actor may do.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

IdentityState = Literal["active", "disabled", "revoked"]


@dataclass(frozen=True)
class AgentIdentity:
    agent_id: str
    name: str
    state: IdentityState = "active"
    key_id: str | None = None
    created_at: datetime | None = None
    disabled_at: datetime | None = None
    revoked_at: datetime | None = None

    @property
    def usable(self) -> bool:
        return self.state == "active"

    def disable(self, now: datetime | None = None) -> "AgentIdentity":
        return AgentIdentity(self.agent_id, self.name, "disabled", self.key_id,
                             self.created_at, now or datetime.now(timezone.utc), self.revoked_at)

    def enable(self) -> "AgentIdentity":
        if self.state == "revoked":
            raise ValueError("revoked identities cannot be re-enabled; create a new identity")
        return AgentIdentity(self.agent_id, self.name, "active", self.key_id,
                             self.created_at, None, self.revoked_at)

    def revoke(self, now: datetime | None = None) -> "AgentIdentity":
        return AgentIdentity(self.agent_id, self.name, "revoked", self.key_id,
                             self.created_at, self.disabled_at, now or datetime.now(timezone.utc))


def require_active(identity: AgentIdentity) -> None:
    if not identity.usable:
        raise PermissionError(f"agent_identity_{identity.state}")
