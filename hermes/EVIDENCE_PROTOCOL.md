# Hermes Evidence Protocol

## 1. Parse the request
Classify the request as procedural, factual, chronological, relational, comparative, documentary, or analytical.

## 2. Retrieve before reasoning
Search the controlled evidence store for the narrowest relevant source set. Expand only when evidence gaps or conflicts require it.

## 3. Build claim records
Every material proposition becomes a claim object with:
- `text`
- `classification`
- `source_ids`
- `transcript_location` when applicable
- `verification_state`
- `attribution` when a person/source is making the claim

## 4. Test provenance
The cited source must actually support the proposition. A source that merely mentions a person or topic is not sufficient evidence for a stronger conclusion.

## 5. Check contrary evidence
Before synthesis, search for credible evidence that narrows, contradicts or qualifies the proposition.

## 6. Separate observation from inference
Use explicit language such as `the record states`, `the witness testified`, `the Gazette provides`, or `this analysis infers`. Never blur these layers.

## 7. Gate the result
- `pass`: material claims have adequate evidence and no unresolved material conflict.
- `conditional`: answer is useful but has identified limitations or unresolved conflicts.
- `blocked`: evidence is insufficient, unavailable, or too contradictory for a reliable factual answer.

## 8. Preserve auditability
A reader must be able to travel from answer -> claim -> source -> exact location where available.
