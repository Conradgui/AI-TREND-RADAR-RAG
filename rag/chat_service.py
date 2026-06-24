"""Chat response orchestration without web framework dependencies."""

from __future__ import annotations

from rag.answer_policy import apply_answer_policy, build_answer_policy, mark_external_evidence_used
from rag.citations import evidence_insufficient_answer, retrieve_citations
from rag.config import get_configured_search_providers
from rag.deep_fetch_policy import apply_deep_fetch_policy
from rag.query_understanding import analyze_query
from rag.retrieval_planning import build_metadata_filter, load_latest_corpus_date
from rag.search_provider_adapters import SearchRequest, build_tavily_request_for_task
from rag.source_review import build_source_review, format_source_review_for_prompt
from rag.tool_routing import build_tool_route, format_tool_route_for_prompt, infer_search_task_type

DISTRACTING_INTERNAL_TERMS = ("diffusiongemma", "glm", "vue3", "乱码", "coding assistant")


def _extract_ai_answer(result: dict) -> str:
    messages = result.get("messages", [])
    ai_messages = [m for m in messages if getattr(m, "type", None) == "ai"]
    return ai_messages[-1].content if ai_messages else "No response generated."


def _build_evidence_context(citations: list[dict], answer_policy: dict, tool_route: dict, source_review: dict) -> str:
    lines = [
        "你必须基于以下 AI Trend Radar RAG 检索证据回答。",
        "如果证据不足，请明确说明不足，不要编造。",
        "回答中请自然提及关键日期和来源。",
        "",
        "回答策略:",
        f"- 证据边界: {answer_policy.get('evidence_boundary', '')}",
        f"- 用户可见说明: {answer_policy.get('disclosure', '')}",
        f"- 执行要求: {answer_policy.get('instruction', '')}",
        "",
        format_tool_route_for_prompt(tool_route),
        "",
        format_source_review_for_prompt(source_review),
        "",
        "检索证据:",
    ]
    for index, citation in enumerate(citations, 1):
        lines.append(_format_citation_for_prompt(index, citation))
    return "\n".join(lines)


def _format_citation_for_prompt(index: int, citation: dict) -> str:
    evidence_type = citation.get("evidence_type", "internal")
    if evidence_type == "external":
        deep_fetch = citation.get("deep_fetch") or {}
        deep_fetch_line = ""
        if deep_fetch.get("ok"):
            deep_fetch_line = (
                f"\n深度抓取: ok | 标题: {deep_fetch.get('title', '')} | "
                f"抓取时间: {deep_fetch.get('fetched_at', '')}\n"
                f"深度摘录: {deep_fetch.get('text_excerpt', '')}"
            )
        elif deep_fetch:
            deep_fetch_line = f"\n深度抓取: failed | 原因: {deep_fetch.get('error', '')}"
        return (
            f"[{index}] 类型: 外部证据 | 来源: {citation.get('source', '')} | "
            f"质量: {citation.get('source_quality', '')}/{citation.get('quality_score', '')} | "
            f"标题: {citation.get('title', '')} | URL: {citation.get('url', '')} | "
            f"检索日期: {citation.get('retrieved_at', '')}\n"
            f"摘录: {citation.get('excerpt', '')}"
            f"{deep_fetch_line}"
        )
    return (
        f"[{index}] 类型: 内部语料 | 日期: {citation.get('date', '')} | 来源: {citation.get('source', '')} | "
        f"标题: {citation.get('title', '')} | citation_id: {citation.get('citation_id', '')}\n"
        f"摘录: {citation.get('excerpt', '')}"
    )


