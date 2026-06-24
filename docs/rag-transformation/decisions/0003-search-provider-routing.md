# Decision 0003: Search Provider Routing Strategy

## Status

Accepted for P1 routing design.

## Context

AI Trend Radar RAG needs external search for questions that exceed the internal corpus, but different search APIs have different strengths.

Using only one provider is brittle:

- it may waste free quota on the wrong task type;
- it may return weak sources for academic or official-source queries;
- it may fail or rate-limit without a fallback path.

The product goal is not "use every search API." The goal is to route each search task to the cheapest provider that is likely to return citation-ready evidence.

## Official Source Notes

These notes were checked on 2026-06-22 and should be refreshed before production deployment.

- Tavily pricing page lists a free Researcher plan with 1,000 API credits per month and no credit card requirement. Tavily search supports search depth, time ranges, include/exclude domains, raw content, and news/general topics.
  - Sources: https://www.tavily.com/pricing, https://docs.tavily.com/documentation/api-reference/endpoint/search
- Exa search is positioned for AI search and can return contents/highlights, research-paper category, published dates, authors, and search types such as instant/fast/deep. Exa pricing page mentions startup and education grants with free credits.
  - Sources: https://exa.ai/docs/reference/search, https://exa.ai/pricing
- Brave Search API provides web/news/image-style search data for agents, mentions LLM context, freshness filters such as last 24 hours and last 7 days, and lists $5 monthly free credits.
  - Sources: https://brave.com/search/api/, https://api-dashboard.search.brave.com/app/documentation/web-search/get-started
- SerpAPI has broad SERP coverage, including Google Search, Google News, Google Scholar, Google Trends, Bing, DuckDuckGo, Brave, and more. Its pricing page lists a free plan with 250 searches per month.
  - Sources: https://serpapi.com/pricing, https://serpapi.com/search-api
- Google Custom Search JSON API is not a recommended new-project choice because the official page says it is not available for new customers and existing customers must transition by 2027-01-01.
  - Source: https://developers.google.com/custom-search/v1/overview
- GitHub REST API is a specialized provider for repository/topic discovery. GitHub docs list 60 unauthenticated requests/hour and 5,000 authenticated requests/hour for general REST API usage; search endpoints may be more restrictive.
  - Source: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api

## Decision

Configure multiple external search providers, but route by task type.

### Provider Profiles

| Provider | Best For | Use Carefully For | Default Role |
| --- | --- | --- | --- |
| Brave | fresh web/news, broad low-cost web discovery | deep academic synthesis | default recent-web provider |
| Tavily | agentic web search, domain-constrained lookup, source extraction | very broad SERP emulation | default official-source/domain provider |
| Exa | research papers, technical articles, AI-native semantic search | strict latest-news monitoring | default research provider |
| SerpAPI | Google SERP compatibility, Scholar/Trends/News fallback | routine low-cost searches | paid/fallback specialty provider |
| GitHub API | repositories, stars, topics, code/project discovery | non-GitHub web search | default GitHub provider |

### Routing Rules

1. Always search internal corpus first.
2. If external evidence is required, choose at most two external providers for a normal answer.
3. Prefer free-quota-friendly providers before paid or broad SERP providers.
4. Use task-specific providers:
   - `official_source_lookup`: Tavily, then Brave.
   - `research_paper`: Exa, then Tavily, then SerpAPI.
   - `recent_web`: Brave, then Tavily.
   - `github_repo`: GitHub API, then Brave, then Tavily.
   - `broad_serp`: Brave, then SerpAPI, then Tavily.
5. Use SerpAPI only when Google-style SERP, Google Scholar, Google Trends, or broad engine compatibility is specifically useful.
6. Do not use Google Custom Search JSON API for new setup.
7. If no external provider key is configured, return a structured unavailable result rather than pretending search was performed.

## Budget Policy

Default budget:

- max external providers per normal question: 2
- max external calls per normal question: 2
- max external calls for deep research workflow: 4
- SerpAPI is specialty/fallback, not default first provider

Provider free quotas and pricing can change. Agents must treat docs in this file as routing guidance, not as permanent billing truth.

## Product Implication

This keeps the system cost-aware and evidence-aware.

For users, a response can explain:

- internal evidence used;
- external providers planned or used;
- why a provider was chosen;
- whether quota or missing keys prevented external search.

## Engineering Implication

Implement a deterministic provider router before implementing API clients.

The router should output:

- task type;
- provider chain;
- primary provider;
- fallback providers;
- budget policy;
- rationale;
- unavailable providers due to missing API keys.

## Evaluation Implication

Benchmarks should verify:

- needs-web questions produce an external provider route;
- GitHub questions prefer GitHub API before generic web search;
- research-paper questions prefer Exa;
- recent-news questions prefer Brave or Tavily;
- SerpAPI is not used as the first provider unless the task explicitly needs SERP/Scholar/Trends coverage.
