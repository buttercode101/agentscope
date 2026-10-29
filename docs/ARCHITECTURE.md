# Full Commission architecture

Browser UI -> Commission API -> Evidence service -> Immutable source store -> Search index / graph -> Hermes orchestration.

### Evidence object
`id, type, statement, classification, source_ids, transcript_location, document_hash, created_at, updated_at, verification_state`

### Source object
`id, tier, publisher, title, canonical_url, retrieved_at, content_hash, publication_date`

### Transcript object
`hearing_id, day, date, speaker, role, start_offset, end_offset, text, source_id`

### Relationship object
`subject_id, predicate, object_id, source_ids, confidence_reason`

The production version should use append-only source snapshots so later website changes cannot silently rewrite the historical record. Derived claims should point to exact source snapshots and transcript ranges.
