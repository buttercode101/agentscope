"""Minimal standard-library Habitat event sender.

Usage:
  HABITAT_WEBHOOK_SECRET=... python examples/send_event.py http://127.0.0.1:8787
"""
import hashlib,hmac,json,os,sys,urllib.request,uuid
base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8787'
secret=os.environ.get('HABITAT_WEBHOOK_SECRET')
if not secret: raise SystemExit('Set HABITAT_WEBHOOK_SECRET first')
payload={'id':str(uuid.uuid4()),'type':'agent.heartbeat','habitat_id':'demo'}
body=json.dumps(payload,separators=(',',':')).encode();sig=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
req=urllib.request.Request(base.rstrip('/')+'/v1/events',data=body,method='POST',headers={'Content-Type':'application/json','X-Habitat-Signature':sig})
with urllib.request.urlopen(req,timeout=10) as r: print(r.read().decode())
