# P1 Search Provider Adapter Interface Plan

Date: 2026-06-22

## Goal

Create a stable adapter interface for future external search providers without calling real provider APIs yet.

## Product Meaning

Provider routing decides which search provider should be used. The adapter interface decides what every provider must return.

This prevents future Brave, Tavily, Exa, SerpAPI, and GitHub implementations from leaking provider-specific response shapes into the core RAG system.

## Scope

1. Add a provider-agnostic search request shape.
   - `query`
   - `task_type`
   - `provider`
   - `max_results`
   - `include_domains`
   - `exclude_domains`

2. Add a provider-agnostic search result shape.
   - `provider`
   - `available`
   - `query`
   - `citations`
   - `raw_results_count`
   - `errors`

3. Add disabled adapters for all configured provider profiles.
   - No network calls.
   - Missing keys should return structured unavailable results.

4. Add a registry.
   - Select adapter by provider name.
   - Reject unknown providers safely.

## Out of Scope

- Real Brave/Tavily/Exa/SerpAPI/GitHub API calls.
- HTTP clients.
- URL fetching.
- LLM answer generation changes.

## Validation

1. Adapter interface tests pass.
2. Registry tests pass.
3. Disabled adapter output passes external evidence conventions.
4. `pnpm rag:check:p0` passes.
