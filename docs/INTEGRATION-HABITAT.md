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
5. Habitat remains independently maintained in its upstream repository; this vendored integration does not modify the upstream repository.

## Production release verification — 12 November 2026

The following checks were completed against the current production release:

- Production source commit: `89fe2adc9b974741ecbf1f08bd3024495c7d3740` (the product-code commit verified for this report).
- GitHub Actions completed the full Python 3.11 pytest suite with **147 passed
  in 3.25s** on the pull-request head that was merged into this release:
  [workflow run 43210791363](https://github.com/buttercode101/agentscope/actions/runs/43210791363).
- Vercel production deployment `dpl_971KVFq4H7z5ViQEWmHV1SNp6CSn` reached
  `READY` from `main` at the product-code commit above.
- The homepage, demo, proof index, manifest, and both published proof JSON
  resources returned HTTP 200 after the latest production deployment.
- Both historical proof digests were recomputed using Habitat's canonical
  JSON rules. Both ledgers reported `intact`, both verified claims resolved
  to their matching evidence actions, and both bundles were unsigned.
- Regression tests now cover Unicode proof canonicalization, read-only
  snapshots of a healthy Habitat database, unchanged database bytes after
  bridge reads, tampered action-integrity hashes, missing/incomplete database
  states, SQLite backup/restore of a populated fixture, Unicode Ed25519
  signing, signature tamper rejection, and a mobile-layout regression guard for unbroken SHA-256 digest strings.
- The optional signing extra is declared as
  `pip install 'agentscope[signing]'`; the missing-dependency hint matches.
- Vercel deployment protection is configured for previews only. Production
  remains public while preview deployments retain SSO protection.
- Vercel reported no runtime errors in the 24 hours preceding this check.
- The public site is a static product/demo surface, not a hosted Habitat
  database or an online agent control plane.
- The proof bundles are unsigned historical snapshots. Digest validity does
  not establish publisher identity or external truth.
- The proof page JavaScript was inspected, but was not executed in a real
  browser during this verification.

## Remaining validation

The release checks above do not establish complete product acceptance:

- Expand bridge fixtures for malformed and legacy/migrated databases. Current
  tests cover healthy, missing, incomplete-schema, and tampered-ledger states.
- Exercise read-only bridge access under concurrent load and verify no locks
  or writes across the full dashboard-generation flow. The current byte-level
  immutability test covers a healthy single-reader fixture.
- Exercise the generated dashboard end-to-end with no Habitat DB, healthy
  data, active signals, failed ledger integrity, and stored claims. Snapshot
  tests do not replace rendered-dashboard acceptance.
- Expand backup/restore coverage to migrated databases, existing destinations,
  and recovery after an interrupted backup. The current test covers a
  populated database and verifies recovered action-ledger integrity.
- Execute real-browser tests for proof-index rendering, proof-link navigation,
  keyboard interactions, and the responsive demo at narrow mobile widths. The
  mobile digest wrapping fix is source- and CI-verified, not visually verified
  in a real browser.
- AgentScope currently has no Android wrapper or PWA/service-worker assets.
  The Python CLI and generated HTML are local-first, but native Android
  installation and a browser-installable offline PWA are not implemented.
- Decide whether to keep Habitat as an independently installable CLI
  distribution or expose the runtime through a separately documented package
  boundary.

## Upstream provenance

- AgentScope source: `buttercode101/agentscope`, main baseline at integration branch creation.
- Habitat source: `buttercode101/Habitat`, `b823836d826a73f1edcea3ff0c5b7ba7399a6219`.
- Both upstream repositories are MIT licensed. Keep their notices and attribution when redistributing integrated code.
