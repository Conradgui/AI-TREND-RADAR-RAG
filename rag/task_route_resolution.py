"""Resolve a single task route from non-destructive Query Signals."""

from __future__ import annotations

from dataclasses import dataclass

from rag.query_signal_extraction import QuerySignals


@dataclass(frozen=True)
class RouteDecision:
    primary_task_family: str
    supporting_task_families: tuple[str, ...]
    answer_mode: str
    route_confidence: float
    ambiguities: tuple[str, ...]


def resolve_task_route(signals: QuerySignals) -> RouteDecision:
    """Choose by user success criteria, not by the retrieval tool to be used."""
    ambiguities = list(signals.ambiguities)

    if signals.locatable_object:
        supporting = ("evidence_research",) if (
            signals.explanation_request or signals.comparison_request or signals.deep_research_request
        ) else ()
        return RouteDecision(
            primary_task_family="item_navigation",
            supporting_task_families=supporting,
            answer_mode="exact_item" if signals.exact_locator and not ambiguities else "item_disambiguation",
            route_confidence=1.0 if not ambiguities else 0.55,
            ambiguities=tuple(ambiguities),
        )

    if signals.verification_request:
        supporting = ("evidence_research",) if (
            signals.explanation_request or "是否说明" in signals.original_query
        ) else ()
        return RouteDecision(
            primary_task_family="claim_verification",
            supporting_task_families=supporting,
            answer_mode="verification_verdict",
            route_confidence=0.92,
            ambiguities=tuple(ambiguities),
        )

    if signals.temporal_structure or signals.relation_structure:
        query = signals.original_query
        if signals.relation_structure and signals.temporal_structure:
            if "格局" in query and any(term in query for term in ("形成", "重排", "竞争", "比较")):
                answer_mode = "cross_sectional_trend"
            elif any(term in query for term in ("按时间", "路线迁移", "关键节点")) or (
                "从" in query and ("到" in query or "至" in query)
            ):
                answer_mode = "timeline"
            else:
                answer_mode = "relation"
        elif signals.relation_structure:
            answer_mode = "cross_sectional_trend" if (
                "格局" in query and any(term in query for term in ("形成", "重排", "竞争", "比较"))
            ) else "relation"
        elif "格局" in query or "技术路线" in query:
            answer_mode = "cross_sectional_trend"
        elif "关注点" in query or "随日期" in query:
            answer_mode = "longitudinal_trend"
        else:
            answer_mode = "timeline"
        supporting = ("evidence_research",) if signals.explanation_request or (
            signals.comparison_request and signals.relation_structure
        ) else ()
        if signals.comparison_request and signals.original_query.lstrip().startswith("比较"):
            supporting = ("evidence_research",)
        elif "最近" in signals.original_query:
            supporting = tuple(dict.fromkeys((*supporting, "trend_discovery")))
        return RouteDecision(
            primary_task_family="temporal_relation_exploration",
            supporting_task_families=supporting,
            answer_mode=answer_mode,
            route_confidence=0.88,
            ambiguities=tuple(ambiguities),
        )

    if signals.news_discovery:
        supporting = ("claim_verification",) if "还没被官方确认" in signals.original_query else ()
        return RouteDecision(
            primary_task_family="trend_discovery",
            supporting_task_families=supporting,
            answer_mode="trend_clusters" if "热门趋势" in signals.original_query else "important_news",
            route_confidence=0.9,
            ambiguities=tuple(ambiguities),
        )

    answer_mode = "comparison" if signals.comparison_request else (
        "deep_research" if signals.deep_research_request else "explanation"
    )
    if signals.comparison_request and "产品路线" in signals.original_query:
        supporting = ("temporal_relation_exploration",)
    elif signals.deep_research_request and "是否正在" in signals.original_query:
        supporting = ("claim_verification",)
    else:
        supporting = ()
    ambiguities = list(ambiguities)
    vague_reference = any(term in signals.original_query for term in ("这个", "这两个", "它", "那个"))
    has_concrete_reference = signals.has_concrete_subject or bool(signals.resolved_references)
    if not signals.intent_signals or (vague_reference and not has_concrete_reference):
        ambiguities.append("request lacks a concrete subject or success criterion")
    return RouteDecision(
        primary_task_family="evidence_research",
        supporting_task_families=supporting,
        answer_mode=answer_mode,
        route_confidence=0.82 if signals.intent_signals and not ambiguities else 0.3,
        ambiguities=tuple(ambiguities),
    )
