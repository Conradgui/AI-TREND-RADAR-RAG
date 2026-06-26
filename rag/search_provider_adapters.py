"""Provider-agnostic adapter interface for future external search clients."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlencode, urlparse

from rag.external_evidence import validate_external_citation
from rag.external_source_quality import apply_excerpt_policy, classify_source_quality, official_lookup_domain_policy
from rag.search_provider_routing import PROVIDER_PROFILES

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
BRAVE_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
EXA_SEARCH_URL = "https://api.exa.ai/search"
GITHUB_REPOSITORY_SEARCH_URL = "https://api.github.com/search/repositories"


@dataclass(frozen=True)
class SearchRequest:
    """Provider-agnostic search request."""

    query: str
    task_type: str
    provider: str
    max_results: int = 5
    include_domains: list[str] = field(default_factory=list)
    exclude_domains: list[str] = field(default_factory=list)


def build_disabled_search_result(request: SearchRequest, reason: str) -> dict:
    """Build a stable unavailable result for a search provider."""
    return {
        "provider": request.provider,
        "available": False,
        "query": request.query,
        "task_type": request.task_type,
        "citations": [],
        "raw_results_count": 0,
        "retrieved_at": date.today().isoformat(),
        "errors": [reason],
    }


def build_tavily_request_for_task(
    query: str,
    task_type: str,
    entities: list[str] | None = None,
    max_results: int = 5,
) -> SearchRequest:
    """Build a Tavily request with task-aware domain policy."""
    include_domains: list[str] = []
    exclude_domains: list[str] = []
    if task_type == "official_source_lookup":
        policy = official_lookup_domain_policy(entities or [])
        include_domains = policy["include_domains"]
        exclude_domains = policy["exclude_domains"]
    return SearchRequest(
        query=query,
        task_type=task_type,
        provider="tavily",
        max_results=max_results,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
    )


class DisabledSearchProviderAdapter:
    """Adapter used until a provider has a real API client."""

    def __init__(self, provider: str, reason: str = "missing_api_key"):
        self.provider = provider
        self.reason = reason

    async def search(self, request: SearchRequest) -> dict:
        return build_disabled_search_result(request, self.reason)


class TavilySearchProviderAdapter:
    """Live Tavily search adapter."""

    def __init__(self, api_key: str, transport=None):
        self.api_key = api_key
        self.transport = transport or _post_json

    async def search(self, request: SearchRequest) -> dict:
        payload = _build_tavily_payload(request)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = self.transport(TAVILY_SEARCH_URL, headers, payload)
        except urllib.error.HTTPError as exc:
            return build_disabled_search_result(request, f"tavily_http_{exc.code}")
        except urllib.error.URLError:
            return build_disabled_search_result(request, "tavily_network_error")
        except Exception:
            return build_disabled_search_result(request, "tavily_request_failed")

        results = response.get("results") or []
        citations = [_tavily_result_to_citation(item, request.task_type) for item in results]
        citations = [citation for citation in citations if not validate_external_citation(citation)]
        errors = [] if len(citations) == len(results) else ["some_results_failed_schema_validation"]
        return {
            "provider": request.provider,
            "available": True,
            "query": request.query,
            "task_type": request.task_type,
            "citations": citations,
            "raw_results_count": len(results),
            "retrieved_at": date.today().isoformat(),
            "errors": errors,
            "usage": response.get("usage", {}),
            "request_id": response.get("request_id", ""),
        }


class BraveSearchProviderAdapter:
    """Live Brave web search adapter."""

    def __init__(self, api_key: str, transport=None):
        self.api_key = api_key
        self.transport = transport or _get_json

    async def search(self, request: SearchRequest) -> dict:
        params = _build_brave_params(request)
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        try:
            response = self.transport(BRAVE_WEB_SEARCH_URL, headers, params)
        except urllib.error.HTTPError as exc:
            return build_disabled_search_result(request, f"brave_http_{exc.code}")
        except urllib.error.URLError:
            return build_disabled_search_result(request, "brave_network_error")
        except Exception:
            return build_disabled_search_result(request, "brave_request_failed")

        results = response.get("web", {}).get("results") or []
        citations = [_brave_result_to_citation(item, request.task_type) for item in results]
        citations = [citation for citation in citations if not validate_external_citation(citation)]
        errors = [] if len(citations) == len(results) else ["some_results_failed_schema_validation"]
        return {
            "provider": request.provider,
            "available": True,
            "query": request.query,
            "task_type": request.task_type,
            "citations": citations,
            "raw_results_count": len(results),
            "retrieved_at": date.today().isoformat(),
            "errors": errors,
            "usage": {},
            "request_id": "",
        }


class ExaSearchProviderAdapter:
    """Live Exa search adapter."""

    def __init__(self, api_key: str, transport=None):
        self.api_key = api_key
        self.transport = transport or _post_json

    async def search(self, request: SearchRequest) -> dict:
        payload = _build_exa_payload(request)
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        try:
            response = self.transport(EXA_SEARCH_URL, headers, payload)
        except urllib.error.HTTPError as exc:
            return build_disabled_search_result(request, f"exa_http_{exc.code}")
        except urllib.error.URLError:
            return build_disabled_search_result(request, "exa_network_error")
        except Exception:
            return build_disabled_search_result(request, "exa_request_failed")

        results = response.get("results") or []
        citations = [_exa_result_to_citation(item, request.task_type) for item in results]
        citations = [citation for citation in citations if not validate_external_citation(citation)]
        errors = [] if len(citations) == len(results) else ["some_results_failed_schema_validation"]
        return {
            "provider": request.provider,
            "available": True,
            "query": request.query,
            "task_type": request.task_type,
            "citations": citations,
            "raw_results_count": len(results),
            "retrieved_at": date.today().isoformat(),
            "errors": errors,
            "usage": {"costDollars": response.get("costDollars", {})},
            "request_id": response.get("requestId", ""),
        }


class GitHubSearchProviderAdapter:
    """Live GitHub repository search adapter."""

    def __init__(self, api_key: str, transport=None):
        self.api_key = api_key
        self.transport = transport or _get_json

    async def search(self, request: SearchRequest) -> dict:
        params = _build_github_repository_params(request)
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            response = self.transport(GITHUB_REPOSITORY_SEARCH_URL, headers, params)
        except urllib.error.HTTPError as exc:
            return build_disabled_search_result(request, f"github_http_{exc.code}")
        except urllib.error.URLError:
            return build_disabled_search_result(request, "github_network_error")
        except Exception:
            return build_disabled_search_result(request, "github_request_failed")

        results = response.get("items") or []
        citations = [_github_repo_to_citation(item, request.task_type) for item in results]
        citations = [citation for citation in citations if not validate_external_citation(citation)]
        errors = [] if len(citations) == len(results) else ["some_results_failed_schema_validation"]
        return {
            "provider": request.provider,
            "available": True,
            "query": request.query,
            "task_type": request.task_type,
            "citations": citations,
            "raw_results_count": len(results),
            "retrieved_at": date.today().isoformat(),
            "errors": errors,
            "usage": {
                "total_count": response.get("total_count"),
                "incomplete_results": response.get("incomplete_results"),
            },
            "request_id": "",
        }


class SearchProviderRegistry:
    """Registry that resolves provider names to adapters."""

    def __init__(
        self,
        configured_provider_keys: dict[str, str] | None = None,
        transports: dict[str, object] | None = None,
    ):
        self.configured_provider_keys = configured_provider_keys or {}
        self.transports = transports or {}

    async def search(self, request: SearchRequest) -> dict:
        if request.provider not in PROVIDER_PROFILES:
            return build_disabled_search_result(request, "unknown_provider")

        api_key = self.configured_provider_keys.get(request.provider)
        if not api_key:
            return await DisabledSearchProviderAdapter(request.provider).search(request)

        if request.provider == "tavily":
            return await TavilySearchProviderAdapter(
                api_key,
                transport=self.transports.get("tavily"),
            ).search(request)
        if request.provider == "brave":
            return await BraveSearchProviderAdapter(
                api_key,
                transport=self.transports.get("brave"),
            ).search(request)
        if request.provider == "exa":
            return await ExaSearchProviderAdapter(
                api_key,
                transport=self.transports.get("exa"),
            ).search(request)
        if request.provider == "github":
            return await GitHubSearchProviderAdapter(
                api_key,
                transport=self.transports.get("github"),
            ).search(request)

        return await DisabledSearchProviderAdapter(
            request.provider,
            reason="provider_client_not_implemented",
        ).search(request)


def _build_tavily_payload(request: SearchRequest) -> dict:
    payload = {
        "query": request.query,
        "search_depth": "advanced",
        "topic": "news",
        "max_results": request.max_results,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
        "include_favicon": False,
        "include_usage": True,
        "days": 10,  # 只搜索近10天的内容
    }
    if request.include_domains:
        payload["include_domains"] = request.include_domains
    if request.exclude_domains:
        payload["exclude_domains"] = request.exclude_domains
    return payload


def _build_brave_params(request: SearchRequest) -> dict:
    params = {
        "q": request.query,
        "count": min(request.max_results, 20),
        "safesearch": "moderate",
        "text_decorations": "false",
        "extra_snippets": "true",
    }
    # 默认添加时间过滤：过去10天
    params["freshness"] = "pw"
    return params


def _build_exa_payload(request: SearchRequest) -> dict:
    return {
        "query": request.query,
        "numResults": request.max_results,
        "contents": {
            "highlights": True,
            "summary": True,
        },
    }


def _build_github_repository_params(request: SearchRequest) -> dict:
    return {
        "q": _build_github_query(request.query),
        "sort": "stars",
        "order": "desc",
        "per_page": min(request.max_results, 100),
    }


def _build_github_query(query: str) -> str:
    cleaned = str(query or "").strip()
    if "archived:" not in cleaned:
        cleaned = f"{cleaned} archived:false"
    return cleaned


def _tavily_result_to_citation(item: dict, task_type: str) -> dict:
    url = item.get("url", "")
    quality = classify_source_quality(url, task_type=task_type, entities=_infer_entities(item.get("title", ""), url))
    return {
        "evidence_type": "external",
        "provider": "tavily",
        "source": _source_from_url(url),
        "source_type": "web",
        "title": item.get("title", ""),
        "url": url,
        "retrieved_at": date.today().isoformat(),
        "excerpt": apply_excerpt_policy(item.get("content", ""), quality),
        "score": item.get("score"),
        **quality,
    }


def _brave_result_to_citation(item: dict, task_type: str) -> dict:
    url = item.get("url", "")
    quality = classify_source_quality(url, task_type=task_type, entities=_infer_entities(item.get("title", ""), url))
    excerpt_parts = [item.get("description", "")]
    excerpt_parts.extend(item.get("extra_snippets") or [])
    return {
        "evidence_type": "external",
        "provider": "brave",
        "source": _source_from_url(url),
        "source_type": "web",
        "title": item.get("title", ""),
        "url": url,
        "retrieved_at": date.today().isoformat(),
        "excerpt": apply_excerpt_policy(" ".join(excerpt_parts), quality),
        "score": item.get("rank"),
        **quality,
    }


def _exa_result_to_citation(item: dict, task_type: str) -> dict:
    url = item.get("url", "")
    quality = classify_source_quality(url, task_type=task_type, entities=_infer_entities(item.get("title", ""), url))
    excerpt = _first_non_empty([
        item.get("summary", ""),
        " ".join(item.get("highlights") or []),
        item.get("text", ""),
    ])
    return {
        "evidence_type": "external",
        "provider": "exa",
        "source": _source_from_url(url),
        "source_type": "web",
        "title": item.get("title", ""),
        "url": url,
        "retrieved_at": date.today().isoformat(),
        "excerpt": apply_excerpt_policy(excerpt, quality),
        "score": (item.get("highlightScores") or [None])[0],
        "published_at": item.get("publishedDate", ""),
        **quality,
    }


def _github_repo_to_citation(item: dict, task_type: str) -> dict:
    url = item.get("html_url", "")
    quality = classify_source_quality(url, task_type=task_type, entities=["GitHub"])
    excerpt = (
        f"{item.get('description') or ''} "
        f"Stars: {item.get('stargazers_count', 0)}. "
        f"Forks: {item.get('forks_count', 0)}. "
        f"Language: {item.get('language') or 'unknown'}. "
        f"Updated at: {item.get('updated_at', '')}."
    )
    return {
        "evidence_type": "external",
        "provider": "github",
        "source": "github.com",
        "source_type": "api",
        "title": item.get("full_name", ""),
        "url": url,
        "retrieved_at": date.today().isoformat(),
        "excerpt": apply_excerpt_policy(excerpt, quality),
        "score": item.get("stargazers_count"),
        "published_at": item.get("created_at", ""),
        **quality,
    }


def _source_from_url(url: str) -> str:
    host = urlparse(url).netloc
    return host or "Tavily Search"


def _infer_entities(title: str, url: str) -> list[str]:
    lowered = f"{title or ''} {url or ''}".lower()
    entities = []
    for entity in ("Google", "Anthropic", "OpenAI", "GitHub"):
        if entity.lower() in lowered:
            entities.append(entity)
    return entities


def _first_non_empty(values: list[str]) -> str:
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned:
            return cleaned
    return ""


def _post_json(url: str, headers: dict, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str, headers: dict, params: dict) -> dict:
    query = urlencode(params)
    separator = "&" if "?" in url else "?"
    req = urllib.request.Request(f"{url}{separator}{query}", headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))
