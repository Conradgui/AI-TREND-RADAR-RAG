"""Task-aware retrieval seam for auditable Evidence Records."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations

from rag.citations import build_citations, retrieve_citations_with_status
from rag.entity_identity import canonical_entity_ids
from rag.graph_question_planning import build_graph_question_plans
from rag.graph_reasoning_service import (
    build_entity_relation_citation,
    build_entity_relation_evidence,
    build_graph_reasoning_citation,
    build_graph_reasoning_evidence,
)
from rag.query_understanding import QueryPlan, analyze_query
from rag.retrieval_planning import build_metadata_filter
from rag.retriever.lexical_store import normalize_lexical_text
from rag.route_contract_validation import (
    RouteContractReunderstandingRequired,
    validate_route_contract_for_retrieval,
)


@dataclass(frozen=True)
class ResearchRequest:
    """What a caller must provide to retrieve evidence for one user request."""

    question: str
    latest_corpus_date: str | None = None
    limit: int = 10
    context: dict = field(default_factory=dict)
    route_contract: dict | None = None


@dataclass(frozen=True)
class EvidenceBundle:
    """Evidence Records and an auditable account of how they were selected."""

    status: str
    task_family: str
    records: list[dict] = field(default_factory=list)
    background_records: list[dict] = field(default_factory=list)
    unverified_records: list[dict] = field(default_factory=list)
    analysis: object | None = None
    query_plan: dict = field(default_factory=dict)
    trace: dict = field(default_factory=dict)
    error_code: str = ""
    elapsed_ms: float = 0.0


class EvidenceRetrievalGateway:
    """Hide task routing and retrieval adapters behind one small interface."""

    def __init__(self, retriever, structured_store=None, graph_driver=None):
        self.retriever = retriever
        self.structured_store = structured_store
        self.graph_driver = graph_driver

    async def retrieve(self, request: ResearchRequest) -> EvidenceBundle:
        started_at = time.perf_counter()
        try:
            plan, route_trace = _plan_for_request(request)
        except RouteContractReunderstandingRequired as exc:
            return EvidenceBundle(
                status="clarification_required",
                task_family=str((request.route_contract or {}).get("primary_task_family") or ""),
                trace={
                    "path": "contract_preflight",
                    "route_source": "route_contract_v2",
                    "shadow": True,
                    "reason": str(exc),
                },
                error_code="route_contract_reunderstanding_required",
                elapsed_ms=(time.perf_counter() - started_at) * 1000,
            )

        if _is_generic_trend_plan(plan):
            trend = self._discover_trends(request, plan)
            if trend is not None:
                records, trace, error_code = trend
                return EvidenceBundle(
                    status="error" if error_code else ("ready" if records else "empty"),
                    task_family="trend_discovery",
                    records=records,
                    analysis=plan,
                    query_plan=plan.to_dict(),
                    trace={**trace, **route_trace},
                    error_code=error_code,
                    elapsed_ms=(time.perf_counter() - started_at) * 1000,
                )

        navigation_hits = self._navigation_hits(request, plan)
        if navigation_hits or route_trace.get("primary_task_family") == "item_navigation":
            records = build_citations(navigation_hits, max_citations=request.limit)
            return EvidenceBundle(
                status="ready" if records else "empty",
                task_family="item_navigation",
                records=records,
                analysis=plan,
                query_plan=plan.to_dict(),
                trace={
                    "path": "navigator",
                    **route_trace,
                    "candidate_count": len(navigation_hits),
                },
                elapsed_ms=(time.perf_counter() - started_at) * 1000,
            )

        if _is_focused_important_news_plan(plan):
            trend = self._discover_trends(request, plan, important_news=True)
            if trend is not None:
                records, trace, error_code = trend
                return EvidenceBundle(
                    status="error" if error_code else ("ready" if records else "empty"),
                    task_family="trend_discovery",
                    records=records,
                    background_records=trace.pop("background_records", []),
                    unverified_records=trace.pop("unverified_records", []),
                    analysis=plan,
                    query_plan=plan.to_dict(),
                    trace={**trace, **route_trace},
                    error_code=error_code,
                    elapsed_ms=(time.perf_counter() - started_at) * 1000,
                )

        outcome = await retrieve_citations_with_status(
            self.retriever,
            plan.retrieval_query,
            k=request.limit,
            where=build_metadata_filter(plan, request.latest_corpus_date),
            prefer_recent=plan.time_window.get("label") == "recent_corpus_first",
            latest_date=request.latest_corpus_date,
            graph_requirement=_effective_graph_requirement(plan),
        )
        task_family = route_trace.get("primary_task_family") or task_family_for_plan(plan)
        records, entity_filter_mode = _focused_records(outcome.citations, plan, task_family)
        graph_trace = {"status": "not_required"}
        if task_family in {
            "timeline", "relation_exploration", "temporal_relation_exploration"
        }:
            records, graph_trace = await self._append_graph_evidence(
                request, plan, records
            )
            if graph_trace["status"] == "error":
                return EvidenceBundle(
                    status="partial_error",
                    task_family=task_family,
                    records=records,
                    analysis=plan,
                    query_plan=plan.to_dict(),
                    trace={
                        "path": "evidence_search",
                        **route_trace,
                        "graph_evidence": graph_trace,
                    },
                    error_code="required_graph_evidence_unavailable",
                    elapsed_ms=(time.perf_counter() - started_at) * 1000,
                )
        recovered_required_graph = (
            outcome.status == "partial_error"
            and graph_trace.get("status") == "ready"
            and outcome.error_code == "required_graph_unavailable"
        )
        final_status = "degraded" if recovered_required_graph else outcome.status
        final_error_code = "" if recovered_required_graph else outcome.error_code
        return EvidenceBundle(
            status="empty" if final_status == "ready" and not records else final_status,
            task_family=task_family,
            records=records,
            analysis=plan,
            query_plan=plan.to_dict(),
            trace={
                "path": "evidence_search",
                **route_trace,
                "channel_status": outcome.channel_status,
                "pre_filter_count": len(outcome.citations),
                "focused_count": len(records),
                "entity_filter_mode": entity_filter_mode,
                "graph_evidence": graph_trace,
            },
            error_code=final_error_code,
            elapsed_ms=(time.perf_counter() - started_at) * 1000,
        )


    async def _append_graph_evidence(self, request, plan, records):
        graph_plans = build_graph_question_plans(request.question, query_plan=plan)
        if not graph_plans:
            return records, {
                "status": "error",
                "error_code": "graph_question_not_plannable",
            }
        if self.graph_driver is None:
            return records, {"status": "error", "error_code": "graph_driver_unavailable"}
        citations = []
        evidence_rows = []
        for graph_plan in graph_plans:
            try:
                evidence = await build_graph_reasoning_evidence(self.graph_driver, graph_plan)
            except Exception as exc:
                return records, {"status": "error", "error_code": type(exc).__name__}
            evidence_rows.append(evidence)
            citations.append(build_graph_reasoning_citation(evidence))
        relation_rows = []
        for left_plan, right_plan in combinations(graph_plans, 2):
            try:
                relation = await build_entity_relation_evidence(
                    self.graph_driver, left_plan, right_plan
                )
            except Exception as exc:
                return records, {"status": "error", "error_code": type(exc).__name__}
            relation_rows.append(relation)
            citations.append(build_entity_relation_citation(relation))
        return [*records, *citations], {
            "status": "ready",
            "entity_count": len(graph_plans),
            "relation_count": len(relation_rows),
            "citation_ids": [citation["citation_id"] for citation in citations],
            "observation_count": sum(row.get("observation_count", 0) for row in evidence_rows),
            "repeated_content_count": sum(
                row.get("repeated_content_count", 0) for row in evidence_rows
            ),
        }

    def _navigation_hits(self, request: ResearchRequest, plan) -> list[dict]:
        if self.structured_store is None:
            return []
        hits = self.structured_store.search(
            request.question,
            k=request.limit,
            where=None,
        )
        if not hits or hits[0].get("match_type") not in {"exact_id", "exact_title", "title_in_query"}:
            return []
        return hits

    def _discover_trends(
        self, request: ResearchRequest, plan, *, important_news: bool = False
    ) -> tuple[list[dict], dict, str] | None:
        """Build a bounded, diverse trend list from structured Daily Corpus items."""
        if self.structured_store is None or not hasattr(self.structured_store, "recent"):
            return None
        where = (
            {"content_type": "topic_candidate"}
            if important_news
            else build_metadata_filter(plan, request.latest_corpus_date)
        )
        try:
            candidates = self.structured_store.recent(
                limit=max(request.limit * 20, 100),
                where=where,
            )
        except Exception as exc:
            return [], {"path": "trend_discovery", "candidate_count": 0}, type(exc).__name__

        if important_news:
            candidates, entity_rejected, entity_filter_mode = _candidates_for_entities(
                candidates, plan.entities
            )
            ranked, background, unverified, excluded, merged_event_sources = _rank_important_news_candidates(
                candidates,
                latest_corpus_date=request.latest_corpus_date,
                limit=request.limit,
            )
            excluded = [*entity_rejected, *excluded]
        else:
            ranked = _rank_trend_candidates(
                candidates,
                latest_corpus_date=request.latest_corpus_date,
                limit=request.limit,
            )
            background, unverified, excluded = [], [], []
            merged_event_sources, entity_filter_mode = {}, "not_required"
        records = build_citations(ranked, max_citations=request.limit)
        return records, {
            "path": "trend_discovery",
            "candidate_count": len(candidates),
            "deduplicated_candidate_count": len(_deduplicate_candidates(candidates)),
            "returned_count": len(records),
            "entity_filter_mode": entity_filter_mode,
            "background_records": build_citations(background, max_citations=request.limit),
            "unverified_records": build_citations(unverified, max_citations=request.limit),
            "merged_event_sources": merged_event_sources,
            "excluded_candidate_ids": [
                str((candidate.get("metadata") or {}).get("citation_id") or "")
                for candidate in excluded
            ],
        }, ""


def _plan_for_request(request: ResearchRequest) -> tuple[QueryPlan, dict]:
    """Project one validated Route Contract into the legacy retrieval internals.

    This compatibility projection is private to the Gateway. It prevents the
    old query analyser from taking ownership of a route that was already
    resolved upstream while the retrieval implementation is migrated in
    vertical slices.
    """
    contract = request.route_contract
    if contract is None:
        return analyze_query(request.question), {
            "route_source": "legacy_query_analysis",
            "shadow": False,
        }

    validate_route_contract_for_retrieval(contract)
    family = contract["primary_task_family"]
    answer_mode = contract["answer_mode"]
    if family == "trend_discovery":
        intent = "important_news" if answer_mode == "important_news" else "recent_trend"
    elif family == "claim_verification":
        intent = "evidence_sufficiency"
    else:
        intent = "general_search"

    temporal = dict(contract.get("temporal_constraint") or {"mode": "none", "value": None})
    query_terms = [
        *contract.get("subjects", []),
        *contract.get("topics", []),
        *contract.get("claims", []),
        *contract.get("protected_terms", []),
    ]
    retrieval_query = " ".join(dict.fromkeys(term for term in query_terms if term))
    return QueryPlan(
        original_question=contract["original_query"],
        intent=intent,
        retrieval_query=retrieval_query or contract["original_query"],
        top_k=request.limit,
        topics=list(contract.get("topics", [])),
        entities=list(contract.get("subjects", [])),
        sources=list((contract.get("source_constraint") or {}).get("requested_sources", [])),
        time_window=temporal,
        needs_web_search=contract.get("web_permission") == "explicit",
        task_mode="source_check" if family == "claim_verification" else "general",
        graph_requirement=(
            "required" if family == "temporal_relation_exploration" else "optional"
        ),
        routing_notes=[f"Route Contract owns retrieval: {family}"],
    ), {
        "route_source": "route_contract_v2",
        "route_contract_version": contract.get("schema_version"),
        "shadow": True,
        "primary_task_family": family,
    }


def _is_generic_trend_plan(plan) -> bool:
    return plan.intent == "recent_trend" and not any(
        (plan.entities, plan.topics, plan.sources)
    )


def _is_focused_important_news_plan(plan) -> bool:
    return plan.intent == "important_news" and bool(getattr(plan, "entities", []))


def task_family_for_plan(plan) -> str:
    """Map a QueryPlan to its stable product task family."""
    if plan.task_mode == "timeline":
        return "timeline"
    if plan.graph_requirement == "required":
        return "relation_exploration"
    if plan.intent == "evidence_sufficiency" or plan.task_mode == "source_check":
        return "claim_verification"
    if _is_focused_important_news_plan(plan):
        return "trend_discovery"
    return "evidence_research"


def _effective_graph_requirement(plan) -> str:
    """Translate a user task into the minimum evidence channels it requires.

    A timeline needs cross-date Observation edges even when the query parser did
    not see an explicit phrase such as ``跨日关联``. Claim verification remains
    text-evidence-first: graph co-occurrence is a clue, never proof.
    """
    if plan.task_mode == "timeline":
        return "required"
    return plan.graph_requirement


def _focused_records(records: list[dict], plan, task_family: str) -> tuple[list[dict], str]:
    """Prefer exact entity IDs, falling back only for legacy index records."""
    entities = list(getattr(plan, "entities", []) or [])
    if not entities:
        return records, "not_required"

    requested = canonical_entity_ids(entities)
    require_all = task_family == "relation_exploration" and len(requested) > 1
    focused = []
    used_structured = False
    for record in records:
        present = canonical_entity_ids(record.get("entity_ids"))
        if present:
            used_structured = True
            matches = [entity_id in present for entity_id in requested]
            if matches and (all(matches) if require_all else any(matches)):
                focused.append(record)
            continue

        # Compatibility path for an old generation that predates entity IDs.
        haystack = normalize_lexical_text(" ".join(
            str(record.get(field) or "")
            for field in ("title", "source", "excerpt")
        ))
        matches = [normalize_lexical_text(entity) in haystack for entity in entities]
        if matches and (all(matches) if require_all else any(matches)):
            focused.append(record)
    return focused, "structured" if used_structured else "legacy_text_fallback"


def _deduplicate_candidates(candidates: list[dict]) -> list[dict]:
    """Keep one structured occurrence for each stable content item or title."""
    deduplicated = []
    seen = set()
    for candidate in candidates:
        metadata = candidate.get("metadata") or {}
        identity = str(metadata.get("content_id") or "").strip()
        if not identity:
            identity = normalize_lexical_text(metadata.get("title"))
        if not identity or identity in seen:
            continue
        seen.add(identity)
        deduplicated.append(candidate)
    return deduplicated


def _candidates_for_entities(
    candidates: list[dict], entities: list[str]
) -> tuple[list[dict], list[dict], str]:
    """Select company events by subject, retaining a legacy identity fallback."""
    requested = canonical_entity_ids(entities)
    if not requested:
        return candidates, [], "not_required"
    focused, rejected = [], []
    saw_event_subjects = False
    for candidate in candidates:
        metadata = candidate.get("metadata") or {}
        subject_ids = canonical_entity_ids(metadata.get("subject_entity_ids"))
        if subject_ids:
            saw_event_subjects = True
            if any(entity_id in subject_ids for entity_id in requested):
                focused.append(candidate)
            else:
                rejected.append(candidate)
            continue
        present = canonical_entity_ids(metadata.get("entity_ids"))
        if present and any(entity_id in present for entity_id in requested):
            focused.append(candidate)
        else:
            rejected.append(candidate)
    return focused, rejected, "event_subject" if saw_event_subjects else "legacy_entity"


def _rank_important_news_candidates(
    candidates: list[dict],
    *,
    latest_corpus_date: str | None,
    limit: int,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Apply a small product gate for focused 'recent important news' queries.

    Ordinary pricing/configuration details are excluded unless the text carries
    an observable major-decision or broad-impact signal. Material events inside
    the recent window form the main list; older material events remain auditable
    background rather than competing with current news.
    """
    try:
        newest = date.fromisoformat(latest_corpus_date) if latest_corpus_date else None
    except ValueError:
        newest = None

    main, background, unverified, excluded = [], [], [], []
    for index, candidate in enumerate(_deduplicate_candidates(candidates)):
        metadata = candidate.get("metadata") or {}
        content_kind = str(metadata.get("content_kind") or "").strip().casefold()
        event_type = str(metadata.get("event_type") or "").strip().casefold()
        has_event_contract = bool(content_kind and event_type)
        text = normalize_lexical_text(" ".join(
            str(value or "")
            for value in (
                metadata.get("title"), metadata.get("summary"),
                metadata.get("evidence"), candidate.get("text"),
            )
        ))
        ordinary_adjustment = any(term in text for term in (
            "price", "pricing", "seat", "seats", "configuration", "config",
            "价格", "定价", "席位", "配置", "机制调整",
        ))
        decision_signal = any(term in text for term in (
            "restructure", "architecture", "company wide", "strategic decision",
            "重大决策", "体系重构", "架构调整", "全公司",
        ))
        broad_impact_signal = any(term in text for term in (
            "all enterprise customers", "all users", "broad impact", "industry debate",
            "widespread", "全部企业客户", "全部用户", "广泛影响", "行业热议",
        ))
        major_adjustment = decision_signal and broad_impact_signal
        news_event_signal = any(term in text for term in (
            "announce", "partner", "launch", "release", "report", "advance",
            "lawsuit", "sues", "dispute", "leaves", "resigns", "appoints",
            "acquires", "merger", "investment", "funding",
            "宣布", "合作", "发布", "报告", "突破", "进展", "诉讼", "起诉",
            "争议", "离职", "任命", "收购", "合并", "投资", "融资",
        ))
        if has_event_contract:
            if content_kind != "news_event" or event_type in {
                "compatibility", "configuration", "documentation", "how_to",
                "pricing_detail", "project_listing", "tutorial",
            }:
                excluded.append(candidate)
                continue
        else:
            if ordinary_adjustment and not major_adjustment:
                excluded.append(candidate)
                continue
            if not news_event_signal and not major_adjustment:
                excluded.append(candidate)
                continue

        freshness = _freshness(
            metadata.get("publication_date")
            or metadata.get("effective_date")
            or metadata.get("date"),
            newest,
        )
        raw_score = metadata.get("score") or 0
        try:
            priority = max(0.0, min(float(raw_score) / 100.0, 1.0))
        except (TypeError, ValueError):
            priority = 0.0
        materiality = 1.0 if major_adjustment else 0.7
        scored = (0.50 * freshness + 0.30 * materiality + 0.20 * priority, index, candidate)
        temporal_confidence = str(metadata.get("temporal_confidence") or "").casefold()
        if has_event_contract and temporal_confidence in {"low", "unknown"}:
            unverified.append(scored)
        elif freshness <= 0.0:
            background.append(scored)
        else:
            main.append(scored)

    main.sort(key=lambda item: (-item[0], item[1]))
    background.sort(key=lambda item: (-item[0], item[1]))
    unverified.sort(key=lambda item: (-item[0], item[1]))
    selected_main, merged_event_sources = _collapse_event_groups(main, limit=limit)
    return (
        selected_main,
        [item[2] for item in background[:limit]],
        [item[2] for item in unverified[:limit]],
        excluded,
        merged_event_sources,
    )


