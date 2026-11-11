from datetime import timedelta

from habitat.claims import Claim
from habitat.events import Action
from habitat.policy import EvidencePolicy
from habitat.schema import Habitat, utcnow
from habitat.store import Store
from habitat.verify import verify_claim


def make_store(tmp_path):
    store = Store(tmp_path / "habitat.db")
    store.save_habitat(Habitat("h1", "Test Habitat"))
    return store


def test_policy_cannot_be_bypassed_when_no_trusted_action(tmp_path):
    store = make_store(tmp_path)
    claim = Claim.new(store.habitat().id, "deploy", "job-1", "deploy", "ok")
    policy = EvidencePolicy("fresh", required_source="habitat_trusted_ledger")
    result = verify_claim(store, claim, policy=policy)
    assert result.status in {"rejected", "inconclusive"}
    assert "policy" not in result.evidence
    store.close()


def test_policy_downgrades_verified_ledger_evidence(tmp_path):
    store = make_store(tmp_path)
    store.save_action(Action("a1", store.habitat().id, utcnow() - timedelta(minutes=10), "agent-1", "deploy", "ok", "job-1", {}, "run-1"))
    claim = Claim.new(store.habitat().id, "deploy", "job-1", "deploy", "ok")
    claim.run_id = "run-1"
    policy = EvidencePolicy("fresh", required_source="habitat_trusted_ledger", max_age_seconds=60)
    result = verify_claim(store, claim, policy=policy)
    assert result.status == "rejected"
    assert result.evidence["policy"]["status"] == "denied"
    assert "evidence_stale" in result.evidence["policy"]["reasons"]
    store.close()
