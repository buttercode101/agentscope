from datetime import datetime, timezone, timedelta

from habitat.policy import EvidencePolicy, apply_policy


def test_policy_rejects_evidence_beyond_future_skew():
    now = datetime.now(timezone.utc)
    policy = EvidencePolicy("deploy", max_future_seconds=30)
    evidence = {"timestamp": (now + timedelta(minutes=2)).isoformat()}
    result = apply_policy(policy, evidence, now)
    assert result["status"] == "denied"
    assert "evidence_from_future" in result["reasons"]


def test_policy_allows_small_clock_skew():
    now = datetime.now(timezone.utc)
    policy = EvidencePolicy("deploy", max_future_seconds=30)
    evidence = {"timestamp": (now + timedelta(seconds=10)).isoformat()}
    assert apply_policy(policy, evidence, now)["status"] == "allowed"
