# Evidence: P1 Search Provider Adapter Interface

Date: 2026-06-22

## What Changed

Added a provider-agnostic adapter interface for future external search providers.

This module does not call real provider APIs. It defines:

- a stable `SearchRequest` shape;
- a stable unavailable search result shape;
- a disabled adapter for known providers without keys;
- a registry that safely rejects unknown providers;
- a readiness evaluator for adapter behavior.

## Files Added

- `rag/search_provider_adapters.py`
- `rag/eval_search_provider_adapters.py`
- `rag/tests/test_search_provider_adapters.py`
- `rag/tests/test_eval_search_provider_adapters.py`
- `docs/rag-transformation/plans/p1-search-provider-adapter-interface.md`
- `docs/rag-transformation/evals/search-provider-adapters-2026-06-22.json`

## Files Updated

- `package.json`
- `docs/rag-transformation/roadmap.md`

## Validation

### Adapter Tests

Command:

```bash
python3 -m unittest rag.tests.test_search_provider_adapters rag.tests.test_eval_search_provider_adapters -v
```

Result:

- 5 tests passed.

### Adapter Readiness

Command:

```bash
python3 -m rag.eval_search_provider_adapters
```

Result:

```json
{
  "output": "docs/rag-transformation/evals/search-provider-adapters-2026-06-22.json",
  "passed": true
}
```

### Full Focused RAG Check

Command:

```bash
pnpm rag:check:p0
```

Result:

- 92 tests passed.
- Python compile check passed.

## Product Interpretation

This layer makes external search extensible without letting provider-specific response formats leak into the core RAG answer path.

It also makes missing API keys non-fatal. The system can now say "provider unavailable because key is missing" instead of failing unpredictably.

## Keys Needed For Next Live Provider Loop

Minimum one:

- `BRAVE_SEARCH_API_KEY`
- `TAVILY_API_KEY`

Useful next:

- `EXA_API_KEY`

Optional/specialty:

- `SERPAPI_API_KEY`
- `GITHUB_TOKEN`

## Remaining Risk

- No real provider client has been implemented.
- No live external citations have been fetched.
- External provider usage still needs cost/rate-limit monitoring.
