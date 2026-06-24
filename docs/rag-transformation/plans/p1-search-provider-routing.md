# P1 Search Provider Routing Strategy Plan

Date: 2026-06-22

## Goal

Add a deterministic provider-routing layer for future external search.

This module configures provider profiles and routing rules. It does not call real external search APIs.

## Scope

1. Add provider profiles.
   - Brave
   - Tavily
   - Exa
   - SerpAPI
   - GitHub API

2. Add environment configuration keys.
   - `BRAVE_SEARCH_API_KEY`
   - `TAVILY_API_KEY`
   - `EXA_API_KEY`
   - `SERPAPI_API_KEY`
   - `GITHUB_TOKEN`

3. Add deterministic routing.
   - Route by task type.
   - Prefer free-quota-friendly providers.
   - Return unavailable providers when keys are missing.

4. Add tests and evaluation.
   - Research-paper tasks prefer Exa.
   - Recent-web tasks prefer Brave.
   - GitHub repo tasks prefer GitHub API.
   - Google Custom Search is excluded from default routing.

## Out of Scope

- Real API clients.
- Network calls.
- Fetching URLs.
- Merging external evidence into final answers.

## Validation

1. Provider routing tests pass.
2. Config tests pass.
3. `pnpm rag:check:p0` passes.
4. Evidence and execution logs are saved.
