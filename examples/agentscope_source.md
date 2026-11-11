# agentscope ↔ Habitat bridge notes

agentscope is the scan-first supervision surface. Habitat is the claim/evidence layer.
Together they answer two different questions on the same morning scan:

- agentscope: **Is anything off?**
- Habitat: **Does the record support the claim?**

## Minimal integration path (no product pivot)

1. When Hermes (or any runner) records a consequential action, also write a Habitat trusted action + claim via `examples/hermes_bridge.py` (or the equivalent event ingest).
2. Export the portable `proof-*.json` and optional tip file next to the project or into a known proofs directory.
3. Point agentscope at that directory (or at Habitat’s SQLite claims table) as an optional read-only source:
   - open / failed claims
   - recent proof digests
   - “needs attention” items that already carry a claim ID

## Suggested agentscope config addition

```json
{
  "sources": {
    "habitat_proofs_glob": "**/proof-*.json",
    "habitat_db": null
  }
}
```

agentscope remains read-only. Habitat remains the writer of evidence. No shared control plane is required.

## Why this is 10× without pivoting

- Supervision and accountability become one daily surface instead of two tools you have to remember.
- Every anomaly agentscope already detects (drift, auth, silent skip) can be bound to a Habitat claim and, when appropriate, a negative proof.
- Portable proofs stay independently verifiable; agentscope only surfaces them.
