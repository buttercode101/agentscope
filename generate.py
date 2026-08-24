#!/usr/bin/env python3
"""agentscope — scan-first supervision dashboard for AI agent crews.

Reads local agent state (cron jobs, execution logs, sessions) and renders a
self-contained static HTML file answering one question: "is anything off?"

Supervision layer, not control plane: zero operation buttons.
Data never leaves the machine.

Usage:
  python3 generate.py [--config config.example.json] [-o dashboard.html]

Config (optional): see config.example.json. Without a config, auto-detects
Hermes Agent layout under ~/.hermes/.
"""
import argparse, json, sqlite3, os, glob, html
from datetime import datetime, timedelta

# ---------------------------------------------------------------- config ----

DEFAULT_CONFIG = {
    "title": "Agent Command",
    "footer": "generated locally · no data leaves this device",
    "theme": "dark",                     # "dark" | "light"
    "sources": {
        "cron_jobs_glob": "~/.hermes/cron/jobs*",
        "executions_db": "~/.hermes/cron/executions.db",
        "sessions_dir": "~/.hermes/sessions",
        "leads_db": None,
        "leads_query": None,
        "leads_label": "Active items",
    },
    "session_days": 7,
    "max_actions": 15,
}

def load_config(path):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path and os.path.exists(path):
        user = json.load(open(path))
        for k, v in user.items():
            if k == "sources" and isinstance(v, dict):
                cfg["sources"].update(v)
            else:
                cfg[k] = v
    s = cfg["sources"]
    for k in ("cron_jobs_glob", "executions_db", "sessions_dir", "leads_db"):
        if s.get(k):
            s[k] = os.path.expanduser(s[k])
    return cfg

# ------------------------------------------------------------ collectors ----

def load_cron_jobs(pattern):
    jobs = []
    for path in glob.glob(pattern):
        try:
            data = json.load(open(path))
            items = data if isinstance(data, list) else data.get("jobs", list(data.values()) if isinstance(data, dict) else [])
            for j in items:
                if not isinstance(j, dict):
                    continue
                sched = j.get("schedule", {})
                sched_s = sched.get("display", "") if isinstance(sched, dict) else str(sched)
                jobs.append({"name": j.get("name", "?"), "schedule": sched_s,
                             "enabled": bool(j.get("enabled", True))})
        except Exception:
            pass
    seen, out = set(), []
    for j in jobs:
        if j["name"] not in seen:
            seen.add(j["name"]); out.append(j)
    return sorted(out, key=lambda x: (not x["enabled"], x["name"].lower()))

def recent_executions(db_path, limit=40):
    rows = []
    try:
        c = sqlite3.connect(db_path)
        cols = [x[1] for x in c.execute("PRAGMA table_info(executions)")]
        sel = ", ".join(x for x in ["job_id","status","started_at","finished_at","error"] if x in cols)
        rows = [dict(zip(["job_id","status","started_at","finished_at","error"], r))
                for r in c.execute(f"SELECT {sel} FROM executions ORDER BY rowid DESC LIMIT ?", (limit,))]
    except Exception:
        pass
    return rows

def job_names(jobs_pattern, exec_db):
    names = {}
    try:
        c = sqlite3.connect(exec_db)
        for jid, in c.execute("SELECT DISTINCT job_id FROM executions"):
            names[jid] = jid[:8]
    except Exception:
        pass
    for path in glob.glob(jobs_pattern):
        try:
            data = json.load(open(path))
            items = data if isinstance(data, list) else data.get("jobs", list(data.values()) if isinstance(data, dict) else [])
            for j in items:
                if isinstance(j, dict) and j.get("id"):
                    names[j["id"]] = j.get("name", j["id"][:8])
        except Exception:
            pass
    return names

def counter_summary(db_path, total_q, active_q):
    if not db_path or not total_q:
        return None
    try:
        c = sqlite3.connect(db_path)
        n, = c.execute(total_q).fetchone()
        a, = c.execute(active_q).fetchone() if active_q else (n,)
        return {"total": n, "active": a}
    except Exception:
        return None

def session_activity(sessions_dir, days=7):
    counts = {}
    now = datetime.now()
    try:
        for f in os.listdir(sessions_dir):
            p = os.path.join(sessions_dir, f)
            age_days = (now - datetime.fromtimestamp(os.path.getmtime(p))).days
            if age_days < days:
                day = (now - timedelta(days=age_days)).strftime("%a %d")
                counts[day] = counts.get(day, 0) + 1
    except Exception:
        pass
    return counts

