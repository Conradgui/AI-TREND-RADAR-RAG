"""Plan and execute batched external evidence acquisition."""

from __future__ import annotations

from datetime import date

from rag.search_provider_adapters import SearchRequest
from rag.search_provider_routing import build_search_provider_route


DEFAULT_MAX_TOTAL_CALLS = 4
DEFAULT_MAX_RESULTS_PER_CALL = 3


def build_batched_evidence_acquisition_plan(
    relevance_matrix: dict,
    *,
    configured_providers: set[str] | None = None,
    max_total_calls: int = DEFAULT_MAX_TOTAL_CALLS,
    execute: bool = False,
) -> dict:
    """Build a deterministic batch plan from a source relevance matrix."""
    topic = relevance_matrix.get("topic", "")
    reviews = list(relevance_matrix.get("reviews", []) or [])
    gaps = _claim_gaps(topic, reviews)
    tasks = [
        _build_task(gap, configured_providers=configured_providers or set())
        for gap in gaps
    ]
    planned_calls = _planned_call_count(tasks, max_total_calls=max_total_calls)
    return {
        "topic": topic,
        "input_artifact": relevance_matrix.get("artifact", ""),
        "source_relevance_status": relevance_matrix.get("relevance_status", "unknown"),
        "external_api_calls": 0,
        "execution_status": "ready_to_execute" if execute else "planned_not_executed",
        "budget": {
            "free_quota_first": True,
            "max_total_calls": max_total_calls,
            "planned_calls": planned_calls,
            "execute_now": bool(execute),
            "max_results_per_call": DEFAULT_MAX_RESULTS_PER_CALL,
        },
        "claim_gaps": gaps,
        "search_tasks": tasks,
        "notes": [
            "Build the full evidence request set before making provider calls.",
            "Execute as one audited batch when external evidence improves quality or efficiency.",
        ],
    }


async def execute_batched_evidence_acquisition_plan(
    plan: dict,
    registry,
    *,
    max_total_calls: int | None = None,
    max_results_per_call: int | None = None,
) -> dict:
    """Execute the planned provider calls and return a stable evidence artifact."""
    budget = plan.get("budget", {}) or {}
    call_limit = int(max_total_calls or budget.get("max_total_calls") or DEFAULT_MAX_TOTAL_CALLS)
    result_limit = int(max_results_per_call or budget.get("max_results_per_call") or DEFAULT_MAX_RESULTS_PER_CALL)

    executed_calls = 0
    gap_results = []
    all_citations = []

    for task in plan.get("search_tasks", []) or []:
        if executed_calls >= call_limit:
            break
        gap_result = {
            "gap_id": task.get("gap_id", ""),
            "query": task.get("query", ""),
            "task_type": task.get("task_type", ""),
            "needed_source_type": task.get("needed_source_type", ""),
            "attempts": [],
            "citations": [],
        }
        for provider in task.get("available_provider_chain", []) or []:
            if executed_calls >= call_limit:
                break
            request = SearchRequest(
                query=task.get("query", ""),
                task_type=task.get("task_type", ""),
                provider=provider,
                max_results=result_limit,
            )
            provider_result = await registry.search(request)
            citations = list(provider_result.get("citations", []) or [])
            gap_result["attempts"].append({
                "provider": provider,
                "available": provider_result.get("available", False),
                "citation_count": len(citations),
                "raw_results_count": provider_result.get("raw_results_count", 0),
                "errors": provider_result.get("errors", []),
            })
            gap_result["citations"].extend(citations)
            all_citations.extend(citations)
            executed_calls += 1
        gap_result["citation_count"] = len(gap_result["citations"])
        gap_results.append(gap_result)

    return {
        "topic": plan.get("topic", ""),
        "input_artifact": plan.get("input_artifact", ""),
        "source_relevance_status": plan.get("source_relevance_status", "unknown"),
        "execution_status": "executed",
        "executed_at": date.today().isoformat(),
        "external_api_calls": executed_calls,
        "budget": {
            **budget,
            "max_total_calls": call_limit,
            "max_results_per_call": result_limit,
        },
        "claim_gap_results": gap_results,
        "citations": all_citations,
        "citation_count": len(all_citations),
    }


