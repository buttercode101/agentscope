"""Agent claims: assertions that Habitat can verify against trusted state."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
import uuid
from .schema import utcnow

ClaimStatus = Literal["pending", "verified", "rejected", "inconclusive"]

@dataclass
class Claim:
    id: str
    habitat_id: str
    job_id: str | None
    claim: str
    action: str | None = None
    expected_status: str = "ok"
    created_at: datetime = field(default_factory=utcnow)
    verified_at: datetime | None = None
    status: ClaimStatus = "pending"
    evidence: dict[str, Any] = field(default_factory=dict)
    run_id: str | None = None

    @classmethod
    def new(cls, habitat_id: str, claim: str, job_id: str | None = None,
            action: str | None = None, expected_status: str = "ok") -> "Claim":
        return cls(str(uuid.uuid4()), habitat_id, job_id, claim, action, expected_status)
