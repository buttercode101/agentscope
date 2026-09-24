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
import argparse, json, sqlite3, os, glob, html, re
from datetime import datetime, timedelta

# ---------------------------------------------------------------- helpers ---

def rel_time(iso_str):
    """Human relative timestamp: '2h ago', 'yesterday', '3d ago'."""
    if not iso_str:
        return ""
    try:
        t = datetime.fromisoformat(str(iso_str))
        if t.tzinfo is not None:
            t = t.replace(tzinfo=None)  # compare naive-to-naive (local render time)
        delta = datetime.now() - t
    except Exception:
        return str(iso_str)[:16].replace("T", " ")
    mins = int(delta.total_seconds() // 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins}m ago"
    hours = int(mins // 60)
    if hours < 24:
        return f"{hours}h ago"
    days = int(hours // 24)
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days}d ago"
    return t.strftime("%d %b")

def humanize(status, error=""):
    """Short human-readable outcome instead of raw error text."""
    st = (status or "").lower()
    low = (error or "").lower()
    if "drift" in low or ("config" in low and "skip" in low):
        return "Skipped – inference config drifted"
    if any(k in low for k in ("rate limit", "429", "too many requests")):
        return "Failed – rate limited"
    if any(k in low for k in ("auth", "api key", "unauthorized", "401", "403")):
        return "Failed – credentials rejected"
    if "timeout" in low or "timed out" in low:
        return "Failed – timed out"
    if "quota" in low or "credit" in low:
        return "Failed – quota/credits exhausted"
    if "network" in low or "connection" in low:
        return "Failed – network error"
    if st == "failed":
        first = (error or "").split(".")[0].split("\n")[0]
        return "Failed – " + (first[:70] + "…" if len(first) > 70 else first or "unknown error")
    if st in ("succeeded", "success", "ok", "completed"):
        return "Completed"
    if st == "running":
        return "Running now"
    return status or "Unknown"

def parse_cadence_minutes(sched_s):
    """Best-effort parse of 'every 360m' / 'every 2h' / cron-ish displays."""
    s = (sched_s or "").lower()
    try:
        if "every" in s and "m" in s and "h" not in s:
            return int(re.search(r"(\d+)", s).group(1))
        if "every" in s and "h" in s:
            return int(re.search(r"(\d+)", s).group(1)) * 60
        if "daily" in s or ("0 *" in s and "*" in s):
            return 1440
    except Exception:
        pass
    return None


def success_rates(execs, min_runs=3):
    """Per-job success rate over recent runs. Flags high-failure jobs.

    Returns dict: jid -> {"total": n, "ok": k, "rate": float}
    Only meaningful when a job has >= min_runs recorded.
    """
    stats = {}
    for e in execs[-40:]:
        jid = e.get("job_id")
        if not jid:
            continue
        s = stats.setdefault(jid, {"total": 0, "ok": 0})
        s["total"] += 1
        if (e.get("status") or "").lower() in ("succeeded", "success", "ok", "completed"):
            s["ok"] += 1
    out = {}
    for jid, s in stats.items():
        if s["total"] >= min_runs:
            out[jid] = {"total": s["total"], "ok": s["ok"], "rate": round(s["ok"] / s["total"] * 100)}
    return out

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
    "group_by": "none",                  # "none" | "group" — group jobs by their 'group'/'project' field
    "compact": False,                    # compact density option
    "ack_db": "~/.hermes/cron/executions.db",  # sqlite for acknowledged anomalies (table: acks(key TEXT, ts))
        "mcp_jsonl": None,                 # optional JSONL of MCP/tool calls: {"tool","ts","ok"}
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
    for k in ("cron_jobs_glob", "executions_db", "sessions_dir", "leads_db", "ack_db"):
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
                             "enabled": bool(j.get("enabled", True)),
                             "id": j.get("id", ""),
                             "group": j.get("group", j.get("project", "")) or ""})
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

    # per-job failure stats over last 20 runs
    fails = {}
    for e in execs[-20:]:
        if e.get("status") == "failed":
            fails.setdefault(e.get("job_id"), []).append(e)

    # last successful run per job (for overdue detection)
    last_run = {}
    for e in execs:
        jid = e.get("job_id")
        if jid and jid not in last_run and e.get("started_at"):
            last_run[jid] = e["started_at"]

    drift, other = [], {}
    for jid, flist in fails.items():
        err_text = next((e.get("error","") for e in reversed(flist) if e.get("error")), "")
        low = err_text.lower()
        label = jid[:8]
        nfail = len(flist)
        if "drift" in low or ("config" in low and "skip" in low):
            drift.append(label)
        elif any(sig in low for sig in ("auth", "api key", "unauthorized", "403", "401")):
            other[f"auth:{label}"] = f"auth failing ({nfail}x) — check credentials"
        elif nfail >= 3:
            other[label] = f"failed {nfail}x in a row — likely broken"
        else:
            reason = humanize("failed", err_text).replace("Failed – ", "")
            other[label] = f"failed {nfail}x — {reason}"

    for jn in drift:
        a.append(("fail", f"'{jn}' skipping every run — config drifted. Re-pin to restore."))
    for jn, msg in other.items():
        sev = "fail" if any(w in msg for w in ("broken", "auth")) else "fail"
        a.append((sev, f"'{jn}': {msg}"))

    # overdue: enabled jobs that should have run but haven't recently
    job_ids_by_name = {}
    for path in glob.glob("*"):  # names resolved later in build; use exec-db mapping
        break
    for jid, ts in last_run.items():
        try:
            age_h = (datetime.now() - datetime.fromisoformat(ts)).total_seconds() / 3600
        except Exception:
            continue
        if age_h > 48:
            # only flag if this job has recent failures too (enabled check happens in build)
            pass
    if not a:
        a.append(("ok", "All clear — nothing off."))
    return [(k, m, ack_key(k, m)) for k, m in a]


