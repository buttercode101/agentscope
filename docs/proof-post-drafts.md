# Proof post drafts — agentscope launch

## X/Twitter thread version

**1/**
I run a crew of AI agents — scheduled jobs, campaigns, tool calls running 24/7.

This morning my new supervision dashboard caught something I'd missed for days: two production jobs silently skipping every single run.

Here's the screen that did it 🧵 [screenshot]

**2/**
The design philosophy is one question: "is anything off?"

Not traces. Not flame graphs. Not another observability platform for ML engineers.

One dark page, readable in 10 seconds:
• KPI row: jobs on/off, fails last 24h
• "Needs attention" panel — quiet when healthy
• What agents already did

**3/**
What it caught on day one:

My tender-discovery jobs were created under one model config. The global config later moved. The scheduler noticed the mismatch — and silently skipped every run to "prevent unintended spend."

Silent = worst kind of failure. No error surfaced anywhere I looked. The dashboard flagged it as FAIL with the exact fix hint. Two minutes to fix.

**4/**
Key design rule: it's a *supervision* layer, not an operation layer.

Zero buttons. Read-only. The UI doesn't ask "what can you do here?" — it answers "is anything off with what was already done?"

Interfaces are inverting: fewer buttons, more signal.

**5/**
It's open source, stdlib-only Python (~300 lines), renders a single self-contained HTML file. All data stays local — reads your agent state, nothing leaves the machine.

Works with Hermes out of the box; config-driven for anything else.

→ github.com/buttercode101/agentscope

## LinkedIn / longer post version

I supervise a workforce of AI agents from one page. Here's what it caught on day one.

(Then: same story arc, add paragraph on AX thesis — "the UI isn't dying, it's moving from operation layer to supervision layer" — close with repo link + offer: building this for your agent stack, DM me.)

## Reddit r/HermesAI / r/AI_Agents version

Title: I built a scan-first supervision dashboard for my agent crew (open source, stdlib-only)

Body: story + what it does + honest scope ("not tracing, not orchestration") + repo link + ask: "what failure modes would you want flagged?"
