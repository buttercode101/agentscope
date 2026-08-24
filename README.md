<div align="center">

# agentscope

**One clean screen for your AI agent crew.**
*Your agents worked all night. Is anything off?*

[Live site](https://agentscope-liard.vercel.app) · [Get started](#quick-start) · [MIT licensed](LICENSE)

</div>

---

A scan-first, supervision-only dashboard for people running multi-tool agent crews (Hermes Agent, cron-driven jobs, scheduled workflows). It renders one self-contained HTML page that answers a single question every morning:

> **"Is anything off?"**

Not an orchestrator. Not distributed tracing. A supervision layer.

![dashboard](docs/screenshot.png)

## Why

Agent observability platforms (LangSmith, Langfuse, Braintrust) are built for ML engineers reading traces. When your *agent crew* is doing the work — scheduled jobs, campaigns, tool calls around the clock — the human need is different:

- Are my scheduled jobs **actually running**? (Silent config-drift skips and accidentally-disabled jobs are the #1 failure mode in practice.)
- What did my agents **already do**?
- Is anything off?

The interface inverts: fewer buttons, more signal. agentscope has zero controls. It's read-only by design.

## What it caught on day one

Two production jobs had been silently skipping every run for days: their inference config had drifted from the global environment, and the scheduler skipped them "to prevent unintended spend" — with no error surfacing anywhere. The dashboard's first render flagged both as FAIL with the exact fix hint. Fixed in two minutes.

That's the whole thesis: supervision surfaces what logs hide.

## Panels

| Panel | Answers |
|---|---|
| KPI row | Jobs on/total, failed runs 24h, OK runs 24h, active items |
| ⚠ Needs attention | Anomalies ONLY — quiet when healthy. Config-drift skips, auth failures (401/403), repeat failures, disabled jobs |
| Scheduled jobs | Every job with ON/OFF pill and cadence |
| Recent agent actions | Status feed with truncated error reasons |
| Sessions sparkline | Activity per day |

## Quick start

```bash
# auto-detects Hermes Agent layout (~/.hermes/)
python3 generate.py -o dashboard.html

# or point it at your own stack
python3 generate.py --config myconfig.json -o dashboard.html
```

Open `dashboard.html` in any browser. Done.

Requirements: Python 3.8+, stdlib only. Zero dependencies.

### Daily digest (optional)

Wire `generate.py` into any scheduler and have its printed summary sent to yourself (WhatsApp/Telegram/email). Example Hermes prompt: *"Run generate.py, turn the output into a <200-word morning digest."*

## Configuration

Copy `config.example.json`:

| Key | Purpose |
|---|---|
| `title`, `footer`, `theme` | Branding; `"dark"` or `"light"` |
| `sources.cron_jobs_glob` | Glob for job-definition JSON files (`name`, `schedule.display`, `enabled`) |
| `sources.executions_db` | SQLite with an `executions` table (`job_id`, `status`, `started_at`, `error`) |
| `sources.sessions_dir` | Directory of session files (activity counted by mtime) |
| `sources.leads_db` + `leads_query` | Optional generic counter: `[total_sql, active_sql]` |
| `session_days`, `max_actions` | Display tuning |

Any source may be `null` to skip it. The anomaly logic lives in `anomalies()` — extend the signature list for your own stack's failure modes.

## Scope

**In:** supervision of scheduled agent work, anomaly surfacing, one-page scanning.
**Out:** orchestration, deep tracing, multi-user permissions, automatic fixing. This is a supervision layer, not a control plane.

## Roadmap

- [ ] Pluggable source adapters (n8n, Temporal, raw MCP activity logs)
- [ ] Token/cost column from usage audit logs
- [ ] Hosted multi-source version (if demand appears)
- [ ] Anomaly rule packs per agent framework

## License

MIT
