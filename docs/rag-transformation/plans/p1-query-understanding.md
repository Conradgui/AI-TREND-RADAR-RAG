# P1 Query Understanding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small, deterministic query-understanding layer before retrieval so AI Trend Radar RAG can explain and control what it is trying to retrieve.

**Architecture:** The module should stay framework-independent and avoid LangChain/LangGraph coupling. `rag.query_understanding` produces a typed `QueryPlan`; `rag.chat_service` uses the plan to choose the retriever query and top-k, then returns the plan for debugging and future benchmark analysis.

**Tech Stack:** Python standard library, `dataclasses`, `unittest`, existing `rag.chat_service`, existing citation path.

## Global Constraints

- Do not change the original AI Trend Radar UI.
- Do not add LangChain, LangGraph, or large framework dependencies in this module.
- Do not implement live web search in this module.
- Keep the change deterministic and testable without Neo4j, ChromaDB, or a real LLM provider.
- Record module evidence and execution log under `docs/rag-transformation/`.

---

## Module Meaning

Query Understanding means turning a user's natural-language question into a small execution plan:

- what topic or entity seems important
- whether the question is asking for recent information, a timeline, source-specific discovery, or comparison
- whether the internal corpus is enough or future web search is likely needed
- what query string should be sent to the retriever
- how many candidates should be retrieved

Its role in the system is to reduce blind embedding recall. In business terms, this improves answer quality, cost control, and debuggability because we can inspect the system's intent before trusting the final answer.

## Definition Of Done

Module: P1 Query Understanding

Product behavior:
- `/chat` responses can include a compact `query_understanding` object explaining intent, time window, sources, web-need signal, retrieval query, and top-k.

Engineering behavior:
- A framework-independent `rag.query_understanding` module exists.
- `rag.chat_service.build_chat_response()` uses the query plan for retrieval.
- Existing P0 citation behavior still passes.

Evidence behavior:
- The module records what changed, what was verified, and known limitations.

Evaluation behavior:
- Unit tests cover the five seed golden-question patterns at a routing/plan level.
- `pnpm rag:check:p0` still passes after the change.

Non-goals:
- No external web search.
- No metadata filtering inside ChromaDB or Neo4j yet.
- No LLM-based query rewriting.
- No original UI integration.

Residual risks:
- Heuristic parsing is intentionally simple and will need benchmark-driven refinement.
- Query plans do not guarantee retrieval relevance until P1 Hybrid Retrieval Quality.

## Files

- Create: `rag/query_understanding.py`
- Create: `rag/tests/test_query_understanding.py`
- Modify: `rag/chat_service.py`
- Modify: `rag/server.py`
- Modify: `package.json`
- Create: `docs/rag-transformation/evidence/2026-06-22-query-understanding.md`
- Create: `docs/rag-transformation/execution-log/2026-06-22-module-p1-query-understanding.md`

## Task 1: Query Plan Model And Heuristics

**Interfaces:**
- Produces: `analyze_query(question: str) -> QueryPlan`
- Produces: `QueryPlan.to_dict() -> dict`

- [x] Write unit tests for recent RAG, Claude update, GitHub weekly, RAG timeline, and Google OKF/ALM comparison patterns.
- [x] Implement `QueryPlan` and deterministic heuristics.
- [x] Verify `python3 -m unittest rag.tests.test_query_understanding -v`.

## Task 2: Chat Service Integration

**Interfaces:**
- Consumes: `analyze_query(question: str) -> QueryPlan`
- Modifies: `build_chat_response(agent, retriever, message, history) -> dict`

- [x] Extend chat-service tests to prove retrieval uses `query_plan.retrieval_query` and `query_plan.top_k`.
- [x] Include `query_understanding` in both evidence-backed and evidence-insufficient responses.
- [x] Verify `python3 -m unittest rag.tests.test_chat_service rag.tests.test_citations rag.tests.test_query_understanding -v`.

## Task 3: API Contract And Canonical Test Command

**Interfaces:**
- Consumes: chat response dictionary field `query_understanding`
- Modifies: `ChatResponse` schema in `rag/server.py`
- Modifies: `package.json` script `rag:test:p0`

- [x] Add `query_understanding: dict = Field(default_factory=dict)` to the API response model.
- [x] Add `rag.tests.test_query_understanding` to `rag:test:p0`.
- [x] Verify `pnpm rag:check:p0`.

## Task 4: Evidence And Execution Log

- [x] Record the concept, changed files, tests, limitations, and next module recommendation in evidence.
- [x] Record the execution loop in execution log.
- [x] Run a final focused status check.
