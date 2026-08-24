# agentscope

**One clean screen that shows what your AI agents already did — so you catch problems fast without living in logs.**

A scan-first, supervision-only dashboard for people running multi-tool agent crews (Hermes, cron-driven agents, scheduled jobs). It answers a single question every morning: **"is anything off?"**

Not an orchestrator. Not a tracing tool. A supervision layer.

![dashboard](docs/screenshot.png)

## Why

Agent observability tools (LangSmith, Langfuse, Braintrust) are built for ML engineers debugging traces. But when your *agent crew* is doing the work — scheduled jobs, tool calls, campaigns — what the human needs is not a flame graph. It's a 10-second glance:

- Are my scheduled jobs actually running? (Silent drift-skips and disabled-by-accident jobs are the #1 failure mode.)
- What did my agents already do?
- Is anything off?

This was built dogfood-first: on its first real run it caught two production jobs that had been silently skipping for days due to inference config drift — fixed within minutes of seeing it.

## Features

- **KPI row** — jobs on/total, failed runs (24h), OK runs (24h), active items
- **Needs Attention panel** — surfaces ONLY real problems; quiet when healthy:
  - config-drift skips (job created under one provider/model, environment moved on)
  - auth failures (401/403 patterns)
  - repeated failures
  - accidentally-disabled jobs
- **Scheduled jobs table** with ON/OFF pills
- **Recent agent actions feed** (status + truncated error reasons)
- **Sessions activity sparkline**
- Dark, mobile-friendly, single self-contained HTML file
- Zero buttons — read-only by design. Supervision, not control plane.
- **Local-only**: reads local SQLite/JSON state; nothing leaves your device

## Quick start

```bash
# Auto-detects Hermes Agent layout (~/.hermes/)
python3 generate.py -o dashboard.html

# Or with a custom config (see config.example.json)
python3 generate.py --config myconfig.json -o dashboard.html
```

Open `dashboard.html` in any browser. Done.

### Daily digest (optional)

Wire `generate.py` into any scheduler and have the printed summary sent to yourself
(WhatsApp/Telegram/email). Example Hermes prompt: *"Run generate.py, turn the output
into a <200-word morning digest."*

## Configuration

`config.example.json`:

| Key | Purpose |
|---|---|
| `title`, `footer` | Page branding |
| `sources.cron_jobs_glob` | Glob for job-definition JSON files (`name`, `schedule.display`, `enabled`) |
| `sources.executions_db` | SQLite with an `executions` table (`job_id`, `status`, `started_at`, `error`) |
| `sources.sessions_dir` | Directory of session files (activity counted by mtime) |
| `sources.leads_db` + `leads_query` | Optional generic counter (leads, tasks, tickets): `[total_sql, active_sql]` |
| `session_days`, `max_actions` | Display tuning |

Any source can be `null` to skip it. The anomaly logic lives in `anomalies()` — extend the signature list for your own stack's failure modes.

## Requirements

Python 3.8+, stdlib only. No dependencies.

## Roadmap

- [ ] Pluggable source adapters (n8n, Temporal, raw MCP activity logs)
- [ ] Token/cost column from usage audit logs
- [ ] Hosted multi-source version (if demand appears)
- [ ] Anomaly rule packs per agent framework

## License

MIT