async def build_chat_response(
    agent,
    retriever,
    message: str,
    history: list[dict],
    latest_corpus_date: str | None = None,
    external_search_registry=None,
    configured_search_providers: set[str] | None = None,
    external_deep_fetcher=None,
) -> dict:
    """Build a grounded chat response with retrieval-derived citations."""
    query_plan = analyze_query(message)
    corpus_date = latest_corpus_date or load_latest_corpus_date()
    metadata_filter = build_metadata_filter(query_plan, corpus_date)
    query_understanding = query_plan.to_dict()
    query_understanding["latest_corpus_date"] = corpus_date
    query_understanding["metadata_filter"] = metadata_filter

    citations = (
        await retrieve_citations(
            retriever,
            query_plan.retrieval_query,
            k=query_plan.top_k,
            where=metadata_filter,
        )
        if retriever
        else []
    )
    if not citations:
        answer_policy = build_answer_policy(query_plan, citations)
        query_understanding["answer_policy"] = answer_policy
        query_understanding["tool_routing"] = build_tool_route(
            query_plan,
            answer_policy,
            citations,
            configured_search_providers=(
                configured_search_providers
                if configured_search_providers is not None
                else get_configured_search_providers()
            ),
        )
        return {
            "answer": evidence_insufficient_answer(message),
            "citations": [],
            "query_understanding": query_understanding,
        }

    answer_policy = build_answer_policy(query_plan, citations)
    tool_route = build_tool_route(
        query_plan,
        answer_policy,
        citations,
        configured_search_providers=(
            configured_search_providers
            if configured_search_providers is not None
            else get_configured_search_providers()
        ),
    )
    external_search = await _maybe_search_external(
        query_plan,
        tool_route,
        external_search_registry,
    )
    external_citations = external_search.get("citations", [])
    if external_citations:
        external_citations, deep_fetch_trace = apply_deep_fetch_policy(
            external_citations,
            fetcher=external_deep_fetcher,
            enabled=external_deep_fetcher is not None,
        )
        citations = [*citations, *external_citations]
        citations = _refine_citations_for_answer(citations, query_plan, external_citations)
        answer_policy = mark_external_evidence_used(answer_policy, external_citations)
        tool_route = _mark_external_tool_executed(tool_route, external_search, deep_fetch_trace)
    else:
        deep_fetch_trace = {
            "attempted": False,
            "reason": "no_external_citations",
            "selected_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "targets": [],
        }

    source_review = build_source_review(citations)
    query_understanding["answer_policy"] = answer_policy
    query_understanding["tool_routing"] = tool_route
    query_understanding["external_search"] = external_search
    query_understanding["deep_fetch"] = deep_fetch_trace
    query_understanding["source_review"] = source_review

    normalized_history = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in history
    ]
    messages = [
        {"role": "system", "content": _build_evidence_context(citations, answer_policy, tool_route, source_review)},
        *normalized_history,
        {"role": "user", "content": message},
    ]
    result = await agent.ainvoke({"messages": messages})

    return {
        "answer": apply_answer_policy(_extract_ai_answer(result), answer_policy),
        "citations": citations,
        "query_understanding": query_understanding,
    }


def _refine_citations_for_answer(citations: list[dict], query_plan, external_citations: list[dict]) -> list[dict]:
    deduped = _dedupe_citations_by_semantic_key(citations)
    if not external_citations or not getattr(query_plan, "needs_web_search", False):
        return deduped

    external = [citation for citation in deduped if citation.get("evidence_type") == "external"]
    internal = [citation for citation in deduped if citation.get("evidence_type", "internal") == "internal"]
    focused_internal = [
        citation for citation in internal
        if _is_focused_internal_context(citation, query_plan)
    ]
    if focused_internal:
        return [*focused_internal[:2], *external]
    return external


