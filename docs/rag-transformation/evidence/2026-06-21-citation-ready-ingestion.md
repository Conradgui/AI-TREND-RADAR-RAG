# Evidence: Citation-Ready Ingestion

## Date

2026-06-21

## Module

P0 / Module 3: Citation-Ready Ingestion

## What Was Verified

The ingestion layer now creates citation-ready metadata for:

- Markdown report chunks
- Topic candidate chunks from `topic-pool.json`
- Graph topic nodes and per-date appearance relationships
- Re-runnable vector ingestion for a single date

## Focused Tests

Command:

```bash
python3 -m unittest rag.tests.test_ingest rag.tests.test_graphrag_builder rag.tests.test_sync_corpus -v
```

Result:

```text
Ran 19 tests in 0.013s

OK
```

## Real Corpus Inspection

Command:

```bash
python3 - <<'PY'
import json
from pathlib import Path
from rag.ingest import normalize_topic_pool, build_topic_candidate_chunks
pool = normalize_topic_pool(json.loads(Path('digests/2026-06-21/topic-pool.json').read_text(encoding='utf-8')), '2026-06-21')
chunks, metadatas, ids = build_topic_candidate_chunks(pool, '2026-06-21')
print({'chunks': len(chunks), 'ids': ids[:2]})
print(json.dumps(metadatas[0], ensure_ascii=False, indent=2))
print(chunks[0][:500])
PY
```

Result summary:

```text
{'chunks': 52, 'ids': ['2026-06-21/topic-pool/0', '2026-06-21/topic-pool/1']}
```

First metadata sample:

```json
{
  "content_type": "topic_candidate",
  "date": "2026-06-21",
  "report_type": "topic-pool",
  "source": "Product Hunt",
  "title": "Claude Code Artifacts",
  "url": "https://www.producthunt.com/r/ZKUSXUIDPQQBDF?utm_campaign=producthunt-api&utm_medium=api-v2&utm_source=Application%3A+AI+Trend+Radar+%28ID%3A+285539%29",
  "score": 80,
  "action": "深挖",
  "category": "AI 产品与用户入口",
  "citation_id": "2026-06-21/topic-pool/0",
  "evidence": "来源：Product Hunt\n热度信号：451 / 14\n发布时间：2026-06-19\n关键词：Software Engineering, Developer Tools, Artificial Intelligence",
  "tags": "Software Engineering, Developer Tools, Artificial Intelligence"
}
```

## Interpretation

The local corpus can now produce retrievable units with enough metadata for downstream citation extraction. Module 4 can build `/chat` citations from retrieval results instead of inventing a separate citation source.

The vector ingestion path also replaces existing chunks for a date before writing new chunks, which reduces duplicate-ID failures during repeated local ingestion.

## Residual Risk

Vector replacement currently deletes a date's old chunks before adding new chunks. If ChromaDB fails after deletion, that date's vector data may be missing until ingestion is rerun. This should be hardened in a later ingestion reliability task, preferably with an explicit replace/upsert strategy and failure reporting.

## Reviewer Gate

A reviewer agent initially returned `Blocked` because graph evidence was stored on the `Topic` node and could be overwritten when the same topic appeared on multiple dates.

Fix applied:

- `APPEARED_ON` relationships now store per-date `summary`, `reason`, and `evidence` in addition to `score`, `action`, `source`, and `url`.
- Added a focused regression test for the same topic appearing on two dates with different evidence.

Post-fix test result:

```text
test_ingest_candidate_preserves_per_date_occurrence_evidence ... ok
Ran 19 tests in 0.013s
OK
```
