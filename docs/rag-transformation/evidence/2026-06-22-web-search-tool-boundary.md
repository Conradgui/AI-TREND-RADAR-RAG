# Evidence: Web Search Tool Boundary

## Date

2026-06-22

## Module

P0 / Module 6: Web Search Tool Boundary

## What Was Verified

The project now has an explicit boundary for future web search tools.

Files:

- `docs/rag-transformation/decisions/0002-web-search-tool-boundary.md`
- `rag/tests/test_tool_boundary_docs.py`

## Module Tests

Command:

```bash
python3 -m unittest rag.tests.test_tool_boundary_docs -v
```

Result:

```text
Ran 2 tests in 0.001s

OK
```

## Golden Question Validation

Command:

```bash
python3 -m rag.eval_golden
```

Result:

```json
{
  "errors": [],
  "summary": {
    "total": 5,
    "answerability": {
      "insufficient": 0,
      "internal-only": 3,
      "needs-web": 2
    },
    "needs_conrad_review": 5,
    "current_status": {
      "dataset-ready-not-live-evaluated": 5
    }
  }
}
```

## P0 Focused Suite

Command:

```bash
python3 -m unittest rag.tests.test_tool_boundary_docs rag.tests.test_eval_golden rag.tests.test_chat_service rag.tests.test_citations rag.tests.test_ingest rag.tests.test_graphrag_builder rag.tests.test_sync_corpus -v
```

Result:

```text
Ran 33 tests in 0.030s

OK
```

## Interpretation

Web search remains out of P0 implementation scope. The boundary now defines four future tool contracts:

- `search_corpus`
- `web_search`
- `fetch_url`
- `compare_internal_and_external`

The decision document makes internal and external evidence labels explicit.

## Residual Risk

No actual web search provider, browser automation tool, source ranking policy, or external citation implementation exists yet. Those require future design and, depending on provider choice, Conrad approval.

## Reviewer Gate

Reviewer verdict: `Pass With Follow-ups`.

No P0 blocking issues were found.

P1 follow-ups before implementing web search:

- Define strict tool schemas, including input parameters, output schema, errors, logs, and invocation conditions.
- Add stronger tests to prevent web search from becoming the default P0 path.
- Clarify Q3's "recent Claude updates" benchmark mode: P0 should answer from internal corpus only, otherwise evidence-insufficient; it should not behave as a real-time product news query until web search is explicitly enabled.
