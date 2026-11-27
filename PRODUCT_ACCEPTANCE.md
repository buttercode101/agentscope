# Product acceptance — 27 November 2026

This record supersedes the earlier dated release notes for the checks listed here. It does not erase their historical scope.

## Current product boundary

AgentScope is a local-first supervision CLI that reads configured agent sources and generates a standalone dashboard. The optional Habitat bridge is read-only. The public Vercel site is the product, demo and proof-explorer surface; it is **not** a hosted agent runtime or remote control plane.

## Verified build and workflows

| Check | Result |
|---|---|
| Full Python test suite | 154 passed, 6 skipped |
| Focused unittest suite (test_generate, test_habitat_bridge) | 32 passed |
| Browser acceptance | 5 pages × 5 viewport widths; navigation, filters, acknowledgement, clipboard, keyboard and proof-bundle checks passed |
| Live production browser | 3 routes × 8 viewport widths; all HTTP 200, no horizontal overflow, system dark palette changes |
| Live demo workflow | 24-hour/7-day filters and event visibility verified |
| Live proof explorer | 2 published historical bundles passed bundle digest, pinned manifest digest, ledger export and claim-consistency checks |
| Clean local install | Editable install in a fresh virtual environment, CLI help and HTML generation passed |
| Habitat bridge | Generated a dashboard from a real local Habitat SQLite fixture; ledger showed intact and the source DB SHA-256 was unchanged |

The production commit was deployed to the agent-supervision Vercel project. Live URL: https://agent-supervision.vercel.app/

## Evidence and trust boundary

- Disconnected core telemetry is now reported as **UNKNOWN**, not “All clear.”
- Missing-source findings cannot be acknowledged away.
- Missing job/execution/session sources show **UNKNOWN** in their KPIs and tables; connected but empty sources show real zero/no-run states.
- Job JSON and execution database schemas are validated before being reported ready.
- AgentScope reads monitored SQLite sources in read-only mode. A full dashboard build left the execution/lead database byte-for-byte unchanged, including when the legacy acknowledgement path pointed at that source.
- Empty-but-connected sources show a genuine zero/empty state; disconnected or invalid sources show UNKNOWN rather than zero counts. The unknown-state dashboard is included in the responsive browser fixture.
- MCP JSONL record shapes are validated; malformed records are skipped safely and a mixed file is reported as degraded.
- The Habitat bridge displays stored claim verdicts as stored records; it does not independently re-verify them.
- The published proof snapshots are unsigned. A matching digest proves bundle integrity, not publisher identity or external truth.
- The tested Habitat run was explicitly seeded sample data. No real autonomous agent execution was represented as live evidence.

## Remaining product limitations

- No hosted persistent Habitat API/service or multi-user control plane is deployed. Run the CLI/API locally; the public site is static.
- No Android wrapper or installable offline PWA has been delivered.
- No physical-device acceptance was performed.
- The integration verifies the local ledger-to-dashboard workflow, not a live third-party autonomous agent run.

These are intentional boundaries for the current local-first product, not capabilities claimed by the public site.
