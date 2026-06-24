# P1 External Source Quality Controls and Excerpt Policy Plan

Date: 2026-06-22

## Goal

Replace the temporary fixed 600-character excerpt cap with source-aware quality controls.

## Product Meaning

External search being "available" is not enough. The RAG system must distinguish primary evidence from social reposts and noisy pages.

For official-source questions, a LinkedIn repost can be a discovery signal, but it should not be treated as final primary evidence.

## Scope

1. Add source quality classification.
   - official
   - academic
   - developer
   - trusted_media
   - social
   - generic

2. Add source-quality metadata to external citations.
   - `source_quality`
   - `quality_score`
   - `needs_deep_fetch`
   - `quality_notes`

3. Add dynamic excerpt policy.
   - official/academic/developer: preserve more context.
   - social/noisy pages: cap aggressively and mark for deep fetch or replacement.
   - generic: moderate cap.

4. Add Tavily domain routing for official-source tasks.
   - For Google/OKF-style official lookup, prefer Google domains.
   - Exclude common social domains when the task demands primary evidence.

## Out of Scope

- Browser fetching.
- Full URL content extraction.
- LLM reranking.
- Final answer integration with external evidence.

## Validation

1. Source quality tests pass.
2. Tavily payload uses include/exclude domains for official-source tasks when provided by routing policy.
3. Excerpt policy preserves more content for official sources than social sources.
4. `pnpm rag:check:p0` passes.
