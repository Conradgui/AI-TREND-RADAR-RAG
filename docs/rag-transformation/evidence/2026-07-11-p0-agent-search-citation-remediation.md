# P0 Agent, Search, And Citation Remediation Evidence

Date: 2026-07-11

## Scope

This evidence covers remediation branch `codex/claude-audit-remediation` after the preserved Claude snapshot `7a47b1c`. It does not certify a live provider, local dashboard, Docker runtime, or Stage 2.4 completion.

## Baseline

`pnpm rag:check:p0` initially ran 191 deterministic tests and failed with 5 failures plus 2 errors.

| Boundary | Reproduced issue | Classification |
| --- | --- | --- |
| Agent invocation | `chat_service` passed a second positional argument to agents whose contract only accepted a payload. | Shared-path bug |
| Search requests | Tavily forced every task into advanced, recent-news search, including paper and official-source discovery. | Shared-path bug |
| Citation selection | The external merge no longer called the existing citation-refinement policy. | Shared-path bug |
| Search trace | A cache hit was labelled as an executed external search; cache keys did not include the search route. | Shared-path truthfulness bug |
| Test fixtures | Fixed June `retrieved_at` values crossed the real ten-day freshness boundary in July. | Deterministic-test maintenance bug |

## Changes Verified

1. Direct-LLM fallback and LangGraph-compatible agents now share `ainvoke(payload, config=None)`.
2. The direct-LLM adapter is importable without loading provider SDKs; selecting an unavailable provider now fails when creating that model with a clear error.
3. Tavily and Brave only apply recent-news freshness constraints to `recent_web`; paper and official lookup tasks use general search.
4. External citations go through existing refinement after merging, so obvious unrelated internal noise is excluded in needs-web answers.
5. Cache entries are scoped to question plus task/provider route. A cache hit is emitted as `reused_cached_result`, not as a new tool execution.
6. Freshness-sensitive test citations now use the current date; the production ten-day freshness policy is unchanged.

## Verification

- Focused: `python3 -m unittest rag.tests.test_chat_service rag.tests.test_search_provider_adapters -v` — 22 passed.
- Canonical: `pnpm rag:check:p0` — 193 passed, including syntax compilation.
- Diff integrity: `git diff --check` — passed.

The canonical count is two higher than baseline because this remediation adds contract coverage for direct-LLM invocation and cache-trace truthfulness. It must not be described as a coverage percentage or as live-runtime evidence.

## Residual Risks

- No real LLM/provider request was made; credentials, provider availability, latency, and semantic answer quality remain unverified.
- Dashboard-local `/chat` acceptance still needs the separate Stage 2.4 local-runtime gate.
- External search cache is process-local and five minutes long by design. It is not a durable evidence store.
