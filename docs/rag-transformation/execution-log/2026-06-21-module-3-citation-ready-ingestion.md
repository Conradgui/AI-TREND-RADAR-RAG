# Execution Log: Module 3 Citation-Ready Ingestion

## Date

2026-06-21

## Action

Added citation-ready ingestion metadata for report chunks, topic candidate chunks, graph topic nodes, and per-date graph appearance relationships.

## Why

The RAG system cannot be trusted if retrieved text has no source, date, title, URL, or evidence trail. This module turns ingestion output into citation-capable retrieval units so later chat responses can return grounded citations.

## Files Modified

- `rag/ingest.py`
- `rag/graphrag/builder.py`
- `rag/tests/test_ingest.py`
- `rag/tests/test_graphrag_builder.py`

## Files Created

- `docs/rag-transformation/evidence/2026-06-21-citation-ready-ingestion.md`
- `docs/rag-transformation/execution-log/2026-06-21-module-3-citation-ready-ingestion.md`

## Concept

Citation-ready ingestion means every retrievable unit carries enough metadata to prove where it came from.

## Role In The System

This bridges retrieval and user trust. Without it, the model may answer from relevant text but cannot show reliable citations. With it, Module 4 can expose citations in `/chat`.

## Plain-Language Principle

When text enters the retrieval layer, it should bring its label with it: date, source, title, URL, score, category, and evidence. The answer layer can then show that label back to the user.

## Business Questions A Reviewer Would Ask

- Can a user tell which source supported an answer?
- Can the system distinguish report text from topic-pool candidates?
- Does structured topic evidence become searchable, or only graph data?
- Does graph ingestion preserve enough fields for trend explanations?
- Are metadata values safe for ChromaDB storage?

## Failure Modes Addressed

- Report chunks only had anonymous `date` and `source`.
- Topic candidates were not added to vector retrieval.
- Graph topics dropped summary, URL, source, reason, and evidence.
- Builder imports required Neo4j during lightweight tests.
- `datetime.timezone` usage would fail at runtime.
- Re-running ingestion for the same date could hit duplicate vector IDs.
- Reviewer found that same-title topics across dates could overwrite node-level evidence. This was fixed by preserving citation fields on `APPEARED_ON` relationships.

## Reviewer Gate

Initial verdict: `Blocked`.

Blocking issue:

- Per-date graph evidence could be lost when the same topic appeared on multiple dates.

Resolution:

- Added `summary`, `reason`, and `evidence` to the `APPEARED_ON` relationship.
- Added a regression test for same-topic, different-date evidence retention.

Post-fix result:

```bash
python3 -m unittest rag.tests.test_ingest rag.tests.test_graphrag_builder rag.tests.test_sync_corpus -v
```

```text
Ran 19 tests in 0.013s

OK
```

## Verification

See `docs/rag-transformation/evidence/2026-06-21-citation-ready-ingestion.md`.

## Next Step

Move to Module 4: Chat Citations. The next module should read citation-ready retrieval metadata and return citations from `/chat`.

## Follow-Up Risk

Vector date replacement should be hardened later. Current behavior reduces duplicate-ID failures but is not fully transactional.
