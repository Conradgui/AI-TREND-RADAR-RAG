"""Deterministic external search provider routing."""

from __future__ import annotations


PROVIDER_PROFILES = {
    "brave": {
        "label": "Brave Search API",
        "best_for": ["recent_web", "broad_serp"],
        "budget_role": "free_quota_friendly_default",
    },
    "tavily": {
        "label": "Tavily Search",
        "best_for": ["official_source_lookup", "recent_web"],
        "budget_role": "agent_search_default",
    },
    "exa": {
        "label": "Exa Search",
        "best_for": ["research_paper", "technical_article"],
        "budget_role": "research_specialist",
    },
    "serpapi": {
        "label": "SerpAPI",
        "best_for": ["broad_serp", "google_scholar", "google_trends"],
        "budget_role": "specialty_fallback",
    },
    "github": {
        "label": "GitHub REST API",
        "best_for": ["github_repo"],
        "budget_role": "specialized_free_authenticated",
    },
}

ROUTES_BY_TASK_TYPE = {
    "official_source_lookup": ["tavily", "brave", "serpapi"],
    "research_paper": ["exa", "tavily", "serpapi"],
    "technical_article": ["exa", "tavily", "brave"],
    "recent_web": ["brave", "tavily", "exa"],
    "github_repo": ["github", "brave", "tavily"],
    "broad_serp": ["brave", "serpapi", "tavily"],
    "google_scholar": ["serpapi", "exa", "tavily"],
    "google_trends": ["serpapi", "brave", "tavily"],
}

DEFAULT_PROVIDER_CHAIN = ["brave", "tavily", "exa", "serpapi"]


def build_search_provider_route(
    search_task: dict,
    configured_providers: set[str] | None = None,
) -> dict:
    """Build a provider route for future external search without calling providers."""
    configured = configured_providers if configured_providers is not None else set()
    task_type = search_task.get("task_type") or "broad_serp"
    provider_chain = ROUTES_BY_TASK_TYPE.get(task_type, DEFAULT_PROVIDER_CHAIN)
    available = [provider for provider in provider_chain if provider in configured]
    unavailable = [provider for provider in provider_chain if provider not in configured]
    primary = available[0] if available else None

    return {
        "query": search_task.get("query", ""),
        "task_type": task_type,
        "primary_provider": primary,
        "provider_chain": provider_chain,
        "available_provider_chain": available,
        "fallback_providers": available[1:],
        "unavailable_providers": unavailable,
        "budget_policy": _budget_policy(task_type),
        "rationale": _rationale(task_type, provider_chain),
    }


def _budget_policy(task_type: str) -> dict:
    if task_type in {"research_paper", "google_scholar", "google_trends"}:
        return {
            "free_quota_first": True,
            "max_external_providers": 2,
            "max_external_calls": 4,
            "serpapi_role": "specialty_provider",
        }
    return {
        "free_quota_first": True,
        "max_external_providers": 2,
        "max_external_calls": 2,
        "serpapi_role": "fallback_not_default",
    }


def _rationale(task_type: str, provider_chain: list[str]) -> str:
    if task_type == "research_paper":
        return "research tasks prefer Exa for AI-native research/paper search, then Tavily, then SerpAPI."
    if task_type == "recent_web":
        return "recent web tasks prefer Brave for fresh broad web search, then Tavily."
    if task_type == "github_repo":
        return "GitHub repository tasks prefer the GitHub API before generic web search."
    if task_type == "official_source_lookup":
        return "official source lookup prefers Tavily for domain-constrained search, then Brave."
    return f"{task_type} uses provider chain: {', '.join(provider_chain)}."
