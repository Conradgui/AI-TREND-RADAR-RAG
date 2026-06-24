# P0 Fresh Corpus Sync + RAG Grounding Plan

> For implementation workers: execute this plan module by module. Each module must leave an execution note under `docs/rag-transformation/execution-log/` and evidence under `docs/rag-transformation/evidence/` when verification produces observable output.

**Goal:** Sync fresh AI Trend Radar Pages corpus into AI Trend Radar RAG, ingest it with citation-ready metadata, and validate it with the first five golden questions.

**Architecture:** AI Trend Radar remains the upstream data producer. AI Trend Radar RAG consumes the upstream GitHub Pages artifacts, stores local copies for repeatable development, ingests markdown and topic metadata into retrieval stores, and returns grounded answers with citations.

**Tech Stack:** TypeScript data artifacts, Python RAG ingestion, Neo4j, ChromaDB, FastAPI, local markdown/json evaluation files.

## Global Constraints

- Communicate in Chinese when explaining work to Conrad.
- Explain concepts before implementation.
- Do not install dependencies without listing the install action first.
- Do not move or delete files without listing the affected paths first.
- Keep changes scoped to the current module.
- Prefer simple local files for P0 evaluation and evidence.
- Do not fix the original AI Trend Radar web UI Agent in P0.

---

## Module 0: Project Record Folder

**Files:**
- Create: `docs/rag-transformation/README.md`
- Create: `docs/rag-transformation/roadmap.md`
- Create: `docs/rag-transformation/plans/p0-fresh-corpus-sync.md`
- Create: `docs/rag-transformation/decisions/0001-project-boundary.md`
- Create: `docs/rag-transformation/evals/golden-questions.md`
- Create: `docs/rag-transformation/evidence/README.md`
- Create: `docs/rag-transformation/execution-log/2026-06-21-module-0-project-record.md`

**Concept:** This module creates the durable project management folder.

**Role:** It makes future execution auditable and gives every module a place to record decisions and evidence.

**Verification:** `find docs/rag-transformation -maxdepth 3 -type f | sort` lists the project record files.

## Module 1: Fresh Corpus Sync Design

**Files:**
- Create: `scripts/sync-pages-corpus.ts` or `rag/sync_corpus.py`
- Test: matching unit tests for URL construction and manifest parsing

**Concept:** A corpus sync script downloads already-published AI Trend Radar artifacts instead of rerunning the upstream scraping pipeline.

**Role:** It solves stale RAG data without requiring upstream collection tokens such as Product Hunt, Gitee, or notification secrets.

**Implementation direction:** Use the upstream Pages base URL `https://conradgui.github.io/AI-TREND-RADAR`, read `manifest.json`, then copy recent `digests/YYYY-MM-DD/ai-topic-radar.md`, `digests/YYYY-MM-DD/topic-pool.json`, and `digests/search-index.json` into the local project.

**Verification:** Running the sync command updates local corpus dates to the latest upstream date and writes a summary to `docs/rag-transformation/evidence/`.

## Module 2: Topic Pool Compatibility

**Files:**
- Modify: `rag/ingest.py`
- Modify or create: focused tests under `rag/tests/`

**Concept:** Topic pool compatibility means the RAG code reads the real upstream JSON structure.

**Role:** The current public corpus uses `candidates`; code that expects only `topics` silently loses structured evidence.

**Implementation direction:** Add a small loader function that returns candidates from `candidates` first, falls back to `topics`, and normalizes date onto each candidate.

**Verification:** Tests cover `candidates`, `topics`, empty pools, and malformed optional fields.

## Module 3: Citation-Ready Ingestion

**Files:**
- Modify: `rag/ingest.py`
- Modify: `rag/graphrag/builder.py`
- Modify: `rag/retriever/vector_store.py` only if metadata handling requires it

**Concept:** Citation-ready ingestion means every retrievable unit carries enough metadata to prove where it came from.

**Role:** It converts RAG from anonymous search into evidence-backed research.

**Implementation direction:** Store date, report type, source, title, URL, score, action, category, and evidence when available. Markdown chunks should keep report-level metadata; topic candidates should keep topic-level metadata.

**Verification:** A test or inspection command confirms retrieved chunks contain date, source/title, and evidence-capable metadata.

## Module 4: Chat Citations

**Files:**
- Modify: `rag/server.py`
- Modify: `rag/agent/tools.py`
- Add tests for citation extraction behavior

**Concept:** Chat citations are structured references returned alongside the generated answer.

**Role:** They let Conrad inspect whether an answer is actually grounded in AI Trend Radar evidence.

**Implementation direction:** Keep citation data from retrieval/tool results and return it in `/chat`. P0 can use conservative citation extraction from top retrieval results before attempting full LLM-grounded citation attribution.

**Verification:** For an answerable question, `/chat` returns at least one citation with date, source/title, and excerpt.

## Module 5: Golden Question Evaluation

**Files:**
- Modify: `docs/rag-transformation/evals/golden-questions.md`
- Create: local evaluation script or pytest cases after the citation path exists

**Concept:** Golden questions are representative questions with expected behavior.

**Role:** They prevent quality from being judged by vibes and catch regressions.

**Implementation direction:** Use the first five questions as the seed set. Mark whether each question should be answerable from internal corpus only or may need web search later.

**Verification:** A local command evaluates the five questions and records pass/fail notes in `docs/rag-transformation/evidence/`.

## Module 6: Web Search Tool Boundary

**Files:**
- Create or update an architecture note before implementation

**Concept:** Web search is a tool for external freshness and gap filling, not a substitute for the internal corpus.

**Role:** It lets the future Agent answer questions that exceed AI Trend Radar corpus coverage while still separating internal evidence from external evidence.

**Implementation direction:** Do not implement web search in P0. Define future tool contracts such as `search_corpus`, `web_search`, `fetch_url`, and `compare_internal_and_external`.

**Verification:** The architecture note clearly states when web search is allowed and how its citations differ from internal corpus citations.
