# Evidence: P1 Query Understanding

## Date

2026-06-22

## Module

P1: Retrieval Quality + Agent Control / Module 1: Query Understanding

## Concept

Query Understanding turns a natural-language user question into a compact retrieval plan before search.

In this module, the plan records:

- inferred intent
- important topics and entities
- source hints
- time-window hints
- whether future web search is likely needed
- rewritten retrieval query
- retrieval top-k

This matters because pure embedding recall can retrieve plausible but wrong context. A query plan gives the system and reviewer a way to inspect what the RAG system believed it was trying to find.

## Product Behavior

`/chat` can now return a `query_understanding` object alongside `answer` and `citations`.

When evidence is insufficient, the system still returns the query-understanding object, which helps diagnose whether the issue is query interpretation, corpus coverage, or retrieval quality.

## Engineering Changes

Files:

- `rag/query_understanding.py`
- `rag/tests/test_query_understanding.py`
- `rag/chat_service.py`
- `rag/tests/test_chat_service.py`
- `rag/server.py`
- `package.json`
- `docs/rag-transformation/plans/p1-query-understanding.md`

Key behavior:

- `analyze_query(question)` returns a typed `QueryPlan`.
- `build_chat_response()` uses `query_plan.retrieval_query` and `query_plan.top_k` when calling the retriever.
- `ChatResponse` includes `query_understanding`.
- The canonical RAG check now includes query-understanding tests and syntax compilation.

## Verification

Focused module command:

```bash
python3 -m unittest rag.tests.test_query_understanding -v
```

Result:

```text
Ran 5 tests in 0.000s

OK
```

Integration command:

```bash
python3 -m unittest rag.tests.test_chat_service rag.tests.test_citations rag.tests.test_query_understanding -v
```

Result:

```text
Ran 14 tests in 0.040s

OK
```

Canonical RAG command:

```bash
pnpm rag:check:p0
```

Result:

```text
Ran 38 tests in 0.018s

OK
```

Final focused status check:

```bash
python3 -m unittest rag.tests.test_query_understanding rag.tests.test_chat_service -v
```

Result:

```text
Ran 7 tests in 0.018s

OK
```

## Temporary Failure Caught

The first chat-service integration test run failed because the fake retriever did not record the `k` argument.

Fix:

- Updated the test fake to store `self.k`.

Why this mattered:

- The test now actually verifies that the query plan controls retrieval depth.

## Non-Goals

- No external web search was implemented.
- No metadata filtering was added to vector or graph retrieval.
- No LangChain or LangGraph dependency was introduced.
- No original AI Trend Radar UI behavior was changed.

## Residual Risks

- The first parser is heuristic, not LLM-based and not benchmark-trained.
- It can identify time/source intent, but current retrievers do not yet apply metadata filters.
- `needs_web_search` is only a signal; the web tool contract remains future work.
- The script name `rag:test:p0` now includes an early P1 test, so a future cleanup should rename it to `rag:test:core` or split phase commands.
- The reviewer agent for this module timed out twice and did not return a verdict. This does not block the module because focused tests and self-review passed, but the next module should use a narrower reviewer prompt or rely on a targeted local checklist.

## Next Recommended Module

P1 Module 2 should be Hybrid Retrieval Quality:

- pass time/source hints into retrieval
- improve candidate ranking
- measure citation relevance against golden questions
- preserve current evidence-insufficient behavior when recall is weak
