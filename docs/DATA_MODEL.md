# AgentScope + Habitat data boundaries

## AgentScope operational inputs

AgentScope's existing generator reads configured local sources:

- Job definition JSON files.
- Execution-history SQLite database.
- Session directory metadata.
- Optional business counters.
- Optional MCP/tool-call JSONL.
- Optional acknowledgement state.

The generated HTML contains a snapshot of the data read at generation time. It is not a live query interface.

## Habitat runtime records

Habitat owns its local SQLite schema. AgentScope does not migrate or write this schema.

| Record | Purpose |
|---|---|
| habitat | Runtime identity, model and overall status |
| job | Scheduled work and latest observed execution state |
| signal | Active/resolved anomaly signals with severity |
| action | Trusted action ledger entries |
| action_integrity | Hash-chain links for tamper detection |
| claim | Bounded assertion and its stored verification verdict |
| event | Ingested structured agent event |
| agent | Registered agent identity and permissions |

## AgentScope projection

The bridge reads only:

- Habitat identity and status.
- Enabled/total job counts.
- Counts of active signals by severity.
- Counts of claims by stored verdict.
- Action-ledger integrity result.

It deliberately excludes agent secrets, permissions, raw event payloads, action details, claim evidence bodies, and proof contents from the dashboard summary.

## Trust semantics

- `available=false`: source missing, uninitialized, unreadable, or structurally incomplete; display UNKNOWN.
- `ledger_integrity=intact`: the current action rows match the stored hash chain.
- `ledger_integrity=failed`: the hash chain is incomplete or does not match; surface FAIL.
- `ledger_integrity=unknown`: integrity metadata is absent or uninitialized; never treat as intact.
- Claim counts represent stored Habitat verdicts only. They are not a fresh verification of each claim.
- A valid proof bundle proves properties of the recorded evidence bundle, not that the external world necessarily matches the claim.

## Retention and migration

Habitat remains the system of record for its evidence and proof data. Preserve the original Habitat database and repository until backup/restore, schema migration, and proof-verification tests pass against the unified build. Never rewrite or deduplicate historical proof records during this integration.
