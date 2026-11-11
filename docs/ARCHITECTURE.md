# AgentScope architecture

## Product boundary

AgentScope is the read-only supervision surface for an AI-agent crew. Habitat is the local evidence and verification runtime. The integration is intentionally one-way at the dashboard boundary: AgentScope reads Habitat state and renders a bounded summary; it does not run jobs or mutate evidence.

## Runtime flow

```text
Hermes / scheduled agent sources
        |
        +----> AgentScope collectors ----> generated local HTML dashboard
        |
        +----> Habitat signed event intake
                    |
                    v
             Habitat SQLite store
             - jobs and runtime signals
             - append-only action ledger
             - correlated claims
             - evidence policy decisions
                    |
                    v
             Habitat verification + proof
                    |
                    v
       AgentScope read-only SQLite bridge
                    |
                    v
       Dashboard evidence/health summary
```

## Responsibilities

### AgentScope

- Read local cron definitions, execution history, sessions, and optional MCP JSONL.
- Detect operational anomalies and missing telemetry.
- Generate a self-contained, read-only HTML dashboard.
- Optionally read a Habitat SQLite database in SQLite `mode=ro`.
- Display Habitat runtime state, active signals, claim verdict counts, and action-ledger integrity.
- Treat unavailable evidence as UNKNOWN.

### Habitat

- Ingest structured agent events and preserve action provenance.
- Maintain local job, signal, action, agent, and claim records.
- Correlate claims to exact runs/actions.
- Verify claims against trusted ledger evidence or explicit external evidence adapters.
- Apply policy gates that can downgrade but never upgrade unsupported claims.
- Export portable proof bundles and verify their structure, content integrity, and signatures.

## Integration contract

The bridge in `agentscope_habitat.py` is a read-only projection, not a second implementation of Habitat's domain model. It queries a bounded set of tables and verifies the action hash chain using Habitat's canonical hash routine. It does not re-run migrations, create claims, acknowledge signals, execute jobs, or rewrite stored verdicts.

A stored claim verdict is displayed as stored state. The bridge does not label it as freshly re-verified.

## Deployment model

The default AgentScope product site is a static landing/demo surface. Operational dashboards are generated locally from configured sources. Habitat's local runtime can be operated locally or through its separately configured authenticated API. Do not publish a local operational database or private agent dashboard as a public demo.

## Security invariants

1. The default AgentScope path remains local and self-contained.
2. Habitat database access from AgentScope is read-only.
3. Missing telemetry is UNKNOWN, not healthy.
4. Ledger integrity failure is a failure, not a warning hidden by acknowledgement.
5. Proof content integrity, signature validity, publisher trust, and external truth remain distinct.
6. The integration must not introduce an agent execution/control surface into AgentScope.
