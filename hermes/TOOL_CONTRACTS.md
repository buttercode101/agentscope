# Hermes Tool Contracts

## Evidence retrieval
**Purpose:** read indexed source snapshots, documents, transcripts and metadata.
**Write access:** none.
**Required output:** source ID, tier, publisher, title, canonical location, snapshot/version, and relevant excerpt/location.

## Source registration
**Purpose:** register a newly retrieved public source snapshot.
**Write access:** ingestion service only; agents cannot overwrite existing snapshots.
**Invariant:** snapshots are append-only and content-hashed.

## Search
Agents may search the controlled index. Search results are leads until the underlying source is opened and verified.

## Internet research
Only the Research/Verification roles may request external discovery, through a controlled retrieval interface. External material must be registered and tiered before becoming evidence.

## Graph access
Network and related agents may read entity/relationship edges with source IDs. They cannot create an unsupported relationship or infer wrongdoing from graph proximity.

## Findings / decisions
No agent has permission to publish an official finding, alter the Commission record, or mark an allegation as fact. Human/official decision state is read-only input.

## Browser/UI
Browser credentials and privileged API keys never enter the client. UI agents receive redacted, source-backed data only.
