"""Deterministic evidence policies for deciding whether a claim is trustworthy enough."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class EvidencePolicy:
    """A small, serializable set of requirements for verified claims.

    Policies never create evidence. They only constrain evidence already returned
    by Habitat verification, so a policy failure cannot turn missing evidence
    into a positive result.
    """
    name: str
    required_source: str | None = None
    required_action: str | None = None
    required_status: str | None = None
    require_run_id: bool = False
    max_age_seconds: int | None = None
    max_future_seconds: int = 30
    required_detail_keys: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


def evaluate_policy(policy: EvidencePolicy, evidence: dict[str, Any], now: datetime | None = None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    source = evidence.get("source")
    if policy.required_source and source != policy.required_source:
        reasons.append("required_source_missing")
    if policy.required_action and evidence.get("action") != policy.required_action:
        reasons.append("required_action_missing")
    if policy.required_status and evidence.get("status") != policy.required_status:
        reasons.append("required_status_missing")
    if policy.require_run_id and not evidence.get("run_id"):
        reasons.append("run_id_required")
    if policy.required_detail_keys:
        details = evidence.get("details")
        if not isinstance(details, dict):
            reasons.append("details_required")
        else:
            for key in policy.required_detail_keys:
                if key not in details:
                    reasons.append(f"detail_missing:{key}")
    if policy.max_age_seconds is not None or policy.max_future_seconds is not None:
        timestamp = evidence.get("timestamp")
        if not timestamp:
            if policy.max_age_seconds is not None or policy.max_future_seconds is not None:
                reasons.append("timestamp_required")
        else:
            try:
                observed = datetime.fromisoformat(timestamp)
                current = now or datetime.now(observed.tzinfo)
                age = current - observed
                if policy.max_age_seconds is not None and age > timedelta(seconds=policy.max_age_seconds):
                    reasons.append("evidence_stale")
                if policy.max_future_seconds is not None and age < -timedelta(seconds=policy.max_future_seconds):
                    reasons.append("evidence_from_future")
            except (TypeError, ValueError):
                reasons.append("invalid_timestamp")
    return not reasons, reasons


def apply_policy(policy: EvidencePolicy, evidence: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Return a deterministic policy decision without mutating the claim."""
    passed, reasons = evaluate_policy(policy, evidence, now)
    return {"policy": policy.name, "status": "allowed" if passed else "denied", "reasons": reasons}
