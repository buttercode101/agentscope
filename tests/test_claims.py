from pathlib import Path
from habitat.store import Store
from habitat.schema import Habitat, Action, utcnow
from habitat.claims import Claim
from habitat.verify import verify_claim

def test_claim_verified_against_action(tmp_path: Path):
    s=Store(tmp_path/'db.sqlite'); h=Habitat('h','H'); s.save_habitat(h)
    a=Action('a','h',utcnow(),'agent','publish','ok','j1',{'url':'x'}); s.save_action(a)
    c=Claim.new('h','Agent says it published','j1','publish','ok'); s.save_claim(c)
    out=verify_claim(s,c); assert out.status=='verified'; assert out.evidence['action_id']=='a'; s.close()

def test_claim_rejected_without_trusted_action(tmp_path: Path):
    s=Store(tmp_path/'db.sqlite'); h=Habitat('h','H'); s.save_habitat(h)
    c=Claim.new('h','Agent says it deleted','j1','delete','ok'); out=verify_claim(s,c)
    assert out.status=='rejected'; s.close()
