# P1 Live Deep Fetch Smoke and Runtime Toggle Plan

Date: 2026-06-23

## Module

P1 Live Deep Fetch Smoke and Runtime Toggle

## Concept

Deep fetch means the Agent can open a selected external citation URL and extract a short page excerpt after web search returns a candidate source.

This is useful because search snippets are not enough for high-trust answers. The system should inspect important sources, especially official, academic, developer, or weak sources that need verification.

## Definition of Done

Product behavior:

- Live URL deep fetch is disabled by default.
- Runtime can explicitly enable deep fetch through configuration.
- The system exposes whether deep fetch is enabled.
- Live smoke evidence separates search-provider discovery from URL fetch behavior.

Engineering behavior:

- Server passes the real `fetch_url` function only when `RAG_ENABLE_DEEP_FETCH` is explicitly enabled.
- Deterministic tests prove the toggle behavior.
- URL fetch safety remains in place for private/local targets.

Evidence behavior:

- Deep-fetch trace records attempted status, selected URL count, success count, failure count, and target source quality.
- Live smoke output is saved under `docs/rag-transformation/evals/`.

Evaluation behavior:

- Run focused runtime/deep-fetch tests.
- Run canonical `pnpm rag:check:p0`.
- Run one low-volume live URL deep-fetch smoke.

Non-goals:

- Do not enable deep fetch by default.
- Do not claim all search providers can discover the right official URL.
- Do not change the original AI Trend Radar UI.

Residual risks:

- Search-provider discovery can be volatile until Brave, Exa, and GitHub live adapters are implemented.
- Redirect-chain safety is not fully hardened yet.
- Live URL fetching may fail for sites with bot protection or non-HTML rendering.
