from habitat.proof_ui import render_proof_inspector


def _payload():
    return {
        "claim_id": "claim<&",
        "proof": {
            "proof_version": "1",
            "claim": {
                "id": "claim<&",
                "claim": "Completed <deploy>",
                "expected_status": "ok",
                "status": "verified",
                "job_id": "job-1",
                "run_id": "run-1",
                "evidence": {
                    "source": "ledger",
                    "status": "ok",
                    "action_id": "action-2",
                },
            },
            "ledger": {
                "integrity": "intact",
                "actions": [
                    {"id": "action-1", "status": "wrong", "timestamp": "2026-01-01T00:00:00+00:00"},
                    {"id": "action-2", "status": "ok", "timestamp": "2026-01-01T00:01:00+00:00"},
                ],
            },
            "content_sha256": "a" * 64,
        },
    }


def test_proof_inspector_correlates_action_by_evidence_id():
    html = render_proof_inspector(_payload())
    assert "Action status<b>ok</b>" in html
    assert "Action timestamp<b>2026-01-01T00:01:00+00:00</b>" in html
    assert "wrong" not in html


def test_proof_inspector_does_not_claim_unstored_assurance_or_trust():
    html = render_proof_inspector(_payload())
    assert "Structural validity" in html
    assert "Content integrity" in html
    assert "Publisher trust<b>unknown</b>" in html
    assert "External truth" in html
    assert 'state-valid' in html


def test_proof_inspector_escapes_claims_and_path_identifiers():
    html = render_proof_inspector(_payload(), "Test <Habitat>")
    assert "Completed &lt;deploy&gt;" in html
    assert "claim&lt;&amp;" in html
    assert "Test &lt;Habitat&gt;" in html
    assert "claim<&" not in html


def test_proof_inspector_does_not_turn_stored_verified_status_into_external_truth():
    payload = _payload()
    payload["proof"]["claim"]["status"] = "verified"
    html = render_proof_inspector(payload)
    assert "External truth" in html
    assert "Publisher trust<b>unknown</b>" in html
    assert "External truth</span><b class=\"state-unknown\">unknown</b>" in html
