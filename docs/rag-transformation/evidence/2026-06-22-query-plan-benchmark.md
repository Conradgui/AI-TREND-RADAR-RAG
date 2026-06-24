# Evidence: P1 Query Plan Benchmark

## Date

2026-06-22

## Module

P1: Query Plan Benchmark Snapshot

## Concept

This benchmark evaluates how the system plans retrieval before it evaluates generated answers.

The goal is to catch planning drift early:

- wrong intent
- wrong web-search signal
- missing source constraint
- missing time-window constraint
- unstable retrieval query

## Product Behavior

Conrad can now run:

```bash
pnpm rag:eval:plans
```

The command prints a JSON snapshot for the five golden questions.

## Engineering Changes

Files:

- `rag/eval_query_plans.py`
- `rag/tests/test_eval_query_plans.py`
- `package.json`
- `docs/rag-transformation/plans/p1-query-plan-benchmark.md`

Key behavior:

- Loads `docs/rag-transformation/evals/golden-questions.json`.
- Validates the dataset using existing golden-question validation.
- Runs each question through `analyze_query()`.
- Builds metadata filters with `build_metadata_filter()`.
- Prints summary plus per-question rows.

## Snapshot Summary

Command:

```bash
pnpm rag:eval:plans
```

Result summary:

```json
{
  "total": 5,
  "needs_web_search": 2,
  "with_metadata_filter": 1,
  "intents": {
    "learning_map": 1,
    "product_update": 1,
    "recent_trend": 1,
    "source_specific_discovery": 1,
    "technical_comparison": 1
  }
}
```

Important row:

```json
{
  "id": "Q4",
  "planned_intent": "source_specific_discovery",
  "planned_sources": ["GitHub"],
  "planned_time_window": {
    "label": "last_7_days",
    "days": 7,
    "requires_date_filter": true
  },
  "metadata_filter": {
    "$and": [
      { "source": { "$in": ["GitHub", "GitHub Trending", "GitHub Search"] } },
      { "date": { "$gte": "2026-06-15", "$lte": "2026-06-21" } }
    ]
  }
}
```

## Verification

Focused command:

```bash
python3 -m unittest rag.tests.test_eval_query_plans -v
```

Result:

```text
Ran 3 tests in 0.001s

OK
```

Canonical RAG command:

```bash
pnpm rag:check:p0
```

Result:

```text
Ran 49 tests in 0.025s

OK
```

## Non-Goals

- No live retriever relevance scoring.
- No LLM answer grading.
- No web search execution.
- No ChromaDB or Neo4j service startup.

## Residual Risks

- Query-plan quality is only a proxy; it does not prove retrieved chunks are relevant.
- The golden questions still need Conrad's product review for final good-answer criteria.
- Snapshot output is printed to stdout, not yet persisted as a dated artifact file.

## Next Recommended Module

Next module should run a local corpus availability benchmark:

- inspect whether the synced corpus contains likely evidence for each golden question
- report which questions are answerable from corpus before attempting live vector retrieval
- identify gaps that require new ingestion, source normalization, or future web search
