"""Typed domain objects for Habitat."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional, Literal

HabitatStatus = Literal["healthy", "degraded", "needs_attention", "disabled"]
Severity = Literal["critical", "warning", "info"]
SignalType = Literal["anomaly", "info", "audit"]
JobStatus = Literal["ok", "failed", "skipped", "running"]
Actor = Literal["agent", "human", "system"]
ActionStatus = Literal["ok", "failed", "rejected", "approved"]

def utcnow() -> datetime: return datetime.now(timezone.utc)

@dataclass
class Habitat:
    id: str; name: str; model: str = "unknown"; created_at: datetime = field(default_factory=utcnow); updated_at: datetime = field(default_factory=utcnow); status: HabitatStatus = "healthy"

@dataclass
class Job:
    id: str; habitat_id: str; name: str; schedule: Optional[str] = None; enabled: bool = True; command: Optional[str] = None; last_run_at: Optional[datetime] = None; last_status: Optional[JobStatus] = None; failure_streak: int = 0; last_error: Optional[str] = None

@dataclass
class Signal:
    id: str; habitat_id: str; type: SignalType; severity: Severity; code: str; message: str; job_id: Optional[str] = None; detected_at: datetime = field(default_factory=utcnow); resolved_at: Optional[datetime] = None; data: dict[str, Any] = field(default_factory=dict)

@dataclass
class Action:
    id: str; habitat_id: str; timestamp: datetime; actor: Actor; action: str; status: ActionStatus; job_id: Optional[str] = None; details: dict[str, Any] = field(default_factory=dict); run_id: Optional[str] = None

def to_dict(obj: Any) -> dict[str, Any]: return _serialize(asdict(obj))
def _serialize(value: Any) -> Any:
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, dict): return {k: _serialize(v) for k,v in value.items()}
    if isinstance(value, list): return [_serialize(v) for v in value]
    return value
