"""High-signal anomaly derivation and lifecycle reconciliation."""
from __future__ import annotations
from .schema import Habitat, Job, Signal, utcnow
import uuid

def detect(habitat: Habitat, jobs: list[Job]) -> list[Signal]:
    out=[]; now=utcnow()
    for j in jobs:
        if j.failure_streak >= 3: out.append(Signal(str(uuid.uuid4()),habitat.id,"anomaly","critical","failure_streak",f"{j.name} has failed {j.failure_streak} times in a row",j.id,now,None,{"failure_streak":j.failure_streak}))
        if not j.enabled and j.schedule: out.append(Signal(str(uuid.uuid4()),habitat.id,"anomaly","warning","disabled_but_expected",f"{j.name} is disabled but has a schedule",j.id,now,None,{"schedule":j.schedule}))
        if j.last_error and "auth" in j.last_error.lower(): out.append(Signal(str(uuid.uuid4()),habitat.id,"anomaly","critical","auth_failure",f"{j.name} reported an authentication failure",j.id,now,None,{"error":j.last_error}))
    return out

def reconcile(existing: list[Signal], desired: list[Signal]) -> list[Signal]:
    """Return desired signals plus existing signals that should be resolved."""
    active={(s.job_id,s.code):s for s in existing if s.resolved_at is None}
    desired_keys={(s.job_id,s.code) for s in desired}
    now=utcnow()
    for key,s in active.items():
        if key not in desired_keys: s.resolved_at=now
    return desired

def health_status(jobs: list[Job], signals: list[Signal]) -> str:
    active=[s for s in signals if s.resolved_at is None]
    if any(s.severity=="critical" for s in active): return "needs_attention"
    if any(s.severity=="warning" for s in active): return "degraded"
    if jobs and all(not j.enabled for j in jobs): return "disabled"
    return "healthy"
