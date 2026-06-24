# P1 Tool Routing Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define and verify the agent tool-routing contract before implementing real web search.

**Architecture:** Add a deterministic tool-routing planner that consumes the query plan, answer policy, and citation count. The planner always records internal corpus search, marks when external tools are required, and exposes safe fallback behavior while web search is not implemented.

**Tech Stack:** Python standard library, `unittest`, existing RAG query-understanding/chat-service pipeline.

## Global Constraints

- Do not implement real web search in this module.
- Do not modify the original AI Trend Radar UI.
- Keep external tools labeled as unavailable until a later implementation loop.
- Preserve existing P0/P1 focused checks.
- Do not store secrets in docs or committed files.

---

## File Structure

- Create `rag/tool_routing.py`
  - Owns deterministic tool route planning.
  - Produces a serializable dict for API responses and benchmark snapshots.

- Create `rag/eval_tool_routing.py`
  - Scores live chat snapshots for routing-contract compliance.

- Create `rag/tests/test_tool_routing.py`
  - Unit tests for route planning.

- Create `rag/tests/test_eval_tool_routing.py`
  - Unit tests for route rubric.

- Modify `rag/chat_service.py`
  - Attach `tool_routing` to `query_understanding`.
  - Add routing notes to the system prompt.

- Modify `rag/eval_live_chat.py`
  - Live snapshots inherit `tool_routing` from chat responses automatically via `query_understanding`.

- Modify `package.json`
  - Add `rag:eval:tool-routing`.
  - Add new tests and compile targets to `rag:check:p0`.

- Modify docs under `docs/rag-transformation/`
  - Save evidence, execution log, and roadmap update.

## Task 1: Tool Routing Planner

**Files:**
- Create: `rag/tool_routing.py`
- Create: `rag/tests/test_tool_routing.py`

**Interfaces:**
- Consumes: `QueryPlan`, answer-policy dict, citation list.
- Produces: `build_tool_route(plan, answer_policy, citations) -> dict`.

- [ ] **Step 1: Write failing tests**

Tests should cover:

- internal-only questions record `search_corpus` and no external requirement.
- needs-web questions record `search_corpus`, planned `web_search`, planned `fetch_url`, and `external_tools_available=False`.
- no-citation questions stop after internal search and recommend corpus expansion or external search.

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
python3 -m unittest rag.tests.test_tool_routing -v
```

Expected:

- Fail because `rag.tool_routing` does not exist.

- [ ] **Step 3: Implement planner**

Rules:

- Always include an internal `search_corpus` step.
- If `answer_policy["external_search_required"]` is true, append planned external steps:
  - `web_search`
  - `fetch_url`
  - `compare_internal_and_external`
- Set `external_tools_available` to `False`.
- Set `status` to:
  - `internal_only_ready`
  - `external_required_not_available`
  - `evidence_insufficient`
- Set `max_tool_calls` to `1` for internal-only, `4` for needs-web.

- [ ] **Step 4: Run tests and confirm pass**

Run:

```bash
python3 -m unittest rag.tests.test_tool_routing -v
```

Expected:

- All tests pass.

## Task 2: Chat Trace Integration

**Files:**
- Modify: `rag/chat_service.py`
- Modify: `rag/tests/test_chat_service.py`

**Interfaces:**
- Consumes: `build_tool_route(...)`.
- Produces: `query_understanding["tool_routing"]`.

- [ ] **Step 1: Write failing chat-service tests**

Tests should verify:

- chat response includes `query_understanding.tool_routing`.
- needs-web system prompt says external tools are planned but not available.

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
python3 -m unittest rag.tests.test_chat_service -v
```

Expected:

- Fail because `tool_routing` is not yet attached.

- [ ] **Step 3: Integrate tool route into chat service**

Implementation:

- Build route after answer policy is known.
- Attach route to `query_understanding`.
- Add routing lines to the evidence context.

- [ ] **Step 4: Run tests and confirm pass**

Run:

```bash
python3 -m unittest rag.tests.test_chat_service -v
```

Expected:

- All tests pass.

## Task 3: Tool Routing Rubric

**Files:**
- Create: `rag/eval_tool_routing.py`
- Create: `rag/tests/test_eval_tool_routing.py`
- Modify: `package.json`

**Interfaces:**
- Consumes: live snapshot rows.
- Produces: `score_tool_routing_rows(rows) -> list[dict]` and `summarize_tool_routing_rows(rows) -> dict`.

- [ ] **Step 1: Write failing rubric tests**

Tests should verify:

- internal-only rows pass with `search_corpus`.
- needs-web rows fail unless they include planned external steps and unavailable external-tool status.

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
python3 -m unittest rag.tests.test_eval_tool_routing -v
```

Expected:

- Fail because evaluator does not exist.

- [ ] **Step 3: Implement evaluator and package scripts**

Add:

- `rag:eval:tool-routing`
- new tests to `rag:test:p0`
- new modules to `py_compile`.

- [ ] **Step 4: Run focused checks**

Run:

```bash
python3 -m unittest rag.tests.test_tool_routing rag.tests.test_chat_service rag.tests.test_eval_tool_routing -v
pnpm rag:check:p0
```

Expected:

- All tests pass.

## Task 4: Live Snapshot and Evidence

**Files:**
- Modify: `docs/rag-transformation/roadmap.md`
- Create: `docs/rag-transformation/evidence/2026-06-22-tool-routing-contract.md`
- Create: `docs/rag-transformation/execution-log/2026-06-22-module-p1-tool-routing-contract.md`
- Generate: `docs/rag-transformation/evals/live-tool-routing-rubric-2026-06-22.json`

**Interfaces:**
- Uses existing `.venv` and DeepSeek local test configuration.

- [ ] **Step 1: Regenerate live chat snapshot**

Run:

```bash
.venv/bin/python -m rag.eval_live_chat
```

Expected:

- 5 rows with citations and `query_understanding.tool_routing`.

- [ ] **Step 2: Run tool-routing rubric**

Run:

```bash
python3 -m rag.eval_tool_routing
```

Expected:

- 5/5 rows pass routing contract.

- [ ] **Step 3: Save evidence and roadmap update**

Record:

- tests run
- benchmark results
- what is still intentionally not implemented
