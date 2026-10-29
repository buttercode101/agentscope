#!/usr/bin/env python3
"""Controlled source ingestion: fetch -> hash -> immutable local snapshot -> audit row."""
import argparse, hashlib, os, sqlite3, urllib.request
from server import init_db, db, SNAP, now

def ingest(source_id):
    init_db(); c=db(); row=c.execute('SELECT * FROM sources WHERE id=?',(source_id,)).fetchone()
    if not row: raise SystemExit(f'Unknown source: {source_id}')
    req=urllib.request.Request(row['url'],headers={'User-Agent':'Madlanga-Evidence-Room/1.0 (source-ingestion)'})
    with urllib.request.urlopen(req,timeout=30) as r: body=r.read()
    digest=hashlib.sha256(body).hexdigest(); path=os.path.join(SNAP,digest+'.bin')
    if not os.path.exists(path):
        with open(path,'wb') as f:f.write(body)
    c.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?)',(digest,source_id,now(),digest,len(body),os.path.relpath(path,os.path.dirname(SNAP)),'success'))
    c.execute('INSERT INTO audit(at,action,object_type,object_id,details) VALUES(?,?,?,?,?)',(now(),'ingest','source',source_id,json_details(digest,len(body))))
    c.commit(); print(f'{source_id}: {digest} ({len(body)} bytes) -> {path}')

def json_details(digest,n): return '{"sha256":"%s","bytes":%d}'%(digest,n)
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('source_id'); ingest(ap.parse_args().source_id)
