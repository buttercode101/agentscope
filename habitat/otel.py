"""OpenTelemetry-compatible normalization helpers.

Habitat does not replace OpenTelemetry. It consumes a deliberately small JSON
projection of OTel GenAI spans/events and turns only accountability-relevant
operations into Habitat events. This keeps the core dependency-free while
letting existing instrumented agents feed Habitat without adopting a second
tracing model.
"""
from __future__ import annotations

from typing import Any, Iterable


ACCOUNTABILITY_OPERATIONS = {
    "invoke_agent": "agent.heartbeat",
    "invoke_workflow": "job.started",
    "execute_tool": "job.completed",
}


def _attrs(item: dict[str, Any]) -> dict[str, Any]:
    attrs = item.get("attributes") or item.get("span_attributes") or {}
    if isinstance(attrs, list):
        return {
            str(x.get("key")): x.get("value", {}).get("stringValue", x.get("value"))
            for x in attrs if isinstance(x, dict) and x.get("key")
        }
    return attrs if isinstance(attrs, dict) else {}


def events_from_spans(spans: Iterable[dict[str, Any]], habitat_id: str, job_id: str | None = None) -> list[dict[str, Any]]:
    """Convert OTel-style JSON spans into Habitat event envelopes.

    The converter intentionally ignores ordinary model/debug spans. Only
    operations that can contribute to an accountability trail are projected.
    ``trace_id`` becomes the Habitat ``run_id`` so traces and proofs remain
    correlated without copying the whole trace into the ledger.
    """
    out: list[dict[str, Any]] = []
    for span in spans:
        attrs = _attrs(span)
        operation = attrs.get("gen_ai.operation.name") or span.get("name")
        event_type = ACCOUNTABILITY_OPERATIONS.get(operation)
        if not event_type:
            continue
        trace_id = span.get("trace_id") or attrs.get("trace_id")
        span_id = span.get("span_id") or attrs.get("span_id")
        if event_type == "agent.heartbeat":
            out.append({"id": f"otel-{span_id or trace_id}", "type": event_type, "habitat_id": habitat_id, "agent_id": attrs.get("gen_ai.agent.id"), "run_id": trace_id})
            continue
        if not job_id:
            continue
        out.append({
            "id": f"otel-{span_id or trace_id}",
            "type": event_type,
            "habitat_id": habitat_id,
            "job_id": job_id,
            "run_id": trace_id,
            "correlation_id": trace_id,
            "action": attrs.get("gen_ai.operation.name") or operation,
            "model": attrs.get("gen_ai.request.model") or attrs.get("gen_ai.response.model"),
            "status": span.get("status", {}).get("code") if isinstance(span.get("status"), dict) else span.get("status"),
        })
    return out


def accountability_attributes(event: dict[str, Any]) -> dict[str, Any]:
    """Return stable OTel-style attributes for a Habitat event."""
    return {
        "habitat.event.type": event.get("type"),
        "habitat.habitat_id": event.get("habitat_id"),
        "habitat.job_id": event.get("job_id"),
        "habitat.run_id": event.get("run_id") or event.get("correlation_id"),
    }
