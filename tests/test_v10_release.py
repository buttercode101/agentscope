import json, os, threading, time
from urllib.request import Request,urlopen
from habitat.schema import Habitat,Job,Action,utcnow
from habitat.store import Store
from habitat.events import ingest_event,signature_for
from habitat.doctor import diagnose
from habitat.backup import backup,restore

def make(tmp_path):
 s=Store(tmp_path/'h.db');s.save_habitat(Habitat('h','H'));s.save_job(Job('j','h','J',enabled=True,command='echo ok'));return s

def test_invalid_signature_and_replay(tmp_path):
 s=make(tmp_path);body=json.dumps({'id':'e1','type':'job.completed','habitat_id':'h','job_id':'j','run_id':'r1'}).encode()
 try: ingest_event(s,body,'bad','secret')
 except PermissionError: pass
 else: assert False
 r=ingest_event(s,body,signature_for('secret',body),'secret');assert r['duplicate'] is False
 r=ingest_event(s,body,signature_for('secret',body),'secret');assert r['duplicate'] is True
 s.close()

def test_agent_permissions(tmp_path):
 s=make(tmp_path);s.save_agent('a1','h','Agent',True,['submit_events'],'agent-secret')
 body=json.dumps({'id':'e2','type':'job.completed','habitat_id':'h','job_id':'j','run_id':'r2','agent_id':'a1'}).encode()
 try:ingest_event(s,body,signature_for('secret',body),'secret',True,'a1','wrong')
 except PermissionError:pass
 else:assert False
 assert ingest_event(s,body,signature_for('secret',body),'secret',True,'a1','agent-secret')['accepted']
 s.close()

def test_claim_requires_run_over_network(tmp_path):
 s=make(tmp_path);body=json.dumps({'id':'e3','type':'claim.submitted','habitat_id':'h','job_id':'j','action':'run_job','claim':'done','expected_status':'ok'}).encode();r=ingest_event(s,body,signature_for('secret',body),'secret');assert r['claim_status']=='inconclusive';s.close()

def test_backup_restore(tmp_path):
 s=make(tmp_path);s.close();b=backup(tmp_path/'h.db',tmp_path/'backup.db');assert b.exists();restore(b,tmp_path/'restored.db');r=Store(tmp_path/'restored.db');assert r.habitat().id=='h';r.close()
def test_doctor_reports_core_checks(tmp_path,monkeypatch):
 s=make(tmp_path);s.close();monkeypatch.setenv('HABITAT_WEBHOOK_SECRET','x');checks=diagnose(tmp_path/'h.db');assert all(ok for _,ok,_ in checks)
def test_http_server_signed_event(tmp_path):
    from habitat.server import make_handler
    from http.server import ThreadingHTTPServer
    s=make(tmp_path);s.close();server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(str(tmp_path/'h.db'),'secret',True));t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    try:
        body=json.dumps({'id':'e4','type':'job.completed','habitat_id':'h','job_id':'j','run_id':'r4'}).encode();req=Request(f'http://127.0.0.1:{server.server_port}/v1/events',data=body,method='POST',headers={'Content-Type':'application/json','X-Habitat-Signature':signature_for('secret',body)});r=urlopen(req);assert r.status==202
        r=urlopen(f'http://127.0.0.1:{server.server_port}/v1/status');data=json.loads(r.read());assert data['jobs']==1
    finally:server.shutdown();server.server_close()
def test_shell_adapter_uses_argv_by_default():
    from habitat.adapters import ShellAdapter
    r=ShellAdapter().execute('python -c "print(2+3)"');assert r.ok and r.stdout.strip()=='5'
def test_http_dashboard_is_live_surface(tmp_path):
    from habitat.server import make_handler
    from http.server import ThreadingHTTPServer
    s=make(tmp_path);s.close();server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(str(tmp_path/'h.db'),'secret',True));t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    try:
        r=urlopen(f'http://127.0.0.1:{server.server_port}/dashboard');body=r.read().decode();assert 'Demo' in body or 'H' in body;assert 'Jobs &amp; health' in body or 'Jobs & health' in body
    finally:server.shutdown();server.server_close()
def test_tampered_action_ledger_cannot_verify_claim(tmp_path):
    from habitat.claims import Claim
    from habitat.verify import verify_claim
    s=make(tmp_path); s.save_action(Action('a','h',utcnow(),'agent','run_job','ok','j',{},'r1'))
    s.conn.execute("UPDATE action SET status='failed' WHERE id='a'"); s.conn.commit()
    c=Claim.new('h','done','j','run_job','ok'); c.run_id='r1'; s.save_claim(c)
    out=verify_claim(s,c); assert out.status=='inconclusive'; assert out.evidence['reason']=='action_ledger_integrity_check_failed'; s.close()

def test_policy_can_only_downgrade_verified_claim(tmp_path):
    from habitat.claims import Claim
    from habitat.verify import verify_claim
    from habitat.policy import EvidencePolicy
    s=make(tmp_path); s.save_action(Action('a','h',utcnow(),'agent','run_job','ok','j',{},'r1'))
    c=Claim.new('h','done','j','run_job','ok'); c.run_id='r1'; s.save_claim(c)
    policy=EvidencePolicy('strict', required_detail_keys=('deployment_id',))
    out=verify_claim(s,c,policy=policy)
    assert out.status=='rejected'
    assert out.evidence['policy']['status']=='denied'
    s.close()

def test_policy_does_not_turn_missing_evidence_into_verified(tmp_path):
    from habitat.claims import Claim
    from habitat.verify import verify_claim
    from habitat.policy import EvidencePolicy
    s=make(tmp_path); c=Claim.new('h','done','j','run_job','ok'); c.run_id='missing'; s.save_claim(c)
    out=verify_claim(s,c,policy=EvidencePolicy('strict', required_action='run_job'))
    assert out.status != 'verified'
    s.close()