def anomalies(jobs, execs):
    """Core panel: ONLY things needing attention. Quiet when healthy."""
    a = []
    disabled = [j for j in jobs if not j["enabled"]]
    if disabled:
        a.append(("warn", f"{len(disabled)} scheduled job(s) disabled: " + ", ".join(j["name"] for j in disabled)))
    fails = {}
    for e in execs[-20:]:
        if e.get("status") == "failed":
            fails.setdefault(e.get("job_id"), 0)
            fails[e.get("job_id")] += 1
    drift, other = [], {}
    for jid in fails:
        err_text = next((e.get("error","") for e in reversed(execs) if e.get("job_id")==jid and e.get("error")), "")
        low = err_text.lower()
        label = jid[:8]
        if "drift" in low or ("config" in low and "skip" in low):
            drift.append(label)
        elif any(sig in low for sig in ("auth", "api key", "unauthorized", "403", "401")):
            other[f"auth:{label}"] = "auth failure — check credentials"
        else:
            other[label] = f"failed {fails[jid]}x recently"
    for jn in drift:
        a.append(("fail", f"'{jn}' skipping runs — inference/config drift detected. Re-pin its config to restore."))
    for jn, msg in other.items():
        a.append(("fail", f"'{jn}': {msg}"))
    if not a:
        a.append(("ok", "All clear — nothing off."))
    return a

# ---------------------------------------------------------------- render ----

BADGE = {"warn": ("WARN", "#b45309", "#fef3c7"),
         "fail": ("FAIL", "#b91c1c", "#fee2e2"),
         "ok":   ("OK",   "#15803d", "#dcfce7")}

BADGE_LIGHT = {"warn": ("WARN", "#92400e", "#fef3c7"),
               "fail": ("FAIL", "#991b1b", "#fee2e2"),
               "ok":   ("OK",   "#166534", "#dcfce7")}

def esc(s): return html.escape(str(s))

def build(cfg, out_path):
    now = datetime.now().strftime("%a %d %b %Y · %H:%M")
    s = cfg["sources"]
    light = cfg.get("theme", "dark") == "light"
    badge = BADGE_LIGHT if light else BADGE
    jobs = load_cron_jobs(s["cron_jobs_glob"]) if s.get("cron_jobs_glob") else []
    execs = recent_executions(s["executions_db"]) if s.get("executions_db") else []
    leads = counter_summary(s.get("leads_db"), *(s.get("leads_query") or (None, None))) or {"total": 0, "active": 0}
    sess = session_activity(s.get("sessions_dir"), cfg["session_days"]) if s.get("sessions_dir") else {}
    anom = anomalies(jobs, execs)

    enabled_n = sum(1 for j in jobs if j["enabled"])
    day_ago = (datetime.now()-timedelta(days=1)).strftime("%Y-%m-%dT")
    last24_fail = sum(1 for e in execs if e.get("status")=="failed" and (e.get("started_at") or "") >= day_ago)
    last24_ok = sum(1 for e in execs if e.get("status") in ("succeeded","success","ok") and (e.get("started_at") or "") >= day_ago)
    names = job_names(s["cron_jobs_glob"], s["executions_db"]) if s.get("executions_db") else {}

    job_rows = "".join(
        f'<tr><td>{esc(j["name"])}</td><td class="mut">{esc(j["schedule"])}</td>'
        f'<td><span class="pill {"on" if j["enabled"] else "off"}">{"ON" if j["enabled"] else "OFF"}</span></td></tr>'
        for j in jobs) or '<tr><td class="mut">No scheduled jobs found.</td></tr>'

    act_rows = ""
    for e in execs[:cfg["max_actions"]]:
        jn = names.get(e.get("job_id"), (e.get("job_id") or "?")[:8])
        st = e.get("status","?")
        cls = {"failed":"f","succeeded":"s","success":"s"}.get(st,"m")
        t = (e.get("started_at") or "")[:16].replace("T"," ")
        err = ""
        if st == "failed" and e.get("error"):
            err = " — " + esc(e["error"][:90]) + ("…" if len(e["error"])>90 else "")
        act_rows += f'<tr><td class="mut">{esc(t)}</td><td>{esc(jn)}</td><td><span class="st {cls}">{esc(st)}</span>{err}</td></tr>'
    act_rows = act_rows or '<tr><td class="mut">No runs recorded yet.</td></tr>'

    an_html = "".join(
        f'<div class="anom"><span class="badge" style="color:{badge[k][1]};background:{badge[k][2]}">{badge[k][0]}</span> {esc(m)}</div>'
        for k, m in anom)

    sess_spark = " · ".join(f"{d}: {n}" for d, n in sorted(sess.items())) or "no recent activity"
    kpi_leads = (f'<div class="kpi"><div class="v">{leads["active"]}<span class="vsub">/{leads["total"]}</span></div>'
                 f'<div class="l">{esc(s.get("leads_label","Active items"))}</div></div>') if s.get("leads_db") else ""

    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(cfg['title'])}</title>
