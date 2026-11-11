"""Tiny example: project existing OTel-style JSON spans into Habitat events."""
import json
from habitat.otel import events_from_spans

spans = [
    {
        "trace_id": "trace-123",
        "span_id": "span-456",
        "name": "execute_tool",
        "attributes": {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.request.model": "example-model",
        },
        "status": {"code": "OK"},
    }
]

for event in events_from_spans(spans, habitat_id="local", job_id="deploy"):
    print(json.dumps(event, sort_keys=True))
