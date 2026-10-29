# Operations

## Local runtime

```bash
python3 run.py
```

The Evidence Room is available at `http://127.0.0.1:4173/public/` and the API under `/api/`.

## Controlled ingestion

Source ingestion is deliberately a CLI operation rather than a public browser mutation:

```bash
python3 api/ingest.py s1
```

The command fetches the registered canonical URL, calculates SHA-256, writes an immutable snapshot under `data/snapshots/`, and records an audit event. If the runtime has no network access, ingestion fails rather than fabricating a snapshot.

## API

- `GET /api/status` — current build status and corpus counts.
- `GET /api/claims` — claims with source IDs.
- `GET /api/sources` — registered sources.
- `GET /api/hearings` — 178 indexed sitting days.
- `GET /api/hearings?detailed=1` — only source-backed detailed records.
- `GET /api/search?q=...` — deterministic search over the seeded claims/source register.
- `GET /api/gate` — deterministic source-coverage gate for the current claim set.

## Production deployment boundary

The static browser must never receive privileged ingestion credentials. A hosted deployment should split the public read API from an authenticated ingestion/admin service, use object storage for immutable snapshots, Postgres for metadata, and a proper search/index layer for transcripts and exhibits.
