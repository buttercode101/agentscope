# AgentScope + Habitat integration

## Decision

AgentScope remains the user-facing product and generated supervision dashboard. Habitat is integrated as the local evidence, claim-verification, policy, action-ledger, and proof runtime.

This is a single product experience with a separately bounded evidence subsystem. It is not an orchestration/control plane: AgentScope remains read-only and the dashboard bridge never executes jobs, changes claims, acknowledges signals, or mutates Habitat state.

## What is integrated on this branch

- The Habitat Python runtime is vendored under `habitat/` from upstream Habitat commit `b823836d826a73f1edcea3ff0c5b7ba7399a6219`.
- AgentScope packaging now includes the Habitat package.
- `agentscope_habitat.py` reads an explicitly configured Habitat SQLite database using SQLite read-only mode.
- The generated AgentScope dashboard can display Habitat runtime health, job counts, active signals, stored claim verdict counts, and action-ledger integrity.
- Missing/unreadable Habitat state is shown as UNKNOWN, never as healthy.
- A failed action-ledger integrity check is surfaced as a failure.
- The bridge labels claim verdicts as recorded state; it does not pretend to freshly re-verify them.

## Configuration

Set `sources.habitat_db` to the path of an existing initialized Habitat SQLite database. Leave it null to preserve AgentScope's current behaviour.

Example:

```json
{
  "sources": {
    "habitat_db": "~/.habitat/habitat.db"
  }
}
```

Use the actual database path configured for the local Habitat installation; the example path is illustrative.

## Trust boundaries

1. AgentScope opens the database with SQLite `mode=ro`; it does not run Habitat migrations or write to the database.
2. A dashboard snapshot is observational, not an external attestation.
3. A stored `verified` claim is displayed as a stored verdict. Re-verification requires the Habitat verification flow and its original evidence adapters.
4. A proof bundle's content integrity, signature validity, publisher trust, and truth in the outside world remain distinct questions.
5. The original Habitat repository remains intact as the upstream source until this integration passes CI, regression, security, and live-deployment acceptance.

## Validation still required before release

- Run the full AgentScope unittest suite and Habitat test suite in the unified repository.
- Add fixture coverage for malformed, migrated, and tampered Habitat databases.
- Verify no read-only bridge path writes, migrates, or locks the source database.
- Exercise the dashboard with no Habitat DB, a healthy DB, active signals, failed ledger integrity, and recorded claims.
- Inspect the live Vercel deployment and verify the intended runtime mode. The public AgentScope website is currently a static product/demo surface; it must not be mistaken for a hosted Habitat database.
- Decide whether to keep Habitat as an independently installable CLI distribution or expose the runtime through an optional extra after packaging and release tests.

## Upstream provenance

- AgentScope source: `buttercode101/agentscope`, main baseline at integration branch creation.
- Habitat source: `buttercode101/Habitat`, `b823836d826a73f1edcea3ff0c5b7ba7399a6219`.
- Both upstream repositories are MIT licensed. Keep their notices and attribution when redistributing integrated code.
