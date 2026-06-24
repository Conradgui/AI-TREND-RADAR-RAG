# Evidence: P1 Hybrid Retrieval Quality Slice 1

## Date

2026-06-22

## Module

P1: Retrieval Quality + Agent Control / Module 2: Hybrid Retrieval Quality, Slice 1

## Concept

Hybrid Retrieval Quality is about making retrieval obey user intent instead of sending every question through the same generic similarity search.

This slice connects query understanding to metadata filtering:

- Source-specific questions can create a source filter.
- Last-seven-days questions can create a date-window filter.
- Combined questions, such as GitHub over the past week, create combined filters.

## Product Behavior

For a question like:

```text
过去一周 GitHub 热榜上有什么值得关注的选题？
```

The system can now derive:

```json
{
  "$and": [
    { "source": { "$in": ["GitHub", "GitHub Trending", "GitHub Search"] } },
    { "date": { "$gte": "2026-06-15", "$lte": "2026-06-21" } }
  ]
}
```

The date window is anchored to the latest local corpus date, not the machine clock.

## Engineering Changes

Files:

- `rag/retrieval_planning.py`
- `rag/tests/test_retrieval_planning.py`
- `rag/retriever/hybrid.py`
- `rag/tests/test_hybrid_retriever.py`
- `rag/citations.py`
- `rag/chat_service.py`
- `rag/tests/test_chat_service.py`
- `rag/tests/test_citations.py`
- `package.json`
- `docs/rag-transformation/plans/p1-hybrid-retrieval-quality.md`

Key behavior:

- `build_metadata_filter(plan, latest_corpus_date)` builds Chroma-compatible filters.
- `load_latest_corpus_date()` reads the first date from `manifest.json` when available.
- `HybridRetriever.search(query, k, where)` forwards `where` to vector search.
- `retrieve_citations(..., where)` forwards filters to the retriever.
- `build_chat_response()` attaches `metadata_filter` and `latest_corpus_date` to `query_understanding`.

## Verification

Focused filter planning:

```bash
python3 -m unittest rag.tests.test_retrieval_planning -v
```

Result:

```text
Ran 5 tests in 0.001s

OK
```

Focused retriever forwarding:

```bash
python3 -m unittest rag.tests.test_hybrid_retriever -v
```

Result:

```text
Ran 1 test in 0.006s

OK
```

Focused integration:

```bash
python3 -m unittest rag.tests.test_chat_service rag.tests.test_citations rag.tests.test_retrieval_planning rag.tests.test_hybrid_retriever -v
```

Result:

```text
Ran 17 tests in 0.047s

OK
```

Canonical RAG command:

```bash
pnpm rag:check:p0
```

Result:

```text
Ran 46 tests in 0.034s

OK
```

## Temporary Failure Caught

The first integration run failed because test fake retrievers did not accept or record the new `where` parameter.

Fix:

- Updated test retrievers to mirror the real retriever interface.

Why this mattered:

- The test now proves filters are actually forwarded through chat/citation/retriever layers.

## Non-Goals

- No live ChromaDB runtime was started.
- No Neo4j graph filtering was added.
- No reranker was added.
- No external web search was implemented.
- No original AI Trend Radar UI behavior was changed.

## Residual Risks

- Chroma metadata filter semantics still need live verification with a populated collection.
- Graph retrieval still ignores source/date filters, so fused results can include graph candidates outside the vector filter.
- Source aliases are hand-coded and should later be normalized from corpus source taxonomy.
- The command name `rag:test:p0` now includes P1 checks and should later be renamed to `rag:test:core`.

## Next Recommended Module

P1 should next add a lightweight retrieval benchmark snapshot:

- run the five golden questions through query planning
- inspect planned filters and citation availability
- record failures as benchmark cases before adding reranking or more agent tools
