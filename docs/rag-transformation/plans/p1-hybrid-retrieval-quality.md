# P1 Hybrid Retrieval Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect query-understanding signals to retrieval so source/time intent can influence corpus recall instead of remaining debug-only metadata.

**Architecture:** Keep retrieval filtering deterministic and local. `rag.retrieval_planning` converts a `QueryPlan` plus latest corpus date into Chroma-compatible metadata filters; `HybridRetriever` accepts optional filters and passes them to vector retrieval; `chat_service` uses the filter when retrieving citations.

**Tech Stack:** Python standard library, `datetime`, `unittest`, existing vector store `where` support.

## Global Constraints

- Do not implement external web search.
- Do not change the original AI Trend Radar UI.
- Do not add new dependencies.
- Keep graph retrieval behavior backward-compatible.
- Use latest corpus date as the anchor for relative time windows when possible.

---

## Module Meaning

Hybrid Retrieval Quality means making retrieval obey the user's intent more precisely.

In this first slice, the system should use query-understanding signals to narrow vector recall by metadata:

- source intent, such as GitHub-specific questions
- relative time intent, such as past seven days

This does not solve all retrieval quality problems. It creates the first measurable bridge between intent parsing and retrieval behavior.

## Definition Of Done

Module: P1 Hybrid Retrieval Quality, Slice 1

Product behavior:
- A source-specific question can prefer source-filtered chunks.
- A last-seven-days question can produce a date-window filter anchored to the latest corpus date.
- Chat responses still include citations and query-understanding details.

Engineering behavior:
- `HybridRetriever.search()` accepts optional metadata filters.
- `retrieve_citations()` passes optional filters to retrievers.
- `chat_service` derives filters from `QueryPlan`.

Evidence behavior:
- Evidence records the filter contract, tests, and limitations.

Evaluation behavior:
- Unit tests cover source filter construction, date-window construction, retriever filter forwarding, and chat-service filter forwarding.
- `pnpm rag:check:p0` passes.

Non-goals:
- No graph query rewriting.
- No reranker.
- No live ChromaDB E2E benchmark.
- No web search tool execution.

Residual risks:
- Chroma filter semantics need live runtime verification with populated corpus.
- Graph results are not yet filtered by source/date.
- Source names are heuristic aliases and need corpus-driven normalization later.

## Files

- Create: `rag/retrieval_planning.py`
- Create: `rag/tests/test_retrieval_planning.py`
- Modify: `rag/retriever/hybrid.py`
- Create: `rag/tests/test_hybrid_retriever.py`
- Modify: `rag/citations.py`
- Modify: `rag/chat_service.py`
- Modify: `rag/tests/test_chat_service.py`
- Modify: `package.json`
- Create: `docs/rag-transformation/evidence/2026-06-22-hybrid-retrieval-quality.md`
- Create: `docs/rag-transformation/execution-log/2026-06-22-module-p1-hybrid-retrieval-quality.md`

## Task 1: Metadata Filter Planning

- [x] Add `build_metadata_filter(plan, latest_corpus_date)` tests for GitHub source, last-seven-days, combined filters, and no-filter fallback.
- [x] Implement filter construction without reading files or services.
- [x] Verify `python3 -m unittest rag.tests.test_retrieval_planning -v`.

## Task 2: Retriever Filter Forwarding

- [x] Add tests proving `HybridRetriever` passes `where` to vector search and keeps graph search backward-compatible.
- [x] Update `HybridRetriever.search(query, k=5, where=None)`.
- [x] Verify `python3 -m unittest rag.tests.test_hybrid_retriever -v`.

## Task 3: Chat/Citation Integration

- [x] Update `retrieve_citations(retriever, question, k=5, where=None)`.
- [x] Update `build_chat_response()` to build and pass metadata filters.
- [x] Extend chat-service tests to inspect passed filter.
- [x] Verify `python3 -m unittest rag.tests.test_chat_service rag.tests.test_citations rag.tests.test_retrieval_planning rag.tests.test_hybrid_retriever -v`.

## Task 4: Canonical Check And Evidence

- [x] Add new tests to `rag:test:p0`.
- [x] Add syntax check for `rag/retrieval_planning.py`.
- [x] Verify `pnpm rag:check:p0`.
- [x] Record evidence and execution log.