def _dedupe_citations_by_semantic_key(citations: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for citation in citations:
        key = _citation_semantic_key(citation)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(citation)
    return deduped


def _citation_semantic_key(citation: dict) -> str:
    return "|".join(
        str(citation.get(field, "")).casefold().strip()
        for field in ("title", "source", "url")
    )


def _is_focused_internal_context(citation: dict, query_plan) -> bool:
    text = " ".join(
        str(citation.get(field, ""))
        for field in ("title", "source", "excerpt", "category")
    ).casefold()
    if any(term in text for term in DISTRACTING_INTERNAL_TERMS):
        return False

    focus_terms = [
        str(term).casefold()
        for term in [
            *getattr(query_plan, "entities", []),
            *getattr(query_plan, "topics", []),
        ]
        if str(term).strip()
    ]
    return any(term in text for term in focus_terms)


async def _maybe_search_external(query_plan, tool_route: dict, external_search_registry) -> dict:
    if not external_search_registry or not getattr(query_plan, "needs_web_search", False):
        return {"attempted": False, "citations": []}

    provider_route = tool_route.get("provider_route", {})
    providers = provider_route.get("available_provider_chain") or []
    attempted = []
    best_non_official_result = None
    for provider in providers[: provider_route.get("budget_policy", {}).get("max_external_providers", 2)]:
        request = _build_external_search_request(provider, query_plan)
        result = await external_search_registry.search(request)
        attempted.append({
            "provider": provider,
            "available": result.get("available", False),
            "errors": result.get("errors", []),
            "citation_count": len(result.get("citations", [])),
        })
        if result.get("available") and result.get("citations"):
            if (
                provider_route.get("task_type") == "official_source_lookup"
                and not _has_official_external_citation(result["citations"])
            ):
                best_non_official_result = best_non_official_result or result
                continue
            return {
                "attempted": True,
                "provider": provider,
                "attempts": attempted,
                "citations": result["citations"],
                "raw_results_count": result.get("raw_results_count", 0),
                "errors": result.get("errors", []),
            }

    if best_non_official_result:
        return {
            "attempted": True,
            "provider": best_non_official_result.get("provider"),
            "attempts": attempted,
            "citations": best_non_official_result["citations"],
            "raw_results_count": best_non_official_result.get("raw_results_count", 0),
            "errors": [
                *best_non_official_result.get("errors", []),
                "official_source_lookup_without_official_citation",
            ],
        }

    return {
        "attempted": bool(attempted),
        "provider": attempted[-1]["provider"] if attempted else None,
        "attempts": attempted,
        "citations": [],
        "errors": ["external_search_no_citations"] if attempted else ["external_search_no_provider"],
    }


def _has_official_external_citation(citations: list[dict]) -> bool:
    return any(citation.get("source_quality") == "official" for citation in citations)


def _build_external_search_request(provider: str, query_plan):
    task_type = infer_search_task_type(query_plan)
    query = _build_external_search_query(query_plan, task_type)
    if provider == "tavily":
        return build_tavily_request_for_task(
            query=query,
            task_type=task_type,
            entities=getattr(query_plan, "entities", []),
            max_results=2,
        )
    return SearchRequest(
        query=query,
        task_type=task_type,
        provider=provider,
        max_results=2,
    )


def _build_external_search_query(query_plan, task_type: str) -> str:
    """Build a concise web-search query instead of sending the full user question."""
    topics = list(getattr(query_plan, "topics", []) or [])
    entities = list(getattr(query_plan, "entities", []) or [])
    sources = list(getattr(query_plan, "sources", []) or [])

    if task_type == "official_source_lookup":
        return _join_query_terms([*entities, *topics, "knowledge framework", "user preference"])
    if task_type == "research_paper":
        return _join_query_terms([*topics, "evolution", "papers", "survey"])
    if task_type == "github_repo":
        return _join_query_terms([*sources, *topics, "AI", "trending repositories"])
    if task_type == "recent_web":
        return _join_query_terms([*entities, *topics, "latest update"])
    return _join_query_terms([*entities, *topics]) or getattr(query_plan, "retrieval_query", "")


def _join_query_terms(terms: list[str]) -> str:
    seen = set()
    query_terms = []
    for term in terms:
        cleaned = str(term or "").strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            query_terms.append(cleaned)
    return " ".join(query_terms)


def _mark_external_tool_executed(tool_route: dict, external_search: dict, deep_fetch_trace: dict | None = None) -> dict:
    updated = dict(tool_route)
    updated["status"] = "external_executed"
    updated["external_tools_available"] = True
    updated["fallback"] = "已获取外部证据；回答仍需区分内部语料与外部证据。"
    deep_fetch_trace = deep_fetch_trace or {}
    steps = []
    for step in tool_route.get("steps", []):
        if step.get("tool") == "web_search":
            steps.append({
                "tool": "web_search",
                "state": "executed",
                "reason": f"External search returned {len(external_search.get('citations', []))} citation(s).",
            })
        elif step.get("tool") == "fetch_url":
            if deep_fetch_trace.get("attempted"):
                steps.append({
                    "tool": "fetch_url",
                    "state": "executed",
                    "reason": (
                        f"Deep fetch selected {deep_fetch_trace.get('selected_count', 0)} URL(s); "
                        f"{deep_fetch_trace.get('success_count', 0)} succeeded, "
                        f"{deep_fetch_trace.get('failure_count', 0)} failed."
                    ),
                })
            else:
                steps.append({
                    "tool": "fetch_url",
                    "state": "not_executed",
                    "reason": f"Deep fetch not executed: {deep_fetch_trace.get('reason', 'disabled_or_not_configured')}.",
                })
        elif step.get("tool") == "compare_internal_and_external":
            steps.append({
                "tool": "compare_internal_and_external",
                "state": "prompt_level",
                "reason": "Comparison is delegated to the grounded answer prompt.",
            })
        else:
            steps.append(step)
    updated["steps"] = steps
    return updated