def ack_load(db_path):
    """Load set of acknowledged anomaly keys."""
    acks = set()
    try:
        c = sqlite3.connect(db_path)
        c.execute("CREATE TABLE IF NOT EXISTS acks(key TEXT PRIMARY KEY, ts TEXT)")
        for (k,) in c.execute("SELECT key FROM acks"):
            acks.add(k)
    except Exception:
        pass
    return acks

def ack_key(kind, msg):
    """Stable short key for an anomaly message."""
    import hashlib
    return hashlib.sha1(f"{kind}:{msg}".encode()).hexdigest()[:10]


def mcp_tool_stats(jsonl_path):
    """Per-tool success counts from an MCP activity JSONL.

    Expected line shape: {"tool": "server.tool", "ts": "...", "ok": true}
    Returns list of {"tool","total","rate"} sorted by volume, or [] if absent.
    """
    out = {}
    try:
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                tool = rec.get("tool") or rec.get("name")
                if not tool:
                    continue
                s = out.setdefault(tool, {"total": 0, "ok": 0})
                s["total"] += 1
                okv = rec.get("ok", rec.get("success", True))
                if okv in (True, "true", 1, "1"):
                    s["ok"] += 1
    except Exception:
        pass
    rows = [{"tool": t, "total": v["total"],
             "rate": round(v["ok"] / v["total"] * 100) if v["total"] else 0}
            for t, v in out.items()]
    return sorted(rows, key=lambda r: -r["total"])[:8]

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
    all_anom = anomalies(jobs, execs)
    acks = ack_load(s.get("ack_db")) if s.get("ack_db") else set()
    anom = [x for x in all_anom if x[2] not in acks]
    ackd = [x for x in all_anom if x[2] in acks]
    if not anom and ackd:
        anom = [("ok", f"All clear - {len(ackd)} item(s) acknowledged.", "")]

    enabled_n = sum(1 for j in jobs if j["enabled"])
    day_ago = (datetime.now()-timedelta(days=1)).strftime("%Y-%m-%dT")
    last24_fail = sum(1 for e in execs if e.get("status")=="failed" and (e.get("started_at") or "") >= day_ago)
    last24_ok = sum(1 for e in execs if e.get("status") in ("succeeded","success","ok") and (e.get("started_at") or "") >= day_ago)
    names = job_names(s["cron_jobs_glob"], s["executions_db"]) if s.get("executions_db") else {}
    rates = success_rates(execs)
    mcp_rows = mcp_tool_stats(s["mcp_jsonl"]) if s.get("mcp_jsonl") else []

    job_rows = "".join(
        f'<tr><td>{esc(j["name"])}</td><td class="mut">{esc(j["schedule"])}</td>'
        f'<td><span class="pill {"on" if j["enabled"] else "off"}">{"ON" if j["enabled"] else "OFF"}</span></td></tr>'
        for j in jobs) or '<tr><td class="mut">No scheduled jobs found.</td></tr>'

    act_rows = ""
    for e in execs[:cfg["max_actions"]]:
        jn = names.get(e.get("job_id"), (e.get("job_id") or "?")[:8])
        st = e.get("status","?")
        cls = {"failed":"f","succeeded":"s","success":"s"}.get(st,"m")
        outcome = humanize(st, e.get("error",""))
        ts = rel_time(e.get("started_at"))
        # data-age attr powers the client-side time filter
        act_rows += f'<tr data-ts="{esc(e.get("started_at") or "")}"><td class="mut nowrap">{esc(ts)}</td><td>{esc(jn)}</td><td><span class="st {cls}">{outcome}</span></td></tr>'
    act_rows = act_rows or '<tr><td class="mut">No runs recorded yet.</td></tr>'

    def _anom_row(item, with_ack=False):
        k, m = item[0], item[1]
        key = item[2] if len(item) > 2 else ""
        btn = ""
        if with_ack and key:
            btn = ('<button class="ackbtn" data-key="' + esc(key) + '" '
                   'title="Mark as seen - hides until it changes">Got it</button>')
        ak = ' data-ak="' + esc(key) + '"' if key else ""
        return ('<div class="anom"' + ak + '>'
                '<span class="badge" style="color:' + badge[k][1] + ';background:' + badge[k][2] + '">' + badge[k][0] + '</span> '
                + esc(m) + btn + '</div>')
    active_items = [x for x in anom if x[0] != "ok"]
    ok_items = [x for x in anom if x[0] == "ok"]
    an_html = "".join(_anom_row(x, with_ack=True) for x in active_items)
    if ok_items and not active_items:
        an_html = _anom_row(ok_items[0])
    if ackd:
        an_html += '<div class="mut" style="font-size:12px;margin-top:8px">&amp;#9745; ' + str(len(ackd)) + ' acknowledged (hidden until they change)</div>'

    def _job_row(j):
        """One jobs-table row; gains a health % cell when data supports it."""
        jid = j.get("id") or ""
        r = rates.get(jid) or rates.get(jid[:8])
        if r and j["enabled"]:
            pct = r["rate"]
            cls = "ok" if pct >= 80 else ("warn" if pct >= 50 else "bad")
            health = f'<td><span class="hlth {cls}">{pct}%</span><span class="vsub"> of {r["total"]}</span></td>'
        elif not j["enabled"]:
            health = '<td class="mut">-</td>'
        else:
            health = '<td class="mut">n/a</td>'
        return ('<tr><td>' + esc(j["name"]) + '</td><td class="mut">' + esc(j["schedule"]) + '</td>'
                '<td><span class="pill ' + ("on" if j["enabled"] else "off") + '">' + ("ON" if j["enabled"] else "OFF") + '</span></td>'
                + health + '</tr>')

    # jobs table with optional grouping
    group_by = cfg.get("group_by", "none")
    if group_by == "group" and any(j.get("group") for j in jobs):
        groups = {}
        for j in jobs:
            groups.setdefault(j.get("group") or "Other", []).append(j)
        parts = []
        for g in sorted(groups):
            gj = sorted(groups[g], key=lambda x: (not x["enabled"], x["name"].lower()))
            n_on = sum(1 for j in gj if j["enabled"])
            rows = "".join(
                '<tr><td>' + esc(j["name"]) + '</td><td class="mut">' + esc(j["schedule"]) + '</td>'
                '<td><span class="pill ' + ("on" if j["enabled"] else "off") + '">' + ("ON" if j["enabled"] else "OFF") + '</span></td></tr>'
                for j in gj)
            parts.append('<tr class="grp"><td colspan="4">' + esc(g) +
                         ' <span class="vsub">- ' + str(n_on) + '/' + str(len(gj)) + ' on</span></td></tr>')
        for j in gj:
            parts.append(_job_row(j))
        job_rows = "".join(parts)
    else:
        job_rows = "".join(_job_row(j) for j in jobs) or '<tr><td class="mut" colspan="4">No scheduled jobs found.</td></tr>'

    sess_spark = " · ".join(f"{d}: {n}" for d, n in sorted(sess.items())) or "no recent activity"

    if mcp_rows:
        mrows = "".join(
            '<tr><td>' + esc(r["tool"]) + '</td>'
            '<td class="mut">' + str(r["total"]) + ' calls</td>'
            '<td><span class="hlth ' + ("ok" if r["rate"] >= 80 else ("warn" if r["rate"] >= 50 else "bad")) + '">' + str(r["rate"]) + '%</span></td></tr>'
            for r in mcp_rows)
        mcp_panel = ('<div class="panel"><h2>MCP / tool calls</h2>'
                     '<table><tbody>' + mrows + '</tbody></table></div>')
    else:
        mcp_panel = ""
    kpi_leads = (f'<div class="kpi"><div class="v">{leads["active"]}<span class="vsub">/{leads["total"]}</span></div>'
                 f'<div class="l">{esc(s.get("leads_label","Active items"))}</div></div>') if s.get("leads_db") else ""

    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(cfg['title'])}</title>
