# Security Policy

## Reporting a vulnerability

If you discover a security issue in agentscope, please report it
**privately** rather than opening a public issue:

- Email: **security@buttercode101.com**, or
- Open a GitHub private vulnerability report on this repository.

Include steps to reproduce, the impact you believe it has, and any
suggested fix. We acknowledge reports within 48 hours and aim to
resolve confirmed issues promptly. Please do not disclose the issue
publicly until a fix is available.

## Data handling

`generate.py` reads **local** agent state (cron job definitions,
execution logs, session records — by default under `~/.hermes/`, or
paths you configure) and renders a **self-contained static HTML**
dashboard.

- **Data never leaves the machine.** The generator makes no network
  calls, runs no server, and uploads nothing. The public website is a
  static product page; your generated dashboards are local files.
- **Read-only supervision.** agentscope inspects state; it does not
  control agents, and the dashboard contains no operation buttons.
- **Sensitive local data (e.g. prompts, credentials in logs) can end
  up in the generated HTML.** Treat the output file like the source
  data: do not publish it to a public host without review.
- **Local helper files.** Sample data under `data/` is illustrative
  only; do not put real credentials into scanned paths.

## Known limitations (not vulnerabilities)

- Generated HTML is not sanitised for every possible log format;
  source data containing script-like strings is rendered as evidence,
  not executed by this tool — but a user who opens a maliciously
  crafted source file could be exposed. Do not scan untrusted inputs
  in a browser you would not trust with the source itself.
- agentscope reports system-recorded state; it cannot verify things
  that never happened. "Running" means observed evidence, not proof
  of external truth.

## Scope

In scope: `generate.py` and the published demo page.

Out of scope: hosted AI-agent platforms (Hermes Agent, LangSmith,
and similar) except as data sources, and third-party hosts
(Vercel, GitHub) except as they deliver this repository's artifacts.

## P0 note — commission evidence removed from public repo

Commission evidence (the Madlanga commission evidence API previously
mixed into this dashboard repo: `api/`, `data/commission.json`,
`evidence.db`, `data/snapshots/*.bin`, `data/*.bin`) has been moved
out of this public repository and removed from the current HEAD.

**Residual risk:** earlier commits still contain this evidence.
Removing files from HEAD does **not** purge git history. A full history
purge would require a force-push, which was **not** performed as part
of this change. Anyone with access to an old commit, mirror, fork, or
GitHub cache can still retrieve the previously exposed files. Treat
previously public evidence as exposed, rotate/revoke anything that
was secret in it, and consider a history purge (e.g. `git filter-repo`
+ force-push) as a separate, explicitly approved decision.
