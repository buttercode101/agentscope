"""Job execution, scheduling and trusted truth recording."""
from __future__ import annotations
import time,uuid,re
from .schema import Job,Action,utcnow
from .store import Store
from .signals import detect,reconcile,health_status
from .adapters import JobAdapter,ShellAdapter

def _interval_seconds(schedule):
    if not schedule:return None
    m=re.fullmatch(r"every\s+(\d+)\s*(s|sec|secs|m|min|mins|h|hr|hrs)",schedule.strip().lower())
    if not m:return None
    n=int(m.group(1)); return n*({"s":1,"sec":1,"secs":1,"m":60,"min":60,"mins":60,"h":3600,"hr":3600,"hrs":3600}[m.group(2)])

def due(j:Job,now=None):
    if not j.enabled:return False
    interval=_interval_seconds(j.schedule)
    if interval is None:return j.last_run_at is None
    return j.last_run_at is None or (now or utcnow())-j.last_run_at >= __import__('datetime').timedelta(seconds=interval)

def run_once(store:Store,adapter:JobAdapter|None=None,jobs_filter=None):
    adapter=adapter or ShellAdapter();habitat=store.habitat();run_id=str(uuid.uuid4());selected=[j for j in store.jobs() if (jobs_filter is None or j.id in jobs_filter)]
    for j in selected:
        if not j.enabled:
            j.last_status="skipped";store.save_job(j);store.save_action(Action(str(uuid.uuid4()),habitat.id,utcnow(),"system","skip_job","ok",j.id,{"reason":"disabled"},run_id));continue
        j.last_run_at=utcnow()
        if not j.command:
            j.last_status="failed";j.failure_streak+=1;j.last_error="No command configured";store.save_action(Action(str(uuid.uuid4()),habitat.id,utcnow(),"system","run_job","failed",j.id,{"error":j.last_error},run_id));store.save_job(j);continue
        r=adapter.execute(j.command)
        if r.ok:j.last_status="ok";j.failure_streak=0;j.last_error=None;store.save_action(Action(str(uuid.uuid4()),habitat.id,utcnow(),"agent","run_job","ok",j.id,{"stdout":r.stdout},run_id))
        else:j.last_status="failed";j.failure_streak+=1;j.last_error=(r.stderr or r.stdout or f"exit {r.exit_code}").strip()[-2000:];store.save_action(Action(str(uuid.uuid4()),habitat.id,utcnow(),"agent","run_job","failed",j.id,{"error":j.last_error,"exit_code":r.exit_code},run_id))
        store.save_job(j)
    jobs=store.jobs(); existing=store.signals();desired=detect(habitat,jobs);keys={(s.job_id,s.code) for s in existing if s.resolved_at is None}
    for signal in desired:
        if (signal.job_id,signal.code) not in keys:store.save_signal(signal)
    reconcile(existing,desired)
    for s in existing:
        if s.resolved_at:store.save_signal(s)
    habitat.status=health_status(jobs,store.signals());habitat.updated_at=utcnow();store.save_habitat(habitat);return jobs

def run_loop(store,adapter=None,interval=10,stop_after=None):
    started=time.monotonic()
    while True:
        now=utcnow();due_ids=[j.id for j in store.jobs() if due(j,now)]
        if due_ids:run_once(store,adapter,due_ids)
        if stop_after is not None and time.monotonic()-started>=stop_after:break
        time.sleep(max(0.1,interval))
