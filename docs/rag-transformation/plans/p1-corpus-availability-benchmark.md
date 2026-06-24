# P1 Corpus Availability Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight benchmark that checks whether the local synced corpus likely contains evidence for each golden question before live retrieval is tested.

**Architecture:** Scan local `digests/` files using golden-question keywords and query-plan time windows. This is a cheap corpus coverage check, not a semantic retrieval benchmark.

**Tech Stack:** Python standard library, `pathlib`, `datetime`, existing golden-question and query-planning modules, `unittest`.

## Definition Of Done

Product behavior:
- Conrad can see which golden questions likely have local corpus evidence and which may require more ingestion or future web search.

Engineering behavior:
- A deterministic corpus availability snapshot function and CLI exist.
- Tests cover keyword matching, date-window filtering, and actual golden-question execution.

Evidence behavior:
- Evidence records benchmark summary and limitations.

Evaluation behavior:
- Focused tests and canonical RAG checks pass.

Non-goals:
- No vector search.
- No LLM answer quality grading.
- No external web search.

## Files

- Create: `rag/eval_corpus_availability.py`
- Create: `rag/tests/test_eval_corpus_availability.py`
- Modify: `package.json`
- Create: `docs/rag-transformation/evidence/2026-06-22-corpus-availability-benchmark.md`
- Create: `docs/rag-transformation/execution-log/2026-06-22-module-p1-corpus-availability-benchmark.md`

## Tasks

- [x] Implement corpus document loading and keyword matching.
- [x] Implement `build_corpus_availability_snapshot()`.
- [x] Add `rag:eval:corpus` command.
- [x] Add focused tests and canonical check coverage.
- [x] Run focused tests, `pnpm rag:eval:corpus`, and `pnpm rag:check:p0`.
- [x] Record evidence and execution log.
