from habitat.otel import accountability_attributes, events_from_spans


def test_otel_trace_becomes_habitat_run_id():
    spans = [{
        "trace_id": "trace-1",
        "span_id": "span-1",
        "name": "execute_tool",
        "attributes": {"gen_ai.operation.name": "execute_tool"},
        "status": {"code": "OK"},
    }]
    events = events_from_spans(spans, "h1", "job1")
    assert len(events) == 1
    assert events[0]["run_id"] == "trace-1"
    assert events[0]["job_id"] == "job1"


def test_non_accountability_span_is_ignored():
    spans = [{"trace_id": "trace-1", "span_id": "span-1", "name": "chat"}]
    assert events_from_spans(spans, "h1", "job1") == []


def test_accountability_attributes_are_stable():
    attrs = accountability_attributes({
        "type": "job.completed",
        "habitat_id": "h1",
        "job_id": "job1",
        "run_id": "trace-1",
    })
    assert attrs == {
        "habitat.event.type": "job.completed",
        "habitat.habitat_id": "h1",
        "habitat.job_id": "job1",
        "habitat.run_id": "trace-1",
    }
