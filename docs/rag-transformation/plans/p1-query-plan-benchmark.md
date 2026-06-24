# P1 Query Plan Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the five golden questions into a repeatable query-planning benchmark snapshot.

**Architecture:** Add a small CLI module that loads `golden-questions.json`, runs each question through query understanding and retrieval filter planning, and prints a JSON snapshot. This evaluates planning behavior without requiring ChromaDB, Neo4j, LLM keys, or web search.

**Tech Stack:** Python standard library, existing `rag.eval_golden`, `rag.query_understanding`, `rag.retrieval_planning`, `unittest`.

## Definition Of Done

Product behavior:
- Conrad can run one command to inspect how the system plans retrieval for each golden question.

Engineering behavior:
- A deterministic snapshot function exists and is covered by unit tests.
- The CLI can print JSON with question id, intent, answerability, top-k, web-need signal, retrieval query, latest corpus date, and metadata filter.

Evidence behavior:
- Evidence records a snapshot summary and residual risks.

Evaluation behavior:
- Focused tests and canonical RAG checks pass.

Non-goals:
- No live retrieval scoring.
- No LLM answer evaluation.
- No external web search.

## Files

- Create: `rag/eval_query_plans.py`
- Create: `rag/tests/test_eval_query_plans.py`
- Modify: `package.json`
- Create: `docs/rag-transformation/evidence/2026-06-22-query-plan-benchmark.md`
- Create: `docs/rag-transformation/execution-log/2026-06-22-module-p1-query-plan-benchmark.md`

## Tasks

- [x] Implement `build_query_plan_snapshot(questions, latest_corpus_date)`.
- [x] Add unit tests for snapshot shape and source/date filter on Q4.
- [x] Add `rag:eval:plans` command.
- [x] Add test to canonical RAG check.
- [x] Run focused tests and `pnpm rag:check:p0`.
- [x] Record evidence and execution log.