<style>
:root{{
  --bg:{'#f7f5f0' if light else '#101418'};--card:{'#ffffff' if light else '#181e25'};
  --line:{'#ddd6c9' if light else '#2a323c'};--tx:{'#191919' if light else '#e8edf2'};
  --mut:{'#6e6a60' if light else '#8a97a5'};--acc:{'#1e2bfa' if light else '#5b8def'};
  --ok:{'#15803d' if light else '#4ade80'};--bad:{'#dc2626' if light else '#f87171'};
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font:15px/1.55 'Space Grotesk',-apple-system,'Segoe UI',Roboto,sans-serif;padding:16px;max-width:900px;margin:0 auto}}
h1{{font-size:17px;font-weight:700;letter-spacing:.05em;text-transform:uppercase}}
h1::before{{content:"";display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--acc);margin-right:9px}}
.sub{{color:var(--mut);font-size:13px;margin-bottom:14px;font-family:-apple-system,'Segoe UI',Roboto,sans-serif}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:14px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}}
.kpi .v{{font-size:27px;font-weight:700;font-variant-numeric:tabular-nums;color:var(--acc)}}
.vsub{{font-size:15px;color:var(--mut);font-weight:500}}
.kpi .l{{color:var(--mut);font-size:11.5px;text-transform:uppercase;letter-spacing:.07em;margin-top:2px}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:14px}}
.panel h2{{font-size:11.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.09em;margin-bottom:10px}}
.anom{{padding:8px 0;border-bottom:1px solid var(--line);font-size:14px}} .anom:last-child{{border:none}}
.badge{{font-size:11px;font-weight:700;padding:2px 9px;border-radius:99px;margin-right:7px;font-family:'Space Grotesk',sans-serif}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}
td{{padding:7px 8px;border-top:1px solid var(--line);vertical-align:top}}
tr:first-child td{{border-top:none}}
.mut{{color:var(--mut)}}
.pill{{font-size:11px;font-weight:700;padding:2px 10px;border-radius:99px}}
.pill.on{{color:#fff;background:var(--acc)}} .pill.off{{color:var(--mut);background:transparent;border:1px solid var(--line)}}
.st.f{{color:var(--bad);font-weight:600}} .st.s{{color:var(--ok)}}
footer{{color:var(--mut);font-size:12px;text-align:center;margin-top:10px}}
@media(max-width:600px){{body{{padding:10px}} .kpi .v{{font-size:22px}}}}
</style></head><body>
<h1>{esc(cfg['title'])}</h1>
<div class="sub">{esc(now)} — supervision view · read-only</div>

<div class="grid">
<div class="kpi"><div class="v">{enabled_n}<span class="vsub">/{len(jobs)}</span></div><div class="l">Scheduled jobs on</div></div>
<div class="kpi"><div class="v" style="color:{'var(--bad)' if last24_fail else 'var(--acc)'}">{last24_fail}</div><div class="l">Failed runs (24h)</div></div>
<div class="kpi"><div class="v">{last24_ok}</div><div class="l">OK runs (24h)</div></div>
{kpi_leads}
</div>

<div class="panel"><h2>&#9888; Needs attention</h2>{an_html}</div>

<div class="panel"><h2>Scheduled jobs</h2><table><tbody>{job_rows}</tbody></table></div>
<div class="panel"><h2>Recent agent actions</h2><table><tbody>{act_rows}</tbody></table></div>
<div class="panel"><h2>Agent sessions ({cfg['session_days']}d)</h2><div style="font-size:13.5px">{esc(sess_spark)}</div></div>

<footer>{esc(cfg['footer'])}</footer>
</body></html>"""
    d = os.path.dirname(out_path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(doc)
    print(f"Wrote {out_path} ({len(doc)} bytes)")
    print(f"Jobs: {len(jobs)} ({enabled_n} on) | 24h: {last24_ok} ok / {last24_fail} failed")
    for k, m in anom:
        print(f"  [{badge[k][0]}] {m}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Scan-first agent supervision dashboard")
    ap.add_argument("--config", default=None, help="Path to config JSON")
    ap.add_argument("-o", "--output", default=None, help="Output HTML path")
    args = ap.parse_args()
    cfg = load_config(args.config)
    out = args.output or os.path.expanduser("~/agent-supervision/dashboard.html")
    build(cfg, out)
