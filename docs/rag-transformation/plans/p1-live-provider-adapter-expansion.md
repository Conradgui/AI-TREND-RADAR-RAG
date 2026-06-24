# P1 Live Provider Adapter Expansion Plan

Date: 2026-06-23

## Module

P1 Live Provider Adapter Expansion

## Concept

Provider adapters turn different external search APIs into one internal citation format.

The Agent should not care whether evidence came from Brave, Exa, GitHub, or Tavily. It should receive normalized external citations with source, title, URL, excerpt, retrieved date, source quality, and failure trace.

## Provider Roles

- Brave Search: broad and fresh web search.
- Exa Search: research, papers, technical articles, and AI-native semantic search.
- GitHub REST API: repository discovery and GitHub-specific questions.
- Tavily: existing agent-oriented and official-source lookup provider.

## Definition of Done

Product behavior:

- The system can route to more than one live provider.
- If one provider returns no citations, the next provider can be attempted.
- Provider-specific output is normalized into one citation schema.

Engineering behavior:

- Brave, Exa, and GitHub adapters exist behind `SearchProviderRegistry`.
- Unit tests cover request shape, response normalization, registry selection, and safe error handling.
- Live smoke scripts or one consolidated live smoke produce sanitized evidence.

Evidence behavior:

- Live outputs are saved under `docs/rag-transformation/evals/`.
- Docs record which provider worked, which failed, and why.

Evaluation behavior:

- Run adapter unit tests.
- Run canonical `pnpm rag:check:p0`.
- Run low-volume live smoke only after deterministic tests pass.

Non-goals:

- Do not add a new framework.
- Do not implement full provider quota accounting.
- Do not claim production reliability from one smoke run.
- Do not change the original AI Trend Radar UI.

Residual risks:

- API plans and free quotas may vary.
- Live provider schemas can change.
- Search results can be volatile even when APIs are healthy.
