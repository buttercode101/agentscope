"""Native proof inspection page for Habitat's supervision UI."""
from __future__ import annotations

from html import escape
from typing import Any


def _value(value: Any) -> str:
    if value is None:
        return "—"
    return escape(str(value))


def _assurance(proof: dict[str, Any], evidence: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Derive only assurance levels actually established by the proof schema."""
    claim = proof.get("claim") or {}
    ledger = proof.get("ledger") or {}
    signature = proof.get("signature")
    verdict = claim.get("status")
    ledger_integrity = ledger.get("integrity")
    evidence_status = evidence.get("status")

    structural = "valid" if proof.get("proof_version") == "1" and claim and ledger else "unknown"
    content = "valid" if isinstance(proof.get("content_sha256"), str) and len(proof["content_sha256"]) == 64 else "unknown"
    consistent = "valid" if verdict in {"pending", "verified", "rejected", "inconclusive"} and evidence_status is not None else "unknown"
    if verdict == "verified" and not evidence:
        consistent = "invalid"
    signature_state = "present" if signature else "not present"
    publisher = "unknown"
    external = "unknown"
    return (
        ("Structural validity", structural),
        ("Content integrity", content),
        ("Internal consistency", consistent),
        ("Signature", signature_state),
        ("Publisher trust", publisher),
        ("External truth", external),
    )


def render_proof_inspector(payload: dict[str, Any], title: str = "Habitat") -> str:
    proof = payload.get("proof") or {}
    claim = proof.get("claim") or {}
    ledger = proof.get("ledger") or {}
    signature = proof.get("signature") or {}
    evidence = claim.get("evidence") or {}
    if not isinstance(evidence, dict):
        evidence = {}

    levels = _assurance(proof, evidence)
    checks = "".join(
        f'<div class="check"><span>{escape(label)}</span><b class="state-{escape(str(value).replace(" ", "-"))}">{escape(str(value).replace("_", " "))}</b></div>'
        for label, value in levels
    )

    actions = proof.get("ledger", {}).get("actions") or []
    if not isinstance(actions, list):
        actions = []
    evidence_action_id = evidence.get("action_id")
    action = next(
        (candidate for candidate in actions if isinstance(candidate, dict) and candidate.get("id") == evidence_action_id),
        {},
    )
    signature_text = "present" if signature else "not present"
    digest = proof.get("content_sha256")
    claim_id = str(payload.get("claim_id", ""))
    safe_claim_id = escape(claim_id)
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} — Proof {safe_claim_id}</title>
<style>
:root{{--bg:#090a0c;--surface:#101216;--line:#272b33;--text:#f4f5f7;--muted:#9298a4;--ok:#67e8a5;--warn:#f5c451;--bad:#ff6b6b;--accent:#d8ff63}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 Inter,system-ui,sans-serif}}a{{color:inherit;text-decoration:none}}.wrap{{width:min(1080px,calc(100% - 32px));margin:auto}}header{{min-height:72px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between}}.brand{{font-weight:800}}.back{{color:var(--muted)}}main{{padding:42px 0 72px}}h1{{font-size:clamp(32px,5vw,54px);letter-spacing:-.055em;line-height:1.02;margin:0 0 8px}}.sub{{color:var(--muted);margin-bottom:28px}}.grid{{display:grid;grid-template-columns:1.25fr .75fr;gap:12px}}.panel{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:20px;margin-bottom:12px}}h2{{font-size:12px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:0 0 16px}}.claim{{font-size:20px;line-height:1.35;margin-bottom:18px}}.meta{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}.meta div{{border-top:1px solid var(--line);padding-top:8px;color:var(--muted);font-size:12px}}.meta b{{display:block;color:var(--text);font-size:13px;overflow-wrap:anywhere}}.check{{display:flex;justify-content:space-between;gap:15px;padding:10px 0;border-bottom:1px solid var(--line)}}.check:last-child{{border:0}}.state-valid,.state-present{{color:var(--ok)}}.state-unknown,.state-not-present{{color:var(--warn)}}.state-invalid{{color:var(--bad)}}code{{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere}}.note{{border-left:2px solid var(--accent);padding-left:14px;color:var(--muted)}}.actions{{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}}.button{{display:inline-flex;padding:9px 12px;border:1px solid var(--line);border-radius:8px;background:#f4f5f7;color:#090a0c;font-weight:700;font-size:12px}}.button.alt{{background:transparent;color:var(--text)}}@media(max-width:760px){{.wrap{{width:min(100% - 24px,1080px)}}.grid{{grid-template-columns:1fr}}.meta{{grid-template-columns:1fr}}.actions .button{{width:100%;justify-content:center}}}}
</style></head><body><header class="wrap"><a class="brand" href="/">Habitat</a><a class="back" href="/dashboard">← Dashboard</a></header>
<main class="wrap"><div class="sub">Proof inspection · claim {safe_claim_id}</div><h1>{_value(claim.get('status')).upper()} claim</h1><div class="grid"><section><div class="panel"><h2>Claim</h2><div class="claim">{_value(claim.get('claim'))}</div><div class="meta"><div>Expected status<b>{_value(claim.get('expected_status'))}</b></div><div>Evidence source<b>{_value(evidence.get('source'))}</b></div><div>Action ID<b>{_value(evidence.get('action_id'))}</b></div><div>Run / job<b>{_value(claim.get('run_id'))} / {_value(claim.get('job_id'))}</b></div></div></div>
<div class="panel"><h2>Ledger evidence</h2><div class="meta"><div>Integrity<b>{_value(ledger.get('integrity'))}</b></div><div>Action status<b>{_value(action.get('status'))}</b></div><div>Action ID<b>{_value(action.get('id'))}</b></div><div>Action timestamp<b>{_value(action.get('timestamp'))}</b></div></div></div>
<div class="panel"><h2>Proof digest</h2><code>{_value(digest)}</code><div class="actions"><a class="button" href="/v1/claims/{safe_claim_id}/verify" target="_blank" rel="noreferrer">Verify claim</a><a class="button alt" href="/v1/claims/{safe_claim_id}/proof" target="_blank" rel="noreferrer">View proof JSON</a></div></div></section>
<aside><div class="panel"><h2>Assurance</h2>{checks}</div><div class="panel"><h2>Cryptographic status</h2><div class="meta"><div>Signature<b>{signature_text}</b></div><div>Publisher trust<b>unknown</b></div></div></div><div class="panel"><p class="note">A valid proof establishes integrity and consistency within Habitat's evidence boundary. It does not by itself establish that the publisher is trusted or that the underlying real-world event is true.</p></div></aside></div></main></body></html>"""
    return body
