# Execution Log: P1 Search Provider Routing Strategy

Date: 2026-06-22

## Loop

1. Checked official provider docs and pricing pages for current routing assumptions.
2. Created decision doc:
   - `docs/rag-transformation/decisions/0003-search-provider-routing.md`
3. Created module plan:
   - `docs/rag-transformation/plans/p1-search-provider-routing.md`
4. Added failing tests:
   - `rag/tests/test_search_provider_routing.py`
   - `rag/tests/test_search_provider_config.py`
5. Implemented provider routing:
   - `rag/search_provider_routing.py`
6. Added optional provider config:
   - `.env.example`
   - `rag/config.py`
7. Connected provider route into tool routing for needs-web questions:
   - `rag/tool_routing.py`
   - `rag/chat_service.py`
8. Added deterministic provider-routing evaluation:
   - `rag/eval_search_provider_routing.py`
   - `rag/tests/test_eval_search_provider_routing.py`
9. Ran focused checks and generated snapshot.
10. Updated roadmap and evidence.

## Key Decision

Use multi-provider routing instead of choosing one search API.

Provider chain:

- official source lookup: Tavily -> Brave -> SerpAPI
- research paper: Exa -> Tavily -> SerpAPI
- recent web: Brave -> Tavily -> Exa
- GitHub repo: GitHub API -> Brave -> Tavily

## Validation

- Provider routing tests: 12 passed.
- Full focused RAG check: 87 passed.
- Deterministic provider-routing snapshot generated.

## Blockers

- DeepSeek live benchmark regeneration was blocked by current Codex usage limit, so this loop did not refresh the live chat snapshot.
- Real external search still requires API keys and provider client implementation.

## Next Recommended Loop

P1 Search Provider Adapter Interface.

Implement provider adapters behind one interface, but start with one low-risk provider only after API key availability is confirmed.

Recommended first live provider:

1. Brave Search API for recent web and broad search, because it has clear freshness support and monthly free credits.
2. Tavily second for agentic/domain-constrained lookup.
3. Exa third for research-paper/technical article tasks.
4. SerpAPI only for Scholar/Trends/Google SERP compatibility.
