import json, os, sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d=json.load(open(os.path.join(ROOT,'data','commission.json'),encoding='utf-8'))
source_ids={s['id'] for s in d['sources']}
classes={'FACT','MANDATE','RECORD','TESTIMONY','ALLEGATION','ANALYSIS','INFERENCE'}
errors=[]
for c in d['claims']:
    if c['classification'] not in classes: errors.append(f"{c['id']}: invalid classification")
    for sid in c.get('sourceIds',[]):
        if sid not in source_ids: errors.append(f"{c['id']}: unknown source {sid}")
if len(d.get('hearings',[]))==0: errors.append('no detailed hearing records')
if errors:
    print('\n'.join(errors)); raise SystemExit(1)
print(f"VALID: {len(d['sources'])} sources, {len(d['claims'])} claims, {len(d['hearings'])} detailed hearing records")