def _claim_gaps(topic: str, reviews: list[dict]) -> list[dict]:
    gaps = []
    for review in reviews:
        label = review.get("relevance_label")
        if label == "weak_context":
            gaps.append({
                "gap_id": f"{_slug(review.get('source', 'source'))}-primary-confirmation",
                "claim_family": "definition_or_background",
                "current_citation_id": review.get("citation_id", ""),
                "current_source": review.get("source", ""),
                "current_relevance": label,
                "needed_source_type": "primary_or_authoritative_technical_reference",
                "query": _definition_query(topic),
                "task_type": "technical_article",
                "priority": "P1",
            })
        elif label == "partial_support":
            gaps.append({
                "gap_id": f"{_slug(review.get('source', 'source'))}-claim-corroboration",
                "claim_family": "evaluation_or_tooling_claim",
                "current_citation_id": review.get("citation_id", ""),
                "current_source": review.get("source", ""),
                "current_relevance": label,
                "needed_source_type": "primary_benchmark_or_vendor_docs",
                "query": _claim_query(topic),
                "task_type": "research_paper",
                "priority": "P1",
            })
        elif label == "irrelevant_context":
            gaps.append({
                "gap_id": f"{_slug(review.get('source', 'source'))}-replacement",
                "claim_family": "irrelevant_external_context",
                "current_citation_id": review.get("citation_id", ""),
                "current_source": review.get("source", ""),
                "current_relevance": label,
                "needed_source_type": "replacement_relevant_source",
                "query": _claim_query(topic),
                "task_type": "recent_web",
                "priority": "P0",
            })

    if not any(review.get("relevance_label") == "direct_support" for review in reviews):
        gaps.insert(0, {
            "gap_id": "missing-direct-support",
            "claim_family": "core_claim_support",
            "current_citation_id": "",
            "current_source": "",
            "current_relevance": "missing",
            "needed_source_type": "direct_primary_or_academic_source",
            "query": _claim_query(topic),
            "task_type": "research_paper",
            "priority": "P0",
        })
    return gaps


def _build_task(gap: dict, *, configured_providers: set[str]) -> dict:
    route = build_search_provider_route(
        {"query": gap["query"], "task_type": gap["task_type"]},
        configured_providers=configured_providers,
    )
    max_providers = route.get("budget_policy", {}).get("max_external_providers", 2)
    return {
        "gap_id": gap["gap_id"],
        "query": gap["query"],
        "task_type": gap["task_type"],
        "needed_source_type": gap["needed_source_type"],
        "priority": gap["priority"],
        "provider_chain": route.get("provider_chain", []),
        "available_provider_chain": route.get("available_provider_chain", [])[:max_providers],
        "fallback_providers": route.get("fallback_providers", [])[:max(0, max_providers - 1)],
        "budget_policy": route.get("budget_policy", {}),
        "rationale": route.get("rationale", ""),
    }


def _planned_call_count(tasks: list[dict], *, max_total_calls: int) -> int:
    planned = 0
    for task in tasks:
        planned += max(1, len(task.get("available_provider_chain", [])))
    return min(planned, max_total_calls)


def _definition_query(topic: str) -> str:
    if topic.strip().casefold() == "rag":
        return "retrieval augmented generation authoritative technical documentation definition"
    return f"{topic} authoritative technical documentation definition"


def _claim_query(topic: str) -> str:
    if topic.strip().casefold() == "rag":
        return "retrieval augmented generation RAG evaluation benchmark graph agentic hybrid retrieval"
    return f"{topic} evaluation benchmark primary source"


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in str(value).lower()).strip("-") or "source"
