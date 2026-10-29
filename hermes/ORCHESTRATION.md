# Hermes Orchestration Specification

## Pipeline
`request -> classify -> retrieve -> normalize -> independent analysis -> contradiction pass -> red-team -> verification -> finding gate -> synthesis -> provenance`

## Agent order
1. **Evidence** locates and normalizes source material.
2. **Docket** establishes procedural/hearing context.
3. **Chronology** checks dates and sequence.
4. **Network** maps only sourced relationships when relevant.
5. **Contradiction** searches for incompatible evidence.
6. **Research** fills documented evidence gaps using controlled sources.
7. **Red Team** attempts to falsify or weaken the proposed synthesis.
8. **Verification** checks citations, classifications and source support.
9. **Chair** performs procedural/scope synthesis without issuing factual findings.

Agents may run in parallel after retrieval where their tasks are independent. Verification and the finding gate occur after the analytical passes.

## Final response schema
```json
{
  "answer": "...",
  "claims": [{
    "text": "...",
    "classification": "FACT|MANDATE|RECORD|TESTIMONY|ALLEGATION|ANALYSIS|INFERENCE",
    "source_ids": ["..."],
    "transcript_location": null,
    "verification_state": "verified|partial|conflicted|unverified"
  }],
  "conflicts": [],
  "evidence_gaps": [],
  "questions_for_human": [],
  "gate": {"status":"pass|conditional|blocked", "reasons":[]}
}
```

## Failure behaviour
- Retrieval failure: do not answer from memory; return `blocked` with the retrieval gap.
- Citation mismatch: reject the claim and retry retrieval.
- Material conflict: preserve both and return at least `conditional` until resolved or explicitly framed as unresolved.
- Missing primary source: identify the best available lower-tier source and label its limitation.
