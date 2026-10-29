# Hermes

Evidence-constrained multi-agent layer for the Madlanga Commission Evidence Room.

Hermes agents are deliberately **thin**: souls define behaviour and constraints; the evidence store remains the source of factual content.

## Structure
- `CONSTITUTION.md` — system-wide rules.
- `EVIDENCE_PROTOCOL.md` — retrieval and provenance lifecycle.
- `SOURCE_HIERARCHY.md` — source quality rules.
- `FINDING_GATE.md` — release gate for finding-like claims.
- `TOOL_CONTRACTS.md` — tool permissions and invariants.
- `ORCHESTRATION.md` — multi-agent workflow and response schema.
- `agents/*/soul.md` — role-specific behaviour.

## Implementation boundary
These files define the production contract. They do not pretend that an LLM runtime, complete transcript corpus, immutable object store or search index exists yet. Those components must be connected and tested before Hermes is presented as fully operational.
