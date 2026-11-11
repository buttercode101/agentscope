import json, threading, time
from http.client import HTTPConnection
from habitat.schema import Habitat, Action, Job, utcnow
from habitat.store import Store
from habitat.events import signature_for, ingest_event
from habitat.server import make_handler
from http.server import ThreadingHTTPServer


def make_store(tmp_path):
    s=Store(tmp_path/'h.db'); now=utcnow(); s.save_habitat(Habitat('h','H','test',now,now,'healthy')); s.save_job(Job('job-1','h','sync',None,True,'echo hi')); return s


def test_signed_event_and_idempotency(tmp_path):
    s=make_store(tmp_path); body=json.dumps({'id':'evt-1','type':'job.completed','habitat_id':'h','job_id':'job-1'}).encode(); sig=signature_for('secret',body)
    out=ingest_event(s,body,sig,'secret'); assert out['accepted'] and not out['duplicate']; assert s.jobs()[0].last_status=='ok'
    out2=ingest_event(s,body,sig,'secret'); assert out2['duplicate']; assert len(s.events())==1; s.close()


def test_invalid_signature_rejected(tmp_path):
    s=make_store(tmp_path); body=b'{"id":"evt-2","type":"job.completed","habitat_id":"h","job_id":"job-1"}'
    try: ingest_event(s,body,'bad','secret')
    except PermissionError as e: assert str(e)=='invalid_signature'
    else: assert False
    assert not s.events(); s.close()


def test_claim_event_auto_verifies_against_trusted_action(tmp_path):
    s=make_store(tmp_path); s.save_action(Action('a','h',utcnow(),'agent','run_job','ok','job-1',{},'run-1'))
    body=json.dumps({'id':'evt-3','type':'claim.submitted','habitat_id':'h','job_id':'job-1','action':'run_job','claim':'sync completed','expected_status':'ok','run_id':'run-1'}).encode()
    out=ingest_event(s,body,signature_for('secret',body),'secret'); assert out['claim_status']=='verified'; s.close()


def test_server_http(tmp_path):
    s=make_store(tmp_path); s.close(); server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(str(tmp_path/'h.db'),'secret',True)); t=threading.Thread(target=server.serve_forever,daemon=True); t.start();
    try:
        c=HTTPConnection('127.0.0.1',server.server_port); c.request('GET','/v1/status'); r=c.getresponse(); assert r.status==200; data=json.loads(r.read()); assert data['status']=='healthy'; c.close()
        body=json.dumps({'id':'evt-4','type':'job.completed','habitat_id':'h','job_id':'job-1'}).encode(); c=HTTPConnection('127.0.0.1',server.server_port); c.request('POST','/v1/events',body,{'Content-Type':'application/json','X-Habitat-Signature':signature_for('secret',body)}); r=c.getresponse(); assert r.status==202; r.read(); c.close()
    finally: server.shutdown(); server.server_close()
