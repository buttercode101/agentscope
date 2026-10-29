# Evidence data model

The runtime uses SQLite for the local production foundation. The same logical model can move to Postgres without changing the evidence contract.

## Core objects

- **source** — canonical publisher, URL, tier and publication/retrieval metadata.
- **snapshot** — immutable byte capture identified by SHA-256. A source can have many snapshots over time.
- **claim** — a bounded statement with an explicit classification and verification state.
- **claim_sources** — many-to-many provenance mapping; a claim cannot pass the gate without at least one source.
- **hearing** — sitting-day index. `index_only` means the day is known to exist in the indexed sequence but detailed material has not been ingested into this build. `detailed` means a source-backed hearing record is present.
- **audit** — append-only operational record of ingestion actions.

## Integrity invariants

1. Claims never store source prose as if it were a source record.
2. A claim must reference one or more source IDs before it can pass verification.
3. A source snapshot is content-addressed by SHA-256.
4. Re-fetching changed source content creates a new snapshot; old snapshots are retained.
5. Missing hearing detail is represented explicitly rather than synthesized.
6. Agent output is not persisted as factual evidence unless a human/controlled ingestion process promotes it into a sourced claim.
