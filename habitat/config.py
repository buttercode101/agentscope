"""Dependency-free configuration loader and validator."""
from __future__ import annotations
import json
from pathlib import Path

def _scalar(value):
    value=value.strip()
    if not value:return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):return value[1:-1]
    if value.lower() in {'true','false'}:return value.lower()=='true'
    if value.lower() in {'null','none'}:return None
    return value

def load_yaml(path):
    lines=Path(path).read_text(encoding='utf-8').splitlines(); result={}; jobs=[]; in_jobs=False; current=None
    for raw in lines:
        line=raw.split('#',1)[0].rstrip(); stripped=line.strip()
        if not stripped:continue
        if stripped=='jobs:':in_jobs=True;result['jobs']=jobs;continue
        if in_jobs and stripped.startswith('- '):
            current={};jobs.append(current); item=stripped[2:].strip()
            if item:key,value=item.split(':',1);current[key.strip()]=_scalar(value)
            continue
        if in_jobs and line.startswith('  ') and current is not None and ':' in stripped:
            key,value=stripped.split(':',1);current[key.strip()]=_scalar(value);continue
        in_jobs=False
        if ':' in stripped:key,value=stripped.split(':',1);result[key.strip()]=_scalar(value)
    return result

def load_config(path):
    p=Path(path)
    if p.suffix.lower()=='.json':return json.loads(p.read_text(encoding='utf-8'))
    if p.suffix.lower() in {'.yaml','.yml'}:return load_yaml(p)
    raise ValueError('Config must be .yaml, .yml, or .json')

def validate_config(cfg):
    if not isinstance(cfg,dict):raise ValueError('configuration must be an object')
    if not isinstance(cfg.get('id'),str) or not cfg['id'].strip():raise ValueError('id must be a non-empty string')
    if not isinstance(cfg.get('name'),str) or not cfg['name'].strip():raise ValueError('name must be a non-empty string')
    jobs=cfg.get('jobs',[])
    if not isinstance(jobs,list):raise ValueError('jobs must be a list')
    seen=set()
    for i,j in enumerate(jobs):
        if not isinstance(j,dict):raise ValueError(f'jobs[{i}] must be an object')
        for key in ('id','name'):
            if not isinstance(j.get(key),str) or not j[key].strip():raise ValueError(f'jobs[{i}].{key} must be a non-empty string')
        if j['id'] in seen:raise ValueError(f'duplicate job id: {j["id"]}')
        seen.add(j['id'])
        if 'enabled' in j and not isinstance(j['enabled'],bool):raise ValueError(f'jobs[{i}].enabled must be boolean')
        if j.get('command') is not None and not isinstance(j['command'],str):raise ValueError(f'jobs[{i}].command must be string')
    return cfg
