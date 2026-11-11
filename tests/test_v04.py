import json
from habitat.schema import Habitat, Action, utcnow
from habitat.store import Store
from habitat.claims import Claim
from habitat.verify import verify_claim
from habitat.adapters import JSONFileEvidenceAdapter


def make_store(tmp_path):
    s=Store(tmp_path/'h.db'); now=utcnow(); s.save_habitat(Habitat('h','H','test',now,now,'healthy')); return s


def test_external_file_evidence_verifies(tmp_path):
    s=make_store(tmp_path)
    p=tmp_path/'evidence.json'; p.write_text(json.dumps({'deployment': {'status':'ok','version':'1.2.3'}}))
    c=Claim.new('h','deployment completed',action='deploy')
    s.save_claim(c)
    out=verify_claim(s,c,JSONFileEvidenceAdapter(p),'deployment')
    assert out.status=='verified'; assert out.evidence['data']['version']=='1.2.3'
    s.close()


def test_external_evidence_is_inconclusive_on_error(tmp_path):
    s=make_store(tmp_path); c=Claim.new('h','deployment completed',action='deploy'); s.save_claim(c)
    out=verify_claim(s,c,JSONFileEvidenceAdapter(tmp_path/'missing.json'),'deployment')
    assert out.status=='inconclusive'; s.close()


def test_trusted_ledger_beats_external_evidence(tmp_path):
    s=make_store(tmp_path); now=utcnow()
    s.save_action(Action('a','h',now,'agent','deploy','failed',None,{'error':'boom'}))
    c=Claim.new('h','deployment completed',action='deploy',expected_status='ok'); s.save_claim(c)
    out=verify_claim(s,c,JSONFileEvidenceAdapter(tmp_path/'missing.json'),'deployment')
    assert out.status=='rejected'; assert out.evidence['reason']=='matching_action_has_different_status'; s.close()
