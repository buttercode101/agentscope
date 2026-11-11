import tempfile
from pathlib import Path
from habitat.config import load_config
from habitat.schema import Habitat, Job
from habitat.store import Store
from habitat.signals import detect, health_status
from habitat.generate import render_dashboard

def test_config_loads_jobs():
    cfg=load_config(Path(__file__).parents[1]/'examples/simple.yaml')
    assert cfg['name']=='Demo Crew'; assert len(cfg['jobs'])==3; assert cfg['jobs'][0]['enabled'] is True

def test_signal_detection():
    h=Habitat('h','H'); jobs=[Job('j','h','repo',enabled=True,failure_streak=3,last_error='auth failed')]
    sig=detect(h,jobs); codes={s.code for s in sig}; assert {'failure_streak','auth_failure'} <= codes; assert health_status(jobs,sig)=='needs_attention'

def test_store_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        s=Store(Path(d)/'state.db'); h=Habitat('h','H'); s.save_habitat(h); s.save_job(Job('j','h','job')); assert s.habitat().name=='H'; assert s.jobs()[0].name=='job'; s.close()

def test_dashboard_escapes_html():
    h=Habitat('h','<bad>'); html=render_dashboard(h,[],[],[],title='<x>'); assert '&lt;x&gt;' in html; assert '<x>' not in html
