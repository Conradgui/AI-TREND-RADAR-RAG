# Evidence: P1 Graph Runtime Hardening

Date: 2026-06-23

## What Changed

- Updated hybrid graph search to return citation-ready metadata.
- Graph results now include:
  - `content_type`
  - `date`
  - `source`
  - `title`
  - `url`
  - `citation_id`
  - `excerpt`
  - `category`
  - `score`
- Added a focused test proving graph results can become citation candidates.

## Validation

Focused tests:

```text
python3 -m unittest rag.tests.test_hybrid_retriever -v
Ran 2 tests
OK
```

Canonical check:

```text
pnpm rag:check:p0
Ran 127 tests
OK
```

## Runtime Status

Neo4j live runtime is now verified after Docker Desktop was installed and Docker Compose became available.

Docker verification:

```text
Docker version 29.5.3
Docker Compose version v5.1.4
```

Neo4j service:

```text
docker compose up -d
Container ai-trend-radar-rag-neo4j-1 Started
```

Driver verification:

```text
RETURN 1 AS ok
[{'ok': 1}]
```

Ingestion:

```text
.venv/bin/python -m rag.ingest
Found 14 digest dates
ChromaDB total: 1346 chunks
Done. Processed 14 dates.
```

Graph counts:

```text
Topic: 279
Entity: 268
Document: 22
Source: 19
DailyDigest: 14
MENTIONS: 945
APPEARED_ON: 812
DISCOVERED_VIA: 290
PART_OF: 22
```

Graph runtime smoke:

```text
.venv/bin/python -m rag.eval_graph_runtime_live
passed: true
citation_count: 8
graph_citation_count: 4
```

Output:

- `docs/rag-transformation/evals/graph-runtime-live-smoke-2026-06-23.json`

## Product Interpretation

This is a meaningful Graph RAG improvement, but not full Graph RAG completion.

Improved:

- graph retrieval results are now citation-ready;
- graph evidence is less likely to be discarded by citation building;
- hybrid retrieval has better metadata discipline.

Verified:

- live Neo4j ingestion;
- live Neo4j graph query;
- vector plus graph end-to-end runtime;
- service `/health` reports `retriever_mode: hybrid`;
- service `/chat` returns citations that include `graph-topic` citation IDs.

Still not claimed:

- richer graph path reasoning beyond entity-to-topic lookup.

## Bugs Found And Fixed

During live runtime verification, two Neo4j async wrapper issues were found and fixed:

1. `AsyncResult` must be consumed asynchronously.
2. Cypher params containing `query` must be passed as `parameters=params` to avoid collision with the `tx.run(query, ...)` argument.

## Residual Risks

- Current graph search is still shallow: entity full-text search to related topics.
- Graph paths are not yet used for multi-hop reasoning.
- Neo4j now runs locally through Docker; it consumes local machine resources until stopped.
