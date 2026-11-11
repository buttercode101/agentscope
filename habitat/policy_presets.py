"""Common evidence-policy presets for Hermes / agentscope failure modes.

These presets only constrain evidence Habitat already has. They never invent
positive evidence. Use them when a claim must survive the exact failure modes
already measured by agentscope (config drift, silent skip, auth failure, streak).
"""
from __future__ import annotations

from .policy import EvidencePolicy


def trusted_ledger_with_run() -> EvidencePolicy:
    return EvidencePolicy(
        name="trusted_ledger_with_run",
        required_source="habitat_trusted_ledger",
        require_run_id=True,
        max_age_seconds=7 * 24 * 3600,
    )


def no_drift_skip() -> EvidencePolicy:
    """Reject evidence that records a drift_skip or silent skip outcome."""
    return EvidencePolicy(
        name="no_drift_skip",
        required_source="habitat_trusted_ledger",
        required_status="ok",
        require_run_id=True,
        metadata={"reject_reasons": ["drift_skip", "config_drift", "silent_skip"]},
    )


def auth_ok() -> EvidencePolicy:
    return EvidencePolicy(
        name="auth_ok",
        required_source="habitat_trusted_ledger",
        required_status="ok",
        require_run_id=True,
        metadata={"reject_status_prefixes": ["auth_", "401", "403"]},
    )


def recent_action(max_age_seconds: int = 3600) -> EvidencePolicy:
    return EvidencePolicy(
        name="recent_action",
        required_source="habitat_trusted_ledger",
        require_run_id=True,
        max_age_seconds=max_age_seconds,
    )


PRESETS = {
    "trusted_ledger_with_run": trusted_ledger_with_run,
    "no_drift_skip": no_drift_skip,
    "auth_ok": auth_ok,
    "recent_action": recent_action,
}