<style>
:root{--bg:#0b0d10;--card:#11151a;--line:#272e37;--tx:#eef1f4;--mut:#89939f;--acc:#7694ff;--ok:#56d68b;--bad:#ff7373;--warn:#e6ad59}
*{box-sizing:border-box;margin:0;padding:0}html{scroll-behavior:smooth}body{background:var(--bg);color:var(--tx);font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;padding:18px;width:min(1120px,calc(100% - 24px));margin:0 auto;-webkit-font-smoothing:antialiased}h1{font:800 15px ui-monospace,SFMono-Regular,monospace;letter-spacing:.06em;text-transform:uppercase;margin:2px 0}.sub{color:var(--mut);font:11px ui-monospace,monospace;margin:6px 0 18px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:10px}.kpi,.panel{background:var(--card);border:1px solid var(--line);border-radius:11px}.kpi{padding:15px}.kpi .v{font:800 28px ui-monospace,monospace;color:var(--acc);font-variant-numeric:tabular-nums}.vsub{font-size:13px;color:var(--mut);font-weight:500}.kpi .l{color:var(--mut);font:800 9px ui-monospace,monospace;text-transform:uppercase;letter-spacing:.1em;margin-top:4px}.panel{padding:15px;margin-bottom:10px;overflow-x:auto}.panel h2{font:800 10px ui-monospace,monospace;color:var(--mut);text-transform:uppercase;letter-spacing:.11em;margin-bottom:10px}.panel.attn{border-color:#5e3438}.panel.attn h2{color:#ff9c9c}.panel.calm{opacity:.9}.anom{padding:11px 0;border-top:1px solid var(--line);font-size:12px}.anom:first-of-type{border-top:0}.badge{font:800 9px ui-monospace;padding:4px 7px;border-radius:5px;margin-right:7px}.nowrap{white-space:nowrap}table{width:100%;min-width:620px;border-collapse:collapse;font-size:12px}td{padding:10px 8px;border-top:1px solid var(--line);vertical-align:top}tr:first-child td{border-top:0}.mut{color:var(--mut)}.pill{font:800 9px ui-monospace;padding:4px 7px;border-radius:999px}.pill.on{background:#143323;color:#7de3a6}.pill.off{border:1px solid var(--line);color:#77818c}.st{font-weight:600}.st.f{color:var(--bad)}.st.s{color:var(--ok)}.chips{display:flex;gap:6px;margin-bottom:8px}.chip{font:800 10px ui-monospace;padding:6px 10px;border-radius:7px;border:1px solid var(--line);background:transparent;color:var(--mut);cursor:pointer}.chip.active{background:#252e43;border-color:#3d4f80;color:#dce4ff}.hlth{font:800 10px ui-monospace;padding:3px 7px;border-radius:999px}.hlth.ok{color:var(--ok);background:#143323}.hlth.warn{color:var(--warn);background:#3d2e18}.hlth.bad{color:var(--bad);background:#4a2024}.ackbtn{float:right;font:800 9px ui-monospace;padding:4px 8px;border-radius:7px;border:1px solid var(--line);background:transparent;color:var(--mut);cursor:pointer}.ackbtn:hover{border-color:#56606c}.ackbtn:disabled{cursor:default;opacity:.65}tr.grp td{background:#151a20;color:var(--mut);font:800 9px ui-monospace;text-transform:uppercase;letter-spacing:.1em}footer{color:#66717d;font:10px ui-monospace;text-align:center;margin-top:14px}
@media(max-width:760px){body{width:calc(100% - 20px);padding:12px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.kpi .v{font-size:23px}.panel{padding:12px}}@media(max-width:420px){.grid{grid-template-columns:1fr}.kpi .v{font-size:25px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body class="{'compact' if cfg.get('compact') else ''}">
<h1>{esc(cfg['title'])}</h1>
<div class="sub">{esc(now)} — supervision view · read-only</div>

<div class="grid">
<div class="kpi"><div class="v">{enabled_n}<span class="vsub">/{len(jobs)}</span></div><div class="l">Scheduled jobs on</div></div>
<div class="kpi"><div class="v" style="color:{'var(--bad)' if last24_fail else 'var(--acc)'}">{last24_fail}</div><div class="l">Failed runs (24h)</div></div>
<div class="kpi"><div class="v">{last24_ok}</div><div class="l">OK runs (24h)</div></div>
{kpi_leads}
</div>

<div class="panel {'attn' if not anom[0][0] == 'ok' else 'calm'}"><h2>&#9888; Needs attention</h2>{an_html}</div>

<div class="panel"><h2>Scheduled jobs &amp; health</h2><table><tbody>{job_rows}</tbody></table></div>
<div class="panel"><h2>Recent agent actions</h2>
<div class="chips" role="group" aria-label="Time range filter">
<button class="chip active" data-range="7">Last 7 days</button>
<button class="chip" data-range="1">Last 24h</button>
</div>
<table id="actions-table"><tbody>{act_rows}</tbody></table></div>
<script>
(function(){{
  var chips=document.querySelectorAll('.chip');
  chips.forEach(function(c){{c.addEventListener('click',function(){{
    chips.forEach(function(x){{x.classList.remove('active')}});
    c.classList.add('active');
    var cutoff=Date.now()-(parseInt(c.dataset.range)*864e5);
    document.querySelectorAll('#actions-table tr[data-ts]').forEach(function(tr){{
      var ts=Date.parse(tr.dataset.ts);
      tr.style.display=(isNaN(ts)||ts>=cutoff)?'':'none';
    }});
  }})}});
}})();
(function(){{
  document.querySelectorAll('.ackbtn').forEach(function(b){{
    b.addEventListener('click',function(){{
      var key=b.dataset.key, dv=b.closest('.anom');
      try{{var s=JSON.parse(localStorage.getItem('as_ack')||'[]');if(s.indexOf(key)<0){{s.push(key);localStorage.setItem('as_ack',JSON.stringify(s));}}}}catch(e){{}}
      if(dv){{dv.style.opacity='.45';}}
      b.textContent='Seen';
      b.disabled=true;
    }});
  }});
  // re-apply locally acknowledged state on load
  try{{
    var s=JSON.parse(localStorage.getItem('as_ack')||'[]');
    document.querySelectorAll('.ackbtn').forEach(function(b){{
      if(s.indexOf(b.dataset.key)>=0){{b.click();}}
    }});
  }}catch(e){{}}
}})();
</script>
{mcp_panel}<div class="panel"><h2>Agent sessions ({cfg['session_days']}d)</h2><div style="font-size:13.5px">{esc(sess_spark)}</div></div>

<div style="text-align:center;margin:6px 0 14px">
<button id="sharebtn" class="chip" title="Copy a clean text summary">Copy status summary</button>
</div>
<footer>{esc(cfg['footer'])}</footer>
<script>
(function(){{
  var b=document.getElementById('sharebtn');
  if(!b)return;
  b.addEventListener('click',function(){{
    var lines=[document.querySelector('h1').textContent+' - '+document.querySelector('.sub').textContent.split(' — ')[0]];
    document.querySelectorAll('.kpi').forEach(function(k){{
      lines.push(k.querySelector('.l').textContent+': '+k.querySelector('.v').textContent);
    }});
    var attn=document.querySelector('.panel.attn,.panel.calm h2');
    document.querySelectorAll('.anom').forEach(function(a){{lines.push('- '+a.textContent.replace('Got it','').trim());}});
    try{{
      navigator.clipboard.writeText(lines.join('\\n')).then(function(){{
        b.textContent='Copied';setTimeout(function(){{b.textContent='Copy status summary';}},2000);
      }},function(){{b.textContent='Clipboard blocked';}});
    }}catch(e){{b.textContent='Clipboard unavailable';}}
  }});
}})();
</script>

</body></html>"""
    d = os.path.dirname(out_path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(doc)
    print(f"Wrote {out_path} ({len(doc)} bytes)")
    print(f"Jobs: {len(jobs)} ({enabled_n} on) | 24h: {last24_ok} ok / {last24_fail} failed")
    for item in anom:
        k, m = item[0], item[1]
        print(f"  [{badge[k][0]}] {m}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Scan-first agent supervision dashboard")
    ap.add_argument("--config", default=None, help="Path to config JSON")
    ap.add_argument("-o", "--output", default=None, help="Output HTML path")
    args = ap.parse_args()
    cfg = load_config(args.config)
    out = args.output or os.path.expanduser("~/agent-supervision/dashboard.html")
    build(cfg, out)
