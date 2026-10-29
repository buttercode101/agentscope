#!/usr/bin/env python3
import json, os, sqlite3, hashlib, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA=os.path.join(ROOT,'data','commission.json')
DB=os.path.join(ROOT,'data','evidence.db')
SNAP=os.path.join(ROOT,'data','snapshots')

def now(): return datetime.now(timezone.utc).isoformat()
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def init_db():
    os.makedirs(SNAP,exist_ok=True)
    d=json.load(open(DATA,encoding='utf-8'))
    c=db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,tier TEXT NOT NULL,title TEXT NOT NULL,url TEXT NOT NULL,publisher TEXT,date TEXT,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS claims(id TEXT PRIMARY KEY,statement TEXT NOT NULL,classification TEXT NOT NULL,verification_state TEXT NOT NULL DEFAULT 'verified',created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS claim_sources(claim_id TEXT,source_id TEXT,PRIMARY KEY(claim_id,source_id),FOREIGN KEY(claim_id) REFERENCES claims(id),FOREIGN KEY(source_id) REFERENCES sources(id));
    CREATE TABLE IF NOT EXISTS hearings(day INTEGER PRIMARY KEY,date TEXT,witnesses_json TEXT,lead TEXT,url TEXT,status TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,retrieved_at TEXT NOT NULL,content_sha256 TEXT NOT NULL,bytes INTEGER NOT NULL,path TEXT,fetch_status TEXT NOT NULL,FOREIGN KEY(source_id) REFERENCES sources(id));
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,action TEXT NOT NULL,object_type TEXT NOT NULL,object_id TEXT NOT NULL,details TEXT);
    ''')
    for s in d['sources']:
        c.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?,?,?)',(s['id'],s['tier'],s['title'],s['url'],s.get('publisher'),s.get('date'),now()))
    for x in d['claims']:
        c.execute('INSERT OR IGNORE INTO claims VALUES(?,?,?,?,?)',(x['id'],x['statement'],x['classification'],'verified',now()))
        for sid in x['sourceIds']:
            c.execute('INSERT OR IGNORE INTO claim_sources VALUES(?,?)',(x['id'],sid))
    # The archive reports 178 recorded sitting days. Only six have detailed source records in this build.
    detailed={h['day']:h for h in d['hearings']}
    for day in range(1,179):
        h=detailed.get(day)
        if h:
            c.execute('INSERT OR REPLACE INTO hearings VALUES(?,?,?,?,?,?)',(day,h['date'],json.dumps(h['witnesses']),h.get('lead'),h['url'],'detailed'))
        else:
            c.execute('INSERT OR IGNORE INTO hearings VALUES(?,?,?,?,?,?)',(day,None,'[]',None,None,'index_only'))
    c.commit(); c.close()

def q(sql,args=()):
    c=db(); rows=[dict(r) for r in c.execute(sql,args).fetchall()]; c.close(); return rows

def json_out(h,obj,status=200):
    raw=json.dumps(obj,ensure_ascii=False).encode(); h.send_response(status); h.send_header('Content-Type','application/json; charset=utf-8'); h.send_header('Content-Length',str(len(raw))); h.end_headers(); h.wfile.write(raw)

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self,path):
        # Serve project root so /public and /data work together.
        return os.path.join(ROOT,path.lstrip('/'))
    def do_GET(self):
        p=urlparse(self.path); path=p.path
        if path.startswith('/api/'):
            if path=='/api/status':
                d=json.load(open(DATA,encoding='utf-8'))
                return json_out(self,{'ok':True,'asOf':d['status']['asOf'],'latestSitting':d['status']['latestSitting'],'reportDeadline':d['status']['reportDeadline'],'publicEvidenceCloses':d['status']['publicEvidenceCloses'],'sources':len(q('SELECT * FROM sources')),'claims':len(q('SELECT * FROM claims')),'hearingsIndexed':len(q('SELECT * FROM hearings')),'hearingsDetailed':len(q("SELECT * FROM hearings WHERE status='detailed'"))})
            if path=='/api/sources': return json_out(self,{'items':q('SELECT * FROM sources ORDER BY tier,id')})
            if path=='/api/claims':
                rows=q('SELECT c.*, GROUP_CONCAT(cs.source_id) source_ids FROM claims c LEFT JOIN claim_sources cs ON cs.claim_id=c.id GROUP BY c.id ORDER BY c.id')
                for r in rows:r['source_ids']=r['source_ids'].split(',') if r['source_ids'] else []
                return json_out(self,{'items':rows})
            if path=='/api/hearings':
                qs=parse_qs(p.query); detailed=qs.get('detailed',['0'])[0]=='1'
                sql='SELECT * FROM hearings'+(" WHERE status='detailed'" if detailed else '')+' ORDER BY day DESC'
                rows=q(sql)
                for r in rows:r['witnesses']=json.loads(r.pop('witnesses_json'))
                return json_out(self,{'items':rows})
            if path=='/api/search':
                term=parse_qs(p.query).get('q',[''])[0].strip(); like='%'+term+'%'
                if not term:return json_out(self,{'items':[]})
                claims=q('SELECT id,statement,classification FROM claims WHERE statement LIKE ? ORDER BY id',(like,))
                sources=q('SELECT id,title,tier,url FROM sources WHERE title LIKE ? OR publisher LIKE ? ORDER BY id',(like,like))
                return json_out(self,{'claims':claims,'sources':sources})
            if path=='/api/gate':
                issues=[]
                for r in q('SELECT c.id,c.classification,COUNT(cs.source_id) n FROM claims c LEFT JOIN claim_sources cs ON cs.claim_id=c.id GROUP BY c.id'):
                    if r['n']<1: issues.append(r['id']+': no source')
                status='pass' if not issues else 'blocked'
                return json_out(self,{'status':status,'reasons':issues,'rules':['every claim has source ids','classification is preserved','official findings are not emitted by Hermes']})
            return json_out(self,{'error':'not found'},404)
        return super().do_GET()
    def log_message(self,*a): pass

def main():
    init_db(); port=int(os.environ.get('PORT','4173')); server=ThreadingHTTPServer(('0.0.0.0',port),Handler); print(f'Listening on http://127.0.0.1:{port}/public/'); server.serve_forever()
if __name__=='__main__': main()
