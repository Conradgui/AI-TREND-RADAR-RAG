# P1 Runtime Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move from focused local tests to a real local runtime readiness baseline for AI Trend Radar RAG.

**Architecture:** Use the project's existing Python RAG stack instead of hand-rolling replacements: FastAPI, ChromaDB, Neo4j, LangChain, LangGraph, and DeepSeek through the OpenAI-compatible LangChain adapter. Start with local dependency and vector-store readiness; record Neo4j as blocked when Docker is unavailable.

**Tech Stack:** Python 3.12 bundled by Codex, project `.venv`, `rag/requirements.txt`, ChromaDB, DeepSeek, optional Neo4j.

## Global Constraints

- Do not commit or print real API keys.
- Do not install system-level tools such as Docker Desktop or Homebrew packages without Conrad's explicit confirmation.
- Prefer existing project components over custom implementations.
- Record evidence and residual blockers.

---

## Definition Of Done

Product behavior:
- Conrad has a project-local `.env` template ready for DeepSeek.
- The RAG Python runtime dependencies are installed into a project-local `.venv`.
- The project can run focused RAG checks using the local runtime.
- If Neo4j cannot start, the blocker is explicit and documented.

Engineering behavior:
- `.env` exists but contains no real key.
- `.venv` exists and can import RAG runtime dependencies.
- Chroma/vector-store readiness can be tested without Neo4j.
- No system-level install is performed.

Evidence behavior:
- Evidence records commands, pass/fail results, and required user action.

Evaluation behavior:
- `pnpm rag:check:p0` continues to pass.
- Additional runtime import checks pass where possible.

Non-goals:
- No original AI Trend Radar UI integration.
- No production deployment.
- No system Docker installation.
- No secret management migration beyond project-local `.env`.

Residual risks:
- Full `/chat` E2E requires a real API key and Neo4j availability.
- Chroma default embedding may require dependency/runtime checks after installation.

## Tasks

- [x] Create or refresh `.env` template for DeepSeek without committing secrets.
- [x] Create project-local `.venv` with bundled Python 3.12.
- [x] Install `rag/requirements.txt` into `.venv`.
- [x] Verify imports for FastAPI, ChromaDB, Neo4j, LangChain, LangGraph, and dotenv.
- [x] Check whether Neo4j can be started; Docker is unavailable in the current shell, so record blocker.
- [x] Run focused RAG check using the project state.
- [x] Record evidence and execution log.
