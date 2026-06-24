# Evidence: P1 Live Provider Adapter Expansion

Date: 2026-06-23

## What Changed

- Added live Brave Search adapter.
- Added live Exa Search adapter.
- Added live GitHub repository search adapter.
- Kept all providers behind the existing `SearchProviderRegistry`.
- Normalized Brave, Exa, GitHub, and Tavily outputs into the same external citation schema.
- Added `rag/eval_search_provider_live.py` for low-volume live smoke checks.
- Added `pnpm rag:eval:search-provider-live`.

## Official API Basis

- Brave Web Search uses `https://api.search.brave.com/res/v1/web/search` with `X-Subscription-Token`.
- Exa Search uses `POST https://api.exa.ai/search` with `x-api-key`.
- GitHub repository search uses the REST search repositories endpoint and normalized repository metadata.

## Validation

Focused tests:

```text
python3 -m unittest rag.tests.test_search_provider_adapters rag.tests.test_eval_search_provider_adapters -v
Ran 13 tests
OK
```

Canonical check:

```text
pnpm rag:check:p0
Ran 122 tests
OK
```

Live provider smoke:

```text
.venv/bin/python -m rag.eval_search_provider_live
provider_count: 3
available_count: 3
providers_with_citations: brave, exa, github
providers_with_errors: none
```

Output:

- `docs/rag-transformation/evals/search-provider-live-smoke-2026-06-23.json`

Observed first citations:

- Brave: generic web source for Claude update.
- Exa: academic source for Agentic RAG survey.
- GitHub: GitHub repository citation.

## End-to-End Fallback Result

After adding Brave, the OKF/ALM chat-level smoke improved:

```text
external_search_attempted: true
attempts: Tavily returned 0 citations; Brave returned 2 citations
answer_policy_mode: internal_and_external_grounded
deep_fetch_attempted: true
deep_fetch_selected_count: 2
deep_fetch_success_count: 1
deep_fetch_failure_count: 1
```

Output:

- `docs/rag-transformation/evals/deep-fetch-live-smoke-2026-06-23.json`

Interpretation:

- Provider fallback works.
- External citations can trigger deep fetch.
- Deep fetch is still best-effort; one official Google URL returned `network_error` in the chat-level run, while the standalone URL smoke for the same URL had succeeded earlier.

## Product Interpretation

This module materially reduces single-provider fragility.

Before:

- Tavily returning zero citations blocked the OKF/ALM external evidence path.

After:

- The system can fall back to Brave and still produce external citations.
- Research-style queries can use Exa.
- GitHub-specific questions can use the GitHub API instead of generic web search.

## Residual Risks

- No provider-level quota accounting yet.
- Provider result quality still needs evaluation beyond one smoke query.
- Source conflict handling is not implemented yet.
- Deep fetch should eventually validate redirect chains and expose retry/failure classification more clearly.
