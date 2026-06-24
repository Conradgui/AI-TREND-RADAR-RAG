# P1 First Live Tavily Provider Plan

Date: 2026-06-22

## Goal

Implement Tavily as the first live external search provider behind the existing provider-agnostic adapter interface.

## Product Meaning

This is the first step from "planned external search" to "real external evidence."

The provider must return citation-ready external evidence, not raw web snippets mixed directly into answers.

## Scope

1. Add a Tavily adapter.
   - Uses `POST https://api.tavily.com/search`.
   - Uses Bearer authentication.
   - Defaults to `search_depth=basic` to conserve credits.
   - Uses `max_results` from `SearchRequest`.

2. Normalize Tavily results into external citations.
   - `evidence_type=external`
   - `source`
   - `title`
   - `url`
   - `retrieved_at`
   - `excerpt`
   - optional `provider`, `score`, `source_type`

3. Add registry support.
   - If `tavily` key exists, registry uses the live Tavily adapter.
   - If key is missing, registry still returns `missing_api_key`.

4. Add live smoke evaluator.
   - One query.
   - `max_results=1`.
   - No answer generation.
   - No raw content.

## Out of Scope

- Brave, Exa, SerpAPI, and GitHub live clients.
- URL fetch/extract.
- Merging external citations into final LLM answers.
- High-volume searches.

## Validation

1. Tavily adapter mock tests pass.
2. Registry tests pass.
3. `pnpm rag:check:p0` passes.
4. Tavily live smoke returns structured output or a clear provider error without printing API keys.
