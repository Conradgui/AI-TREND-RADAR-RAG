# Evidence: P1 Search Provider Routing Strategy

Date: 2026-06-22

## What Changed

Added a deterministic multi-provider routing strategy for future external search.

This module does not call external APIs. It decides which provider should be tried first for each search task type and records unavailable providers when API keys are missing.

## Files Added

- `docs/rag-transformation/decisions/0003-search-provider-routing.md`
- `docs/rag-transformation/plans/p1-search-provider-routing.md`
- `rag/search_provider_routing.py`
- `rag/eval_search_provider_routing.py`
- `rag/tests/test_search_provider_routing.py`
- `rag/tests/test_search_provider_config.py`
- `rag/tests/test_eval_search_provider_routing.py`
- `docs/rag-transformation/evals/search-provider-routing-2026-06-22.json`

## Files Updated

- `.env.example`
- `package.json`
- `rag/config.py`
- `rag/chat_service.py`
- `rag/tool_routing.py`
- `rag/tests/test_tool_routing.py`
- `docs/rag-transformation/roadmap.md`

## Provider Routing

Default strategy:

- `official_source_lookup`: Tavily -> Brave -> SerpAPI
- `research_paper`: Exa -> Tavily -> SerpAPI
- `technical_article`: Exa -> Tavily -> Brave
- `recent_web`: Brave -> Tavily -> Exa
- `github_repo`: GitHub API -> Brave -> Tavily
- `broad_serp`: Brave -> SerpAPI -> Tavily
- `google_scholar`: SerpAPI -> Exa -> Tavily
- `google_trends`: SerpAPI -> Brave -> Tavily

Google Custom Search JSON API is intentionally excluded from the default provider profiles because the official documentation says it is not available for new customers.

## Validation

### Focused Provider Tests

Command:

```bash
python3 -m unittest rag.tests.test_eval_search_provider_routing rag.tests.test_search_provider_routing rag.tests.test_search_provider_config rag.tests.test_tool_routing -v
```

Result:

- 12 tests passed.

### Full Focused RAG Check

Command:

```bash
pnpm rag:check:p0
```

Result:

- 87 tests passed.
- Python compile check passed.

### Deterministic Provider Routing Snapshot

Command:

```bash
python3 -m rag.eval_search_provider_routing
```

Result:

```json
{
  "total": 5,
  "needs_web": 2,
  "needs_web_with_configured_primary": 0,
  "needs_web_without_configured_primary": 2
}
```

Interpretation:

- The route evaluator found 2 needs-web golden questions.
- No external provider key is configured yet, so those rows correctly have no configured primary provider.
- This is expected and safer than pretending web search is available.

## Live Benchmark Note

Attempted to regenerate the live DeepSeek benchmark after adding provider routing, but the tool call was rejected by current Codex usage limits.

The module was therefore validated with deterministic local tests and provider-routing snapshot only.

## Remaining Risk

- No real external provider client exists yet.
- Provider free quotas and pricing are dynamic and must be refreshed before production use.
- API keys for Brave/Tavily/Exa/SerpAPI are not configured yet.