def _collapse_event_groups(
    scored: list[tuple[float, int, dict]], *, limit: int
) -> tuple[list[dict], dict[str, list[str]]]:
    """Give one main-list slot to an event while preserving its source ledger."""
    selected = []
    groups: dict[str, list[str]] = {}
    seen_groups = set()
    for _, _, candidate in scored:
        metadata = candidate.get("metadata") or {}
        identity = str(metadata.get("citation_id") or "")
        group = str(metadata.get("event_group_id") or "").strip()
        if group:
            groups.setdefault(group, []).append(identity)
            if group in seen_groups:
                continue
            seen_groups.add(group)
        selected.append(candidate)
        if len(selected) >= limit:
            break
    merged = {group: identities for group, identities in groups.items() if len(identities) > 1}
    return selected, merged


def _rank_trend_candidates(
    candidates: list[dict],
    *,
    latest_corpus_date: str | None,
    limit: int,
) -> list[dict]:
    """Rank Daily Corpus candidates before any LLM interpretation.

    This deliberately uses product-owned signals only: upstream trend score,
    recency, and observable content completeness. It does not use the user's
    broad question as a semantic similarity query.
    """
    try:
        newest = date.fromisoformat(latest_corpus_date) if latest_corpus_date else None
    except ValueError:
        newest = None

    scored = []
    for index, candidate in enumerate(_deduplicate_candidates(candidates)):
        metadata = candidate.get("metadata") or {}
        raw_score = metadata.get("score") or 0
        try:
            priority = max(0.0, min(float(raw_score) / 100.0, 1.0))
        except (TypeError, ValueError):
            priority = 0.0
        freshness = _freshness(metadata.get("effective_date") or metadata.get("date"), newest)
        completeness = 1.0 if str(metadata.get("evidence") or candidate.get("text") or "").strip() else 0.0
        rank_score = 0.65 * priority + 0.25 * freshness + 0.10 * completeness
        scored.append((rank_score, index, candidate))
    scored.sort(key=lambda item: (-item[0], item[1]))

    selected = []
    source_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for _, _, candidate in scored:
        metadata = candidate.get("metadata") or {}
        source = str(metadata.get("source") or "未知来源")
        category = str(metadata.get("category") or "未分类")
        if source_counts.get(source, 0) >= 2 or category_counts.get(category, 0) >= 3:
            continue
        source_counts[source] = source_counts.get(source, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected


def _freshness(value: object, newest: date | None) -> float:
    if newest is None:
        return 0.5
    try:
        item_date = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return 0.0
    age_days = (newest - item_date).days
    if age_days < 0:
        return 0.0
    return max(0.0, 1.0 - age_days / 14.0)
