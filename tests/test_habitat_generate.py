from datetime import datetime
from types import SimpleNamespace

from habitat.generate import render_dashboard, render_landing


def test_landing_page_has_real_navigation_and_no_fake_metrics():
    html = render_landing("Test Habitat")
    assert "Don't just log what an agent did" in html
    assert 'href="/dashboard"' in html
    assert "View source on GitHub" in html
    assert "10,000" not in html
    assert "99.9%" not in html


def test_dashboard_escapes_runtime_values_and_has_supervision_sections():
    habitat = SimpleNamespace(name="<Habitat>", status="healthy", model="model<&")
    jobs = [SimpleNamespace(name="job<&", enabled=True, last_status="ok", failure_streak=0, last_error=None)]
    signals = []
    actions = [SimpleNamespace(timestamp=datetime(2026, 1, 2, 3, 4), actor="agent<&", action="run", status="ok")]
    html = render_dashboard(habitat, jobs, signals, actions, habitat.name)
    assert "Jobs &amp; health" in html
    assert "&lt;Habitat&gt;" in html
    assert "job&lt;&amp;" in html
    assert "agent&lt;&amp;" in html
    assert "/dashboard" in html


def test_dashboard_renders_claim_evidence_and_proof_links_without_raw_html_injection():
    habitat = SimpleNamespace(name="Habitat", status="healthy", model="model")
    claim = SimpleNamespace(
        id="claim<&",
        habitat_id="habitat-1",
        job_id="job-1",
        claim="Agent completed <task>",
        action="deploy",
        expected_status="success",
        created_at=datetime(2026, 1, 2, 3, 4),
        verified_at=datetime(2026, 1, 2, 3, 5),
        status="verified",
        evidence={"source": "ledger", "status": "success", "action_id": "action-1"},
        run_id="run-1",
    )
    html = render_dashboard(habitat, [], [], [], claims=[claim])
    assert "Claims &amp; proof" in html
    assert "Agent completed &lt;task&gt;" in html
    assert "source: ledger · status: success · action_id: action-1" in html
    assert "/dashboard/claims/claim&lt;&amp;" in html
    assert "/v1/claims/claim&lt;&amp;/verify" in html
    assert "/v1/claims/claim&lt;&amp;/proof" in html
    assert "claim<&" not in html
