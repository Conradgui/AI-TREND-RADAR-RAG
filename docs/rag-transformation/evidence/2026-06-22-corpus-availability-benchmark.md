# Evidence: P1 Corpus Availability Benchmark

## Date

2026-06-22

## Module

P1: Corpus Availability Benchmark

## Concept

This benchmark checks whether the local synced corpus likely contains evidence for each golden question before live semantic retrieval is tested.

It is intentionally keyword-based. It answers:

- Is there any local evidence signal?
- Is the signal weak, partial, or strong?
- Which dates and report files contain matching terms?

It does not prove answer quality or citation relevance.

## Product Behavior

Conrad can now run:

```bash
pnpm rag:eval:corpus
```

The command scans local `digests/` files and reports corpus coverage for the golden questions.

## Engineering Changes

Files:

- `rag/eval_corpus_availability.py`
- `rag/tests/test_eval_corpus_availability.py`
- `package.json`
- `docs/rag-transformation/plans/p1-corpus-availability-benchmark.md`

Key behavior:

- Loads local markdown and JSON digest files.
- Uses query-plan time windows to scope document scanning.
- Matches golden-question keywords.
- Classifies coverage as `none`, `weak`, `partial`, or `strong`.
- Treats weak one-keyword matches as local signals, but not sufficient corpus evidence.

## Snapshot Summary

Command:

```bash
pnpm rag:eval:corpus
```

Result summary:

```json
{
  "total": 5,
  "likely_has_corpus_evidence": 4,
  "likely_missing_corpus_evidence": 1,
  "needs_web_but_has_local_signals": 2
}
```

Per-question interpretation:

- Q1 RAG recent trends: `partial`, local evidence likely exists.
- Q2 RAG evolution and papers: `partial`, local signals exist but answerability still needs web for papers/articles.
- Q3 Claude updates: `strong`, local evidence likely exists.
- Q4 GitHub weekly topics: `strong`, local evidence likely exists.
- Q5 Google OKF / ALM Wiki: `weak`, only local Google signal exists; local corpus is not enough.

## Temporary Failure Caught

Initial implementation counted any keyword match as `likely_has_corpus_evidence`.

Problem:

- Q5 matched only the generic keyword `Google`.
- That was too optimistic and could encourage unsupported answers.

Fix:

- Added coverage levels.
- `likely_has_corpus_evidence` now requires `partial` or `strong`.
- `weak` remains visible as `has_local_signals`, but does not count as enough evidence.

## Verification

Focused command:

```bash
python3 -m unittest rag.tests.test_eval_corpus_availability -v
```

Result:

```text
Ran 5 tests in 0.003s

OK
```

Canonical RAG command:

```bash
pnpm rag:check:p0
```

Result:

```text
Ran 54 tests in 0.038s

OK
```

## Non-Goals

- No vector retrieval benchmark.
- No LLM generation benchmark.
- No web search.
- No original AI Trend Radar UI changes.

## Residual Risks

- Keyword matching can miss semantically relevant evidence with different wording.
- Keyword matching can still overcount terms in boilerplate text.
- Q2 and Q5 require future external source handling before high-quality final answers.
- A future benchmark should persist dated JSON output, not only print to stdout.

## Next Recommended Module

Next module should be a live local retrieval smoke benchmark after dependencies/runtime are available:

- ingest current corpus into ChromaDB
- run golden questions through retriever
- inspect top citations
- compare citation relevance against this corpus availability baseline
