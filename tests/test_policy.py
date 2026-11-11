from datetime import datetime, timezone, timedelta

from habitat.policy import EvidencePolicy, apply_policy


def test_policy_accepts_matching_fresh_evidence():
    now = datetime.now(timezone.utc)
    policy = EvidencePolicy("deploy", required_source="habitat_trusted_ledger", required_action="deploy", required_status="ok", require_run_id=True, max_age_seconds=60)
    evidence = {"source": "habitat_trusted_ledger", "action": "deploy", "status": "ok", "run_id": "r1", "timestamp": now.isoformat()}
    assert apply_policy(policy, evidence, now)["status"] == "allowed"


def test_policy_rejects_stale_or_missing_requirements():
    now = datetime.now(timezone.utc)
    policy = EvidencePolicy("deploy", required_action="deploy", require_run_id=True, max_age_seconds=60)
    evidence = {"action": "publish", "status": "ok", "timestamp": (now - timedelta(minutes=2)).isoformat()}
    result = apply_policy(policy, evidence, now)
    assert result["status"] == "denied"
    assert "required_action_missing" in result["reasons"]
    assert "run_id_required" in result["reasons"]
    assert "evidence_stale" in result["reasons"]
