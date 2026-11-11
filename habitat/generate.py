"""Render Habitat's public landing page and native supervision surface."""
from __future__ import annotations

from html import escape
from pathlib import Path

from .claims import Claim
from .schema import Action, Habitat, Job, Signal


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#090a0c">
<meta name="description" content="Habitat — local-first supervision and portable evidence for autonomous agents.">
<title>{escape(title)}</title>
<style>
:root {{ --bg:#090a0c;--surface:#101216;--text:#f4f5f7;--muted:#9298a4;--line:#272b33;--accent:#d8ff63;--danger:#ff6b6b;--warn:#f5c451;--ok:#67e8a5; }}
* {{ box-sizing:border-box }} html {{ scroll-behavior:smooth }}
body {{ margin:0;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.55 }}
a {{ color:inherit;text-decoration:none }} .container {{ width:min(1120px,calc(100% - 40px));margin:0 auto }}
.nav {{ min-height:72px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line) }}
.brand {{ display:flex;align-items:center;gap:10px;font-weight:760;letter-spacing:-.02em }}
.mark {{ width:25px;height:25px;border:1px solid #59606b;border-radius:7px;position:relative }} .mark:after {{ content:"";position:absolute;width:9px;height:9px;border-radius:50%;background:var(--accent);left:7px;top:7px;box-shadow:0 0 18px #d8ff6388 }}
.navlinks {{ display:flex;gap:24px;align-items:center;color:var(--muted);font-size:14px }} .navlinks a:hover {{ color:var(--text) }}
.button {{ display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:0 16px;border:1px solid var(--line);border-radius:9px;background:#f4f5f7;color:#090a0c;font-weight:700;font-size:14px }} .button.secondary {{ background:transparent;color:var(--text) }}
.hero {{ padding:96px 0 80px;max-width:900px }} .eyebrow {{ color:var(--accent);font-size:12px;font-weight:750;letter-spacing:.13em;text-transform:uppercase;margin-bottom:20px }}
h1 {{ font-size:clamp(48px,7vw,82px);line-height:.98;letter-spacing:-.065em;margin:0 0 26px;max-width:850px }} .hero p {{ color:var(--muted);font-size:clamp(18px,2vw,21px);max-width:720px;margin:0 0 30px }} .actions {{ display:flex;flex-wrap:wrap;gap:10px }}
.proof {{ margin:0 0 90px;border:1px solid var(--line);background:linear-gradient(135deg,#12151a,#0d0f13);border-radius:16px;overflow:hidden;box-shadow:0 25px 80px #0006 }} .proofbar {{ padding:13px 16px;border-bottom:1px solid var(--line);color:var(--muted);font-size:12px;display:flex;gap:8px;align-items:center }} .dot {{ width:7px;height:7px;border-radius:50%;background:#4d535d }}
.flow {{ padding:32px;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;align-items:stretch }} .node {{ min-height:92px;border:1px solid var(--line);background:var(--surface);border-radius:10px;padding:16px;display:flex;flex-direction:column;justify-content:center;position:relative }} .node b {{ font-size:14px }} .node span {{ color:var(--muted);font-size:12px;margin-top:4px }} .node:not(:last-child)::after {{ content:"→";position:absolute;right:-20px;top:50%;transform:translateY(-50%);color:#565d68;font-size:20px;z-index:2 }}
.section {{ padding:80px 0;border-top:1px solid var(--line) }} .section h2 {{ margin:0 0 12px;font-size:clamp(30px,4vw,48px);letter-spacing:-.045em }} .section-intro {{ color:var(--muted);max-width:650px;font-size:17px;margin:0 0 38px }} .cards {{ display:grid;grid-template-columns:repeat(3,1fr);gap:12px }}
.card {{ border:1px solid var(--line);background:var(--surface);border-radius:12px;padding:24px }} .card .num {{ color:var(--accent);font-size:12px;font-weight:800 }} .card h3 {{ margin:28px 0 8px;font-size:18px }} .card p {{ color:var(--muted);font-size:14px;margin:0 }} .note {{ border-left:2px solid var(--accent);padding:2px 0 2px 18px;color:var(--muted);max-width:760px }}
footer {{ border-top:1px solid var(--line);padding:28px 0 44px;color:var(--muted);font-size:13px;display:flex;justify-content:space-between;gap:20px }}
.dashboard {{ padding:36px 0 64px }} .dashhead {{ display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin-bottom:24px }} .dashhead h1 {{ font-size:30px;letter-spacing:-.04em;margin:0 0 4px }} .dashsub {{ color:var(--muted);font-size:13px }}
.kpis {{ display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px }} .kpi,.panel {{ border:1px solid var(--line);background:var(--surface);border-radius:12px }} .kpi {{ padding:18px }} .kpi .value {{ font-size:30px;font-weight:720;letter-spacing:-.04em }} .kpi .value small {{ color:var(--muted);font-size:14px;font-weight:500 }} .kpi .label {{ color:var(--muted);font-size:12px;margin-top:3px }}
.panel {{ padding:20px;margin-bottom:12px }} .panel h2 {{ font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin:0 0 14px }} .panel.attention {{ border-color:#54302f }} .panel.calm {{ border-color:#244735 }}
.signal {{ display:flex;gap:10px;align-items:baseline;padding:9px 0;border-bottom:1px solid var(--line) }} .signal:last-child {{ border:0 }} .badge {{ font-size:10px;font-weight:800;border-radius:5px;padding:3px 6px }} .badge.critical {{ background:var(--danger);color:#190708 }} .badge.warning {{ background:var(--warn);color:#191405 }} .ok {{ color:var(--ok) }}
.claim-grid {{ display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px }} .claim {{ border:1px solid var(--line);background:#0d0f13;border-radius:10px;padding:16px }} .claim-top {{ display:flex;justify-content:space-between;gap:12px;align-items:flex-start }} .claim-id {{ color:var(--muted);font:11px ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere }} .claim-text {{ margin:10px 0 14px;font-size:15px }} .claim-meta {{ display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;color:var(--muted);font-size:12px }} .claim-meta strong {{ display:block;color:var(--text);font-size:12px;margin-top:2px;overflow-wrap:anywhere }} .claim-actions {{ display:flex;flex-wrap:wrap;gap:8px;margin-top:14px }} .mini {{ min-height:34px;padding:0 11px;font-size:12px }} .status-verified {{ color:var(--ok) }} .status-rejected {{ color:var(--danger) }} .status-pending {{ color:var(--warn) }}
table {{ width:100%;border-collapse:collapse;font-size:13px }} th,td {{ padding:10px 8px;text-align:left;border-bottom:1px solid var(--line) }} th {{ color:var(--muted);font-size:11px;font-weight:550 }} tr:last-child td {{ border-bottom:0 }}
@media(max-width:900px) {{ .kpis {{ grid-template-columns:repeat(2,1fr) }} .cards {{ grid-template-columns:repeat(2,1fr) }} .flow {{ grid-template-columns:1fr 1fr }} .node:not(:last-child)::after {{ right:-20px }} }}
@media(max-width:760px) {{ .container {{ width:min(100% - 28px,1120px) }} .navlinks a:not(.button) {{ display:none }} .hero {{ padding:68px 0 58px }} .flow {{ grid-template-columns:1fr;padding:20px }} .node:not(:last-child)::after {{ right:auto;left:50%;top:auto;bottom:-24px;transform:translateX(-50%) rotate(90deg) }} .cards,.claim-grid {{ grid-template-columns:1fr 1fr }} .dashhead {{ align-items:flex-start;flex-direction:column }} .panel {{ overflow:auto }} table {{ min-width:650px }} }}
@media(max-width:460px) {{ h1 {{ font-size:46px }} .cards,.kpis,.claim-grid {{ grid-template-columns:1fr }} footer {{ flex-direction:column }} .button {{ width:100% }} .actions .button {{ width:100% }} }}
</style></head><body>{body}</body></html>"""


def render_landing(title: str = "Habitat") -> str:
    body = f"""<header class="container nav"><a class="brand" href="/"><span class="mark"></span>Habitat</a>
<nav class="navlinks"><a href="#why">Why</a><a href="#how">How it works</a><a href="/dashboard" class="button">Open dashboard</a></nav></header>
<main><section class="container hero"><div class="eyebrow">Local-first accountability for agents</div>
<h1>Don't just log what an agent did. Check the evidence.</h1>
<p>Habitat is a small supervision and evidence runtime for autonomous agents. It turns authenticated events into a verifiable local record, checks claims against that record, and produces portable proof another machine can inspect.</p>
<div class="actions"><a class="button" href="/dashboard">Open supervision dashboard</a><a class="button secondary" href="https://github.com/buttercode101/Habitat">View source on GitHub</a></div></section>
<section class="container proof" id="how"><div class="proofbar"><span class="dot"></span><span>evidence path</span><span>·</span><span>deterministic, local, inspectable</span></div>
<div class="flow"><div class="node"><b>Agent</b><span>existing framework</span></div><div class="node"><b>Event</b><span>authenticated input</span></div><div class="node"><b>Ledger</b><span>tamper-evident record</span></div><div class="node"><b>Verify</b><span>claim + evidence</span></div><div class="node"><b>Proof</b><span>portable artifact</span></div></div></section>
<section class="section" id="why"><div class="container"><h2>A layer for accountability, not another observability suite.</h2>
<p class="section-intro">Keep your agent framework and existing telemetry. Habitat focuses on the narrower question that matters when an agent makes a claim: what evidence does the system actually have?</p>
<div class="cards"><article class="card"><div class="num">01 / RECORD</div><h3>Capture trusted actions</h3><p>Accept structured, authenticated events and correlate work with run IDs instead of inventing another tracing system.</p></article>
<article class="card"><div class="num">02 / VERIFY</div><h3>Test claims against evidence</h3><p>Check exact action/run relationships and explicit external evidence without treating a valid record as proof of real-world truth.</p></article>
<article class="card"><div class="num">03 / EXCHANGE</div><h3>Export portable proof</h3><p>Produce a proof artifact that can be verified away from the producer database, including in CI.</p></article></div></div></section>
<section class="section"><div class="container"><p class="note">Habitat is deliberately small. It does not replace tracing, evaluation, orchestration, or human judgment. It gives those systems an accountability surface they can inspect.</p></div></section></main>
<footer class="container"><span>{escape(title)} · MIT licensed</span><span>local evidence → verification → proof</span></footer>"""
    return _page(f"{title} — Agent accountability", body)


def _claim_evidence(claim: Claim) -> str:
    evidence = claim.evidence if isinstance(claim.evidence, dict) else {}
    if not evidence:
        return "No recorded evidence"
    parts = []
    for key in ("source", "status", "action_id", "run_id", "adapter"):
        value = evidence.get(key)
        if value not in (None, ""):
            parts.append(f"{escape(str(key))}: {escape(str(value))}")
    return " · ".join(parts) if parts else "Recorded evidence"


def render_dashboard(habitat: Habitat, jobs: list[Job], signals: list[Signal], actions: list[Action], title: str = "Habitat", claims: list[Claim] | None = None) -> str:
    claims = claims or []
    unresolved = [s for s in signals if s.resolved_at is None and s.severity in ("critical", "warning")]
    unresolved.sort(key=lambda s: (0 if s.severity == "critical" else 1, s.detected_at))
    enabled = sum(j.enabled for j in jobs)
    ok = sum(j.last_status == "ok" for j in jobs)
    failed = sum(j.last_status == "failed" for j in jobs)
    attention = "".join(f'<div class="signal"><span class="badge {escape(s.severity)}">{escape(s.severity.upper())}</span><span><strong>{escape(s.code)}</strong> — {escape(s.message)}</span></div>' for s in unresolved) or '<div class="ok">All clear. Nothing needs attention.</div>'
    rows = "".join(f'<tr><td>{escape(j.name)}</td><td>{"enabled" if j.enabled else "disabled"}</td><td>{escape(j.last_status or "—")}</td><td>{j.failure_streak}</td><td>{escape(j.last_error or "—")}</td></tr>' for j in jobs) or '<tr><td colspan="5">No jobs configured.</td></tr>'
    acts = "".join(f'<tr><td>{escape(a.timestamp.strftime("%Y-%m-%d %H:%M"))}</td><td>{escape(a.actor)}</td><td>{escape(a.action)}</td><td>{escape(a.status)}</td></tr>' for a in actions[:20]) or '<tr><td colspan="4">No recent actions.</td></tr>'
    claim_cards = "".join(
        f'<article class="claim"><div class="claim-top"><span class="claim-id">{escape(c.id)}</span><strong class="status-{escape(c.status)}">{escape(c.status.upper())}</strong></div>'
        f'<div class="claim-text">{escape(c.claim)}</div><div class="claim-meta">'
        f'<div>Expected<strong>{escape(c.expected_status)}</strong></div>'
        f'<div>Evidence<strong>{_claim_evidence(c)}</strong></div>'
        f'<div>Run<strong>{escape(c.run_id or "—")}</strong></div>'
        f'<div>Job<strong>{escape(c.job_id or "—")}</strong></div></div>'
        f'<div class="claim-actions"><a class="button secondary mini" href="/dashboard/claims/{escape(c.id)}">Inspect claim</a>'
        f'<a class="button secondary mini" href="/v1/claims/{escape(c.id)}/verify" target="_blank" rel="noreferrer">Verify now</a>'
        f'<a class="button secondary mini" href="/v1/claims/{escape(c.id)}/proof" target="_blank" rel="noreferrer">Proof JSON</a></div></article>'
        for c in claims[:20]
    ) or '<div class="ok">No claims recorded yet.</div>'
    panel_class = "attention" if unresolved else "calm"
    body = f"""<header class="container nav"><a class="brand" href="/"><span class="mark"></span>Habitat</a><nav class="navlinks"><a href="/">Overview</a><a href="/dashboard" class="button">Supervision</a></nav></header>
<main class="container dashboard"><div class="dashhead"><div><h1>{escape(title)}</h1><div class="dashsub">{escape(habitat.status)} · {escape(habitat.model)} · local supervision</div></div><a class="button secondary" href="/">What is Habitat?</a></div>
<div class="kpis"><div class="kpi"><div class="value">{enabled}<small>/{len(jobs)}</small></div><div class="label">Jobs enabled</div></div><div class="kpi"><div class="value">{ok}</div><div class="label">Successful runs</div></div><div class="kpi"><div class="value">{failed}</div><div class="label">Failed runs</div></div><div class="kpi"><div class="value">{len(unresolved)}</div><div class="label">Needs attention</div></div></div>
<section class="panel {panel_class}"><h2>Needs attention</h2>{attention}</section>
<section class="panel"><h2>Claims &amp; proof</h2><div class="claim-grid">{claim_cards}</div></section>
<section class="panel"><h2>Jobs &amp; health</h2><table><thead><tr><th>Name</th><th>State</th><th>Last status</th><th>Failure streak</th><th>Last error</th></tr></thead><tbody>{rows}</tbody></table></section>
<section class="panel"><h2>Recent actions</h2><table><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Status</th></tr></thead><tbody>{acts}</tbody></table></section></main>"""
    return _page(f"{title} — Supervision", body)


def write_dashboard(html: str, path: str | Path) -> Path:
    p = Path(path)
    p.write_text(html, encoding="utf-8")
    return p
