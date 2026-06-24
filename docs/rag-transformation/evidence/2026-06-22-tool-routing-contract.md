# Evidence: P1 Tool Routing Contract

Date: 2026-06-22

## What Changed

Added a deterministic tool-routing contract before implementing real web search.

This module records what tools the agent should use, which tools are only planned, and what fallback behavior applies when external tools are unavailable.

## Files Added

- `rag/tool_routing.py`
- `rag/eval_tool_routing.py`
- `rag/tests/test_tool_routing.py`
- `rag/tests/test_eval_tool_routing.py`
- `docs/rag-transformation/plans/p1-tool-routing-contract.md`
- `docs/rag-transformation/evals/live-tool-routing-rubric-2026-06-22.json`

## Files Updated

- `rag/chat_service.py`
- `rag/tests/test_chat_service.py`
- `package.json`
- `docs/rag-transformation/roadmap.md`

## Product Meaning

This adds a visible control layer for future Function Calling.

The system now distinguishes:

- internal-only questions that should only use `search_corpus`;
- needs-web questions that require `web_search`, `fetch_url`, and `compare_internal_and_external`;
- no-evidence questions that should stop instead of fabricating an answer.

External tools are intentionally marked unavailable in this module. This prevents the agent from implying that it has already searched the web.

## Validation

### TDD Red Check

Command:

```bash
python3 -m unittest rag.tests.test_tool_routing rag.tests.test_chat_service -v
```

Initial expected result:

- Failed because `rag.tool_routing` did not exist.
- Failed because chat responses did not include `query_understanding.tool_routing`.

### Focused Module Tests

Command:

```bash
python3 -m unittest rag.tests.test_tool_routing rag.tests.test_chat_service rag.tests.test_eval_tool_routing -v
```

Result:

- 11 tests passed.

### Full Focused RAG Check

Command:

```bash
pnpm rag:check:p0
```

Result:

- 73 tests passed.
- Python compile check passed.

### Live Benchmark

Command:

```bash
.venv/bin/python -m rag.eval_live_chat
```

Result:

```json
{
  "total": 5,
  "with_citations": 5,
  "without_citations": 0,
  "needs_web_questions": 2
}
```

### Tool-Routing Rubric

Command:

```bash
python3 -m rag.eval_tool_routing
```

Result:

```json
{
  "total": 5,
  "passed": 5,
  "failed": 0
}
```

## Snapshot Sanity Check

- Q1: `internal_only_ready`, `search_corpus:executed`
- Q2: `external_required_not_available`, `search_corpus:executed`, `web_search:planned_unavailable`, `fetch_url:planned_unavailable`, `compare_internal_and_external:planned_unavailable`
- Q3: `internal_only_ready`, `search_corpus:executed`
- Q4: `internal_only_ready`, `search_corpus:executed`
- Q5: `external_required_not_available`, `search_corpus:executed`, `web_search:planned_unavailable`, `fetch_url:planned_unavailable`, `compare_internal_and_external:planned_unavailable`

## Remaining Risk

- Real web search is still not implemented.
- External citation schemas are only specified by contract, not exercised with live external sources.
- Neo4j/Graph RAG runtime remains blocked locally because Docker/Neo4j is unavailable.
