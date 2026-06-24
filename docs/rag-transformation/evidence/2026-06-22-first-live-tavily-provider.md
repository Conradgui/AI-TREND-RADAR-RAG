# Evidence: P1 First Live Tavily Provider

Date: 2026-06-22

## What Changed

Implemented Tavily as the first live external search provider.

The adapter now:

- calls Tavily Search through the provider-agnostic adapter interface;
- uses `search_depth=basic` by default to conserve credits;
- disables raw content, images, and LLM answer generation by default;
- normalizes Tavily results into external citations;
- truncates noisy excerpts to keep evidence usable;
- returns structured provider errors without exposing API keys.

## Files Added

- `docs/rag-transformation/plans/p1-first-live-tavily-provider.md`
- `rag/eval_tavily_live.py`
- `docs/rag-transformation/evals/tavily-live-smoke-2026-06-22.json`

## Files Updated

- `rag/search_provider_adapters.py`
- `rag/tests/test_search_provider_adapters.py`
- `package.json`
- `docs/rag-transformation/roadmap.md`

## Validation

### Adapter Tests

Command:

```bash
python3 -m unittest rag.tests.test_search_provider_adapters rag.tests.test_eval_search_provider_adapters -v
```

Result:

- 7 tests passed.

### Full Focused RAG Check

Command:

```bash
pnpm rag:check:p0
```

Result:

- 95 tests passed.
- Python compile check passed.

### Tavily Live Smoke

Command:

```bash
.venv/bin/python -m rag.eval_tavily_live --query "Google OKF ALM Wiki"
```

Result:

```json
{
  "available": true,
  "citation_count": 1,
  "raw_results_count": 1,
  "errors": [],
  "usage": {
    "credits": 1
  }
}
```

## Quality Note

The live smoke returned a LinkedIn result related to Google Cloud and OKF.

This proves the Tavily adapter works, but it also shows the next product-quality problem: external search needs source-quality controls. For Q5-style official-source questions, the system should prefer official domains such as Google, Google Cloud, Google Research, DeepMind, or primary documentation over social reposts.

## Remaining Risk

- Tavily is live, but external search is not yet merged into final chat answers.
- Source-quality ranking is not implemented.
- URL fetch/extract is not implemented.
- Brave, Exa, SerpAPI, and GitHub live adapters are not implemented yet.
