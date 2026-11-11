import json
from importlib import metadata

from habitat.adapters import JSONFileEvidenceAdapter
from habitat.claims import Claim
from habitat.store import Store
from habitat.verify import verify_claim
from habitat.runtime import due


def setup(tmp_path):
    s = Store(tmp_path / 'habitat.db')
    from habitat.schema import Habitat, Job, utcnow
    now = utcnow()
    s.save_habitat(Habitat('h', 'test', 'unknown', now, now))
    s.save_job(Job('j', 'h', 'job', None, True, None))
    return s


def test_simple_schedule_due(tmp_path):
    s = setup(tmp_path); assert due(s.jobs()[0]); s.close()


def test_external_evidence_predicate(tmp_path):
    f=tmp_path/'e.json'; f.write_text(json.dumps({'result':{'status':'ok','id':'42'}})); s=setup(tmp_path); c=Claim.new('h','external'); s.save_claim(c); out=verify_claim(s,c,JSONFileEvidenceAdapter(f),'result',{'status':'ok','id':'42'}); assert out.status=='verified'; c=Claim.new('h','external'); s.save_claim(c); out=verify_claim(s,c,JSONFileEvidenceAdapter(f),'result',{'status':'failed'}); assert out.status=='rejected'; s.close()


def test_package_metadata_and_entrypoint():
    assert metadata.version('habitat') == '1.3.0'
    entry_points = metadata.entry_points(group='console_scripts')
    habitat = next(ep for ep in entry_points if ep.name == 'habitat')
    assert habitat.value == 'habitat.__main__:main'
