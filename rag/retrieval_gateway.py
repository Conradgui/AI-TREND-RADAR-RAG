"""Task-aware retrieval seam for auditable Evidence Records."""

from __future__ import annotations

import asyncio
import time
import hashlib
from dataclasses import asdict
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations

from rag.citations import build_citations, retrieve_citations_with_status
from rag.entity_identity import canonical_entity_ids, query_entity_ids
from rag.event_contract import canonical_content_kind, canonical_event_type
from rag.event_extraction import extract_event_batch
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
from rag.route_execution_policy import execution_policy_for


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
    supplementary_records: list[dict] = field(default_factory=list)
    background_records: list[dict] = field(default_factory=list)
    unverified_records: list[dict] = field(default_factory=list)
    analysis: object | None = None
    query_plan: dict = field(default_factory=dict)
    trace: dict = field(default_factory=dict)
    error_code: str = ""
    elapsed_ms: float = 0.0


class EvidenceRetrievalGateway:
    """Hide task routing and retrieval adapters behind one small interface."""

    def __init__(
        self,
        retriever,
        structured_store=None,
        graph_driver=None,
        graph_readiness_probe=None,
    ):
        self.retriever = retriever
        self.structured_store = structured_store
        self.graph_driver = graph_driver
        self.graph_readiness_probe = graph_readiness_probe

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
                policy = execution_policy_for("trend_discovery", "trend_clusters")
                records, candidate_graph = await self._augment_candidate_trends(records)
                return EvidenceBundle(
                    status=(
                        "error" if error_code
                        else "degraded" if candidate_graph["status"] == "unavailable"
                        else "ready" if records
                        else "empty"
                    ),
                    task_family="trend_discovery",
                    records=records,
                    analysis=plan,
                    query_plan=plan.to_dict(),
                    trace={
                        **trace,
                        **route_trace,
                        "execution_policy": asdict(policy),
                        "candidate_graph": candidate_graph,
                    },
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
                    supplementary_records=trace.pop("supplementary_records", []),
                    background_records=trace.pop("background_records", []),
                    unverified_records=trace.pop("unverified_records", []),
                    analysis=plan,
                    query_plan=plan.to_dict(),
                    trace={**trace, **route_trace},
                    error_code=error_code,
                    elapsed_ms=(time.perf_counter() - started_at) * 1000,
                )

        effective_graph_requirement = _effective_graph_requirement(plan)
        graph_readiness_trace = {"status": "not_required"}
        required_graph_preflight_failed = False
        if effective_graph_requirement == "required" and self.graph_readiness_probe is not None:
            readiness = await self.graph_readiness_probe.probe("runtime")
            graph_readiness_trace = asdict(readiness)
            if readiness.status != "ready":
                # Preserve text evidence, but do not spend time entering a graph
                # channel that an active readiness probe has already rejected.
                effective_graph_requirement = "disabled"
                required_graph_preflight_failed = True

        metadata_filter = build_metadata_filter(plan, request.latest_corpus_date)
        outcome = await retrieve_citations_with_status(
            self.retriever,
            plan.retrieval_query,
            k=request.limit,
            where=metadata_filter,
            prefer_recent=plan.time_window.get("label") == "recent_corpus_first",
            latest_date=request.latest_corpus_date,
            graph_requirement=effective_graph_requirement,
        )
        task_family = route_trace.get("primary_task_family") or task_family_for_plan(plan)
        timeline_lexical_records = []
        if plan.task_mode == "timeline" and effective_graph_requirement == "disabled":
            timeline_lexical_records = self._timeline_lexical_candidates(
                plan, request, metadata_filter
            )
        retrieved_records = _merge_citation_records(
            outcome.citations, timeline_lexical_records
        )
        records, entity_filter_mode = _focused_records(retrieved_records, plan, task_family)
        graph_trace = {"status": "not_required"}
        if required_graph_preflight_failed:
            graph_trace = {
                "status": "error",
                "error_code": graph_readiness_trace.get("error_code") or "graph_not_ready",
            }
        elif effective_graph_requirement != "disabled" and task_family in {
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
                    "graph_readiness": graph_readiness_trace,
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
                "timeline_lexical_candidate_count": len(timeline_lexical_records),
                "focused_count": len(records),
                "entity_filter_mode": entity_filter_mode,
                "graph_readiness": graph_readiness_trace,
                "graph_evidence": graph_trace,
            },
            error_code=final_error_code,
            elapsed_ms=(time.perf_counter() - started_at) * 1000,
        )


    def _timeline_lexical_candidates(self, plan, request, metadata_filter) -> list[dict]:
        """Preserve direct event hits that hybrid rank fusion may truncate.

        Direct timeline questions are evidence-led and deterministic.  The
        generation-local lexical index can already identify an entity + event
        pair (for example, OpenAI + IPO); losing that hit merely because a
        hybrid RRF top-k is short harms recall.  This bounded supplement is
        deliberately restricted to the graph-free direct-report timeline path.
        """
        if self.structured_store is None or not hasattr(self.structured_store, "search"):
            return []
        try:
            candidates = self.structured_store.search(
                plan.retrieval_query,
                k=max(request.limit * 10, 20),
                where=metadata_filter,
            )
        except Exception:
            return []
        direct_matches = [
            candidate for candidate in candidates
            if candidate.get("match_type") in {
                "exact_id", "exact_title", "title_in_query", "entity_event"
            }
        ]
        return build_citations(direct_matches, max_citations=max(request.limit * 10, 20))


    async def _append_graph_evidence(self, request, plan, records):
        graph_plans = build_graph_question_plans(request.question, query_plan=plan)
        if not graph_plans:
            return records, {
                "status": "error",
                "error_code": "graph_question_not_plannable",
            }
        if self.graph_driver is None:
            return records, {"status": "error", "error_code": "graph_driver_unavailable"}
        graph_pairs = list(combinations(graph_plans, 2))
        results = await asyncio.gather(
            *(
                build_graph_reasoning_evidence(self.graph_driver, graph_plan)
                for graph_plan in graph_plans
            ),
            *(
                build_entity_relation_evidence(self.graph_driver, left_plan, right_plan)
                for left_plan, right_plan in graph_pairs
            ),
            return_exceptions=True,
        )
        failure = next((result for result in results if isinstance(result, Exception)), None)
        if failure is not None:
            return records, {"status": "error", "error_code": type(failure).__name__}
        evidence_rows = results[:len(graph_plans)]
        relation_rows = results[len(graph_plans):]
        citations = [
            *(build_graph_reasoning_citation(evidence) for evidence in evidence_rows),
            *(build_entity_relation_citation(relation) for relation in relation_rows),
        ]
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

    async def _augment_candidate_trends(self, records: list[dict]) -> tuple[list[dict], dict]:
        """Expand only already-ranked trend candidates into graph relations."""
        content_ids = list(dict.fromkeys(
            str(record.get("content_id") or "").strip()
            for record in records
            if record.get("content_id")
        ))
        if not content_ids:
            return records, {"status": "skipped", "reason": "no_candidate_content_ids"}
        if self.graph_driver is None or self.graph_readiness_probe is None:
            return records, {"status": "unavailable", "error_code": "graph_probe_unavailable"}
        readiness = await self.graph_readiness_probe.probe("runtime")
        if readiness.status != "ready":
            return records, {
                "status": "unavailable",
                "error_code": readiness.error_code or "graph_not_ready",
            }
        try:
            rows = await self.graph_driver.execute_query(
                "MATCH (o:Observation) WHERE o.contentId IN $content_ids "
                "OPTIONAL MATCH (e:Entity)-[:MENTIONS]->(o) "
                "OPTIONAL MATCH (o)-[:ABOUT]->(cat:Category) "
                "OPTIONAL MATCH (o)-[:PREVIOUS_OBSERVATION]->(previous:Observation) "
                "RETURN collect(DISTINCT e.name) AS entities, "
                "collect(DISTINCT cat.name) AS categories, "
                "collect(DISTINCT CASE WHEN previous IS NULL THEN null ELSE o.contentId END) "
                "AS repeated_content_ids, count(DISTINCT previous) AS previous_link_count",
                content_ids=content_ids,
                timeout=5.0,
            )
        except Exception as exc:
            return records, {"status": "unavailable", "error_code": type(exc).__name__}
        row = rows[0] if rows else {}
        entities = [value for value in row.get("entities", []) if value]
        categories = [value for value in row.get("categories", []) if value]
        repeated = [value for value in row.get("repeated_content_ids", []) if value]
        previous_links = int(row.get("previous_link_count") or 0)
        if not any((entities, categories, repeated, previous_links)):
            return records, {"status": "empty", "candidate_count": len(content_ids)}

        digest = hashlib.sha1("|".join(sorted(content_ids)).encode("utf-8")).hexdigest()[:12]
        parts = []
        if entities:
            parts.append("候选共同涉及实体：" + "、".join(entities[:8]))
        if categories:
            parts.append("候选覆盖方向：" + "、".join(categories[:8]))
        if repeated or previous_links:
            parts.append(f"发现 {max(len(repeated), previous_links)} 条跨日延续关系")
        graph_record = {
            "evidence_type": "graph",
            "date": max((str(record.get("date") or "") for record in records), default=""),
            "source": "Neo4j Graph",
            "title": "候选趋势关系",
            "citation_id": f"graph-trend-{digest}",
            "excerpt": "；".join(parts),
            "content_ids": content_ids,
        }
        return [*records, graph_record], {
            "status": "ready",
            "candidate_count": len(content_ids),
            "entity_count": len(entities),
            "category_count": len(categories),
            "previous_link_count": previous_links,
        }

    def _navigation_hits(self, request: ResearchRequest, plan) -> list[dict]:
        if self.structured_store is None:
            return []
        route_family = str((request.route_contract or {}).get("primary_task_family") or "")
        if route_family and route_family != "item_navigation":
            return []
        hits = self.structured_store.search(
            request.question,
            k=request.limit,
            where=None,
        )
        if not hits:
            return []
        accepted = {"exact_id", "exact_title", "title_in_query"}
        if route_family == "item_navigation":
            accepted.add("descriptor")
        if hits[0].get("match_type") not in accepted:
            return []
        return hits[:1]

    def _discover_trends(
        self, request: ResearchRequest, plan, *, important_news: bool = False
    ) -> tuple[list[dict], dict, str] | None:
        """Build a bounded, diverse trend list from structured Daily Corpus items."""
        if self.structured_store is None or not hasattr(self.structured_store, "recent"):
            return None
        where = build_metadata_filter(plan, request.latest_corpus_date)
        # Entity filtering happens after legacy rows receive deterministic
        # subject/mention roles. The wider structured window protects recall
        # across roughly two weeks of dense daily reports without increasing
        # the number of records sent to the answer model.
        candidate_limit = (
            max(request.limit * 200, 2000)
            if important_news
            else max(request.limit * 20, 100)
        )
        try:
            candidates = self.structured_store.recent(
                limit=candidate_limit,
                where=where,
            )
        except Exception as exc:
            return [], {"path": "trend_discovery", "candidate_count": 0}, type(exc).__name__

        if important_news:
            candidates = _ensure_event_contract(candidates)
            expanded_entities = [
                *plan.entities,
                *[
                    item.get("entity_id")
                    for item in getattr(plan, "entity_expansions", [])
                    if item.get("entity_id")
                ],
            ]
            candidates, entity_rejected, entity_filter_mode = _candidates_for_entities(
                candidates, list(dict.fromkeys(expanded_entities))
            )
            candidates = _annotate_entity_match_tier(
                candidates,
                direct_entities=plan.entities,
                expansions=getattr(plan, "entity_expansions", []),
            )
            ranked, supplementary, background, unverified, excluded, merged_event_sources = _rank_important_news_candidates(
                candidates,
                latest_corpus_date=request.latest_corpus_date,
                limit=request.limit,
                strict_importance=_requires_strict_importance(request.question),
            )
            excluded = [*entity_rejected, *excluded]
        else:
            ranked = _rank_trend_candidates(
                candidates,
                latest_corpus_date=request.latest_corpus_date,
                limit=request.limit,
            )
            supplementary, background, unverified, excluded = [], [], [], []
            merged_event_sources, entity_filter_mode = {}, "not_required"
        records = build_citations(ranked, max_citations=request.limit)
        return records, {
            "path": "trend_discovery",
            "candidate_count": len(candidates),
            "structured_candidate_limit": candidate_limit,
            "deduplicated_candidate_count": len(_deduplicate_candidates(candidates)),
            "returned_count": len(records),
            "entity_filter_mode": entity_filter_mode,
            "entity_expansions": getattr(plan, "entity_expansions", []),
            "supplementary_records": build_citations(supplementary, max_citations=request.limit),
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

    temporal = _legacy_time_window(contract.get("temporal_constraint"))
    query_terms = [
        *contract.get("subjects", []),
        *contract.get("topics", []),
        *contract.get("retrieval_hints", []),
        *[
            item.get("entity_id")
            for item in contract.get("entity_expansions", [])
            if item.get("entity_id")
        ],
        *contract.get("claims", []),
        *contract.get("protected_terms", []),
    ]
    retrieval_query = " ".join(_expand_retrieval_terms(query_terms))
    execution_policy = execution_policy_for(family, answer_mode)
    graph_requirement = {
        "required": "required",
        "disabled": "disabled",
        # Candidate-bounded graph expansion is owned by the structured trend
        # path and must not leak into the generic hybrid retriever.
        "candidate_bounded": "disabled",
    }[execution_policy.graph_mode]
    task_mode = {
        "comparison": "compare",
        "timeline": "timeline",
        "source_check": "source_check",
    }.get(answer_mode, "general")
    return QueryPlan(
        original_question=contract["original_query"],
        intent=intent,
        retrieval_query=retrieval_query or contract["original_query"],
        top_k=request.limit,
        topics=list(contract.get("topics", [])),
        entities=list(contract.get("subjects", [])),
        retrieval_hints=list(contract.get("retrieval_hints", [])),
        entity_expansions=list(contract.get("entity_expansions", [])),
        sources=list((contract.get("source_constraint") or {}).get("requested_sources", [])),
        time_window=temporal,
        needs_web_search=contract.get("web_permission") == "explicit",
        task_mode=task_mode,
        graph_requirement=graph_requirement,
        routing_notes=[f"Route Contract owns retrieval: {family}"],
    ), {
        "route_source": "route_contract_v2",
        "route_contract_version": contract.get("schema_version"),
        "shadow": True,
        "primary_task_family": family,
        "execution_policy": asdict(execution_policy),
    }


def _expand_retrieval_terms(terms: list[object]) -> list[str]:
    """Add a small, explicit bilingual event vocabulary for corpus retrieval.

    These aliases improve lexical recall while keeping the original user terms
    intact. They are event words with stable Chinese/English equivalence, not
    speculative entity associations.
    """
    aliases = {"上市": ("IPO",), "ipo": ("上市",)}
    expanded: list[str] = []
    for raw in terms:
        term = str(raw or "").strip()
        if not term:
            continue
        expanded.append(term)
        expanded.extend(aliases.get(normalize_lexical_text(term), ()))
    return list(dict.fromkeys(expanded))


def _legacy_time_window(temporal: dict | None) -> dict:
    """Project the versioned temporal contract into the legacy filter shape."""
    temporal = dict(temporal or {})
    if temporal.get("mode") != "relative_window":
        return temporal or {"mode": "none", "value": None}
    try:
        days = int(temporal.get("value"))
    except (TypeError, ValueError):
        return {"mode": "none", "value": None}
    return {
        "label": "last_7_days" if days == 7 else "recent_corpus_first",
        "days": days,
        "requires_date_filter": days == 7,
    }


def _is_generic_trend_plan(plan) -> bool:
    return plan.intent == "recent_trend" and not any(
        (plan.entities, plan.topics, plan.sources)
    )


def _is_focused_important_news_plan(plan) -> bool:
    registered = query_entity_ids(
        " ".join(str(entity) for entity in getattr(plan, "entities", []))
    )
    return plan.intent == "important_news" and bool(registered)


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

    Legacy timeline parsing keeps its graph requirement. A versioned Route
    Contract may explicitly select the deterministic direct-report timeline
    policy, which must not be silently upgraded back to graph-required.
    """
    owns_route = any(
        str(note).startswith("Route Contract owns retrieval:")
        for note in getattr(plan, "routing_notes", [])
    )
    if plan.task_mode == "timeline" and not owns_route:
        return "required"
    return plan.graph_requirement


def _focused_records(records: list[dict], plan, task_family: str) -> tuple[list[dict], str]:
    """Prefer exact entity IDs, falling back only for legacy index records."""
    entities = list(getattr(plan, "entities", []) or [])
    if getattr(plan, "task_mode", "") == "compare":
        return records, "task_scope"
    requested = query_entity_ids(" ".join(str(entity) for entity in entities))
    if not requested:
        return records, "not_required"

    require_all = task_family == "relation_exploration" and len(requested) > 1
    focused = []
    used_structured = False
    for record in records:
        if (
            getattr(plan, "task_mode", "") == "timeline"
            and _record_matches_task_qualifier(record, plan)
        ):
            focused.append(record)
            continue
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


def _record_matches_task_qualifier(record: dict, plan) -> bool:
    """Keep direct event evidence even when old metadata lacks the subject ID."""
    text = normalize_lexical_text(" ".join(
        str(record.get(field) or "")
        for field in ("title", "excerpt", "category", "url")
    ))
    entities = {
        normalize_lexical_text(entity)
        for entity in getattr(plan, "entities", [])
    }
    ignored = {"按时间", "时间线", "相关", "报道", "证据", "openai"}
    aliases = {"上市": ("上市", "ipo"), "ipo": ("ipo", "上市")}
    for raw in str(getattr(plan, "retrieval_query", "")).split():
        term = normalize_lexical_text(raw)
        if not term or term in entities or term in ignored:
            continue
        if any(alias in text for alias in aliases.get(term, (term,))):
            return True
    return False


def _requested_entity_ids(values: list[str]) -> list[str]:
    """Preserve explicit registry IDs before matching natural-language aliases.

    Hyphenated IDs such as ``google-deepmind`` and ``grok-bot`` are also valid
    product/entity identifiers. Passing them through ``query_entity_ids`` as a
    sentence treats them like repository slugs and can erase them entirely.
    Canonicalizing each supplied value first keeps explicit route output
    authoritative while retaining alias matching for display names.
    """
    explicit = canonical_entity_ids(values)
    mentioned = query_entity_ids(" ".join(str(value) for value in values))
    return list(dict.fromkeys([*explicit, *mentioned]))


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


def _merge_citation_records(*groups: list[dict]) -> list[dict]:
    """Merge retrieval channels without erasing distinct dated occurrences."""
    merged = []
    seen = set()
    for group in groups:
        for record in group:
            identity = str(
                record.get("citation_id") or record.get("occurrence_id") or ""
            ).strip()
            if not identity or identity in seen:
                continue
            seen.add(identity)
            merged.append(record)
    return merged


def _ensure_event_contract(candidates: list[dict]) -> list[dict]:
    """Backfill legacy index rows with the same deterministic ingress contract.

    New generations persist these fields during corpus projection. This bridge
    keeps an already-active generation usable until its next controlled rebuild;
    it performs no model call and never overrides a complete reviewed contract.
    """
    extraction_rows = []
    for candidate in candidates:
        metadata = dict(candidate.get("metadata") or {})
        extraction_rows.append({
            **metadata,
            "title": metadata.get("title"),
            "summary": metadata.get("summary") or metadata.get("evidence") or candidate.get("text"),
            "source": metadata.get("source"),
        })
    extracted_rows = extract_event_batch(extraction_rows)

    enriched = []
    contract_fields = (
        "content_kind", "source_role", "event_type", "subject_entity_ids",
        "mentioned_entity_ids", "publication_date", "temporal_confidence",
        "extraction_status", "event_group_id",
    )
    for candidate, extracted in zip(candidates, extracted_rows, strict=True):
        metadata = dict(candidate.get("metadata") or {})
        for field in contract_fields:
            value = extracted.get(field)
            if metadata.get(field) not in (None, "", []):
                if field in {"content_kind", "event_type"}:
                    current = (
                        canonical_content_kind(metadata.get(field))
                        if field == "content_kind"
                        else canonical_event_type(metadata.get(field))
                    )
                    extracted_value = (
                        canonical_content_kind(value)
                        if field == "content_kind"
                        else canonical_event_type(value)
                    )
                    upgradeable = current == "unknown" or (
                        field == "content_kind"
                        and current == "developer_content"
                        and extracted_value in {"research", "news"}
                    ) or (
                        field == "event_type"
                        and current == "documentation_or_tutorial"
                        and extracted_value not in {"unknown", "documentation_or_tutorial"}
                    )
                    if upgradeable and extracted_value != "unknown":
                        metadata[field] = value
                continue
            # An old active generation did not persist source-owned temporal
            # confidence. Derive semantic roles now, but do not retroactively
            # turn its usable report date into an "unknown-time" quarantine.
            if field == "temporal_confidence" and value == "unknown" and not metadata.get(field):
                continue
            if value not in (None, "", []):
                metadata[field] = value
        enriched.append({**candidate, "metadata": metadata})
    return enriched


def _candidates_for_entities(
    candidates: list[dict], entities: list[str]
) -> tuple[list[dict], list[dict], str]:
    """Select entity events by subject IDs, with a controlled registry fallback."""
    requested = _requested_entity_ids(entities)
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
        mentioned = _candidate_registry_entity_ids(candidate)
        if (present and any(entity_id in present for entity_id in requested)) or any(
            entity_id in mentioned for entity_id in requested
        ):
            focused.append(candidate)
        else:
            rejected.append(candidate)
    return focused, rejected, "event_subject" if saw_event_subjects else "legacy_entity"


def _annotate_entity_match_tier(
    candidates: list[dict], *, direct_entities: list[str], expansions: list[dict]
) -> list[dict]:
    """Attach private ranking provenance from IDs and explicit registry mentions."""
    direct = set(_requested_entity_ids(direct_entities))
    related = {
        str(item.get("entity_id") or "").strip(): float(item.get("weight") or 0)
        for item in expansions
        if str(item.get("entity_id") or "").strip()
    }
    entity_scope_required = bool(direct or related)
    annotated = []
    for candidate in candidates:
        metadata = dict(candidate.get("metadata") or {})
        present = set(canonical_entity_ids(metadata.get("subject_entity_ids")))
        present.update(canonical_entity_ids(metadata.get("entity_ids")))
        present.update(_candidate_registry_entity_ids(candidate))
        if not entity_scope_required:
            tier, weight = "direct", 1.0
        elif present & direct:
            tier, weight = "direct", 1.0
        else:
            matched_weights = [related[entity_id] for entity_id in present if entity_id in related]
            if matched_weights:
                tier, weight = "related", max(matched_weights)
            else:
                tier, weight = "background", 0.0
        metadata["_entity_match_tier"] = tier
        metadata["_entity_match_weight"] = weight
        annotated.append({**candidate, "metadata": metadata})
    return annotated


def _rank_important_news_candidates(
    candidates: list[dict],
    *,
    latest_corpus_date: str | None,
    limit: int,
    strict_importance: bool = True,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict], dict[str, list[str]]]:
    """Apply a small product gate for focused 'recent important news' queries.

    Ordinary pricing/configuration details are excluded unless the text carries
    an observable major-decision or broad-impact signal. Fresh direct events form
    the main list; fresh related events are supplementary; older events remain
    auditable background rather than competing with current news.
    """
    try:
        newest = date.fromisoformat(latest_corpus_date) if latest_corpus_date else None
    except ValueError:
        newest = None

    main, supplementary, background, unverified, excluded = [], [], [], [], []
    for index, candidate in enumerate(_deduplicate_candidates(candidates)):
        metadata = candidate.get("metadata") or {}
        raw_content_kind = str(metadata.get("content_kind") or "").strip().casefold()
        raw_event_type = str(metadata.get("event_type") or "").strip().casefold()
        content_kind = canonical_content_kind(raw_content_kind)
        event_type = canonical_event_type(raw_event_type)
        has_event_contract = bool(raw_content_kind and raw_event_type)
        source_role = str(metadata.get("source_role") or "").casefold()
        title_text = normalize_lexical_text(metadata.get("title"))
        source_text = normalize_lexical_text(metadata.get("source"))
        generic_landing_page = (
            title_text in {"news", "latest news"}
            or title_text in {
                f"news {source_text}",
                f"latest news {source_text}",
            }
        )
        # A few older first-party rows persisted the placeholder pair
        # ``unknown/other`` even though their specific title is itself a
        # release or research announcement. Recover only that narrow legacy
        # case; generic collection pages remain browse surfaces.
        legacy_first_party_event = (
            source_role == "first_party"
            and content_kind == "unknown"
            and event_type == "unknown"
            and not generic_landing_page
            and any(term in title_text for term in (
                "announce", "launch", "release", "introduc", "brings",
                "achieves", "appoint", "join", "new era", "发布", "推出",
                "突破", "任命", "加入", "新帅",
            ))
        )
        if legacy_first_party_event:
            content_kind = "news"
            event_type = (
                "model_release"
                if any(term in title_text for term in ("model", "gemini", "robotics", "模型"))
                else "research_release"
            )
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
        high_impact_signal = broad_impact_signal or any(term in text for term in (
            "breakthrough", "state of the art", "state-of-the-art", "open source",
            "open sourcing", "first ever", "real world impact", "real-world impact",
            "company wide", "company-wide", "systemic reorganization", " ceo ",
            "重大突破", "技术突破", "开源", "首次", "系统性重排", "行业级影响",
            # Safety research with plausible systemic consequences and
            # cross-provider regulatory changes deserve main-list treatment,
            # even when the legacy row was previously typed as documentation.
            "systemic failures", "behavioral tendencies", "multiagent systems",
            "eu ai act", "compliance", "系统性失败", "行为倾向", "合规",
        ))
        major_adjustment = decision_signal and broad_impact_signal
        news_event_signal = any(term in text for term in (
            "announce", "partner", "launch", "release", "report", "advance",
            "lawsuit", "sues", "dispute", "leaves", "resigns", "appoints",
            "acquires", "merger", "investment", "funding",
            "宣布", "合作", "发布", "报告", "突破", "进展", "诉讼", "起诉",
            "争议", "离职", "任命", "收购", "合并", "投资", "融资",
        ))
        if generic_landing_page and source_role == "first_party" and not major_adjustment:
            excluded.append(candidate)
            continue
        if has_event_contract:
            excluded_contract = (
                content_kind not in {"news", "research"}
                or event_type in {
                    "compatibility", "documentation_or_tutorial", "pricing_or_access",
                    "unknown",
                }
            )
            if excluded_contract and not major_adjustment:
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
        event_materiality = {
            "acquisition": 1.0,
            "funding": 0.95,
            "litigation": 0.95,
            "leadership": 0.9,
            "model_release": 0.9,
            "safety_incident": 0.9,
            "regulatory_action": 0.85,
            "business_update": 0.85,
            "partnership": 0.65,
            "product_launch": 0.65,
            "research_release": 0.65,
        }.get(event_type, 0.6)
        materiality = 1.0 if major_adjustment else event_materiality
        if high_impact_signal and event_type in {
            "partnership", "product_launch", "research_release"
        }:
            materiality = 0.85
        try:
            evidence_quality = float(metadata.get("quality_score") or 0)
        except (TypeError, ValueError):
            evidence_quality = 0.0
        if evidence_quality <= 0:
            evidence_quality = 0.95 if source_role == "first_party" else 0.55
        base_score = (
            0.35 * freshness
            + 0.30 * materiality
            + 0.20 * evidence_quality
            + 0.15 * priority
        )
        tier = str(metadata.get("_entity_match_tier") or "direct")
        tier_order = {"direct": 0, "related": 1, "background": 2}.get(tier, 2)
        scored = (tier_order, -base_score, index, candidate)
        temporal_confidence = str(metadata.get("temporal_confidence") or "").casefold()
        effective_date = str(
            metadata.get("effective_date") or metadata.get("date") or ""
        ).strip()
        effective_date_basis = str(
            metadata.get("effective_date_basis") or ""
        ).casefold()
        report_date_is_usable = (
            bool(effective_date) and effective_date_basis == "report_date_fallback"
        )
        if (
            has_event_contract
            and temporal_confidence in {"low", "unknown"}
            and source_role != "first_party"
            and not report_date_is_usable
        ):
            unverified.append(scored)
        elif freshness <= 0.0 or tier == "background":
            background.append(scored)
        elif tier == "related" or (strict_importance and materiality < 0.7):
            supplementary.append(scored)
        else:
            main.append(scored)

    main.sort(key=lambda item: (item[0], item[1], item[2]))
    supplementary.sort(key=lambda item: (item[0], item[1], item[2]))
    background.sort(key=lambda item: (-item[0], item[1]))
    unverified.sort(key=lambda item: (-item[0], item[1]))
    primary_limit = min(limit, 5)
    selected_main, merged_event_sources = _collapse_event_groups(main, limit=primary_limit)
    selected_ids = {
        str((item.get("metadata") or {}).get("citation_id") or "")
        for item in selected_main
    }
    selected_event_groups = {
        str((item.get("metadata") or {}).get("event_group_id") or "")
        for item in selected_main
        if str((item.get("metadata") or {}).get("event_group_id") or "")
    }
    overflow = [
        item for item in main
        if str((item[3].get("metadata") or {}).get("citation_id") or "") not in selected_ids
        and str((item[3].get("metadata") or {}).get("event_group_id") or "")
        not in selected_event_groups
    ]
    selected_supplementary, supplementary_groups = _collapse_event_groups(
        [*supplementary, *overflow],
        limit=min(max(limit - len(selected_main), 0), 4),
    )

    merged_event_sources.update(supplementary_groups)
    return (
        selected_main,
        selected_supplementary,
        [item[3] for item in background[:limit]],
        [item[3] for item in unverified[:limit]],
        excluded,
        merged_event_sources,
    )


def _requires_strict_importance(question: str) -> bool:
    compact = normalize_lexical_text(question).replace(" ", "")
    return any(marker in compact for marker in (
        "重要动态", "重要新闻", "重大动态", "重大新闻", "有什么大事",
        "值得关注", "重点进展", "importantupdates", "majorupdates",
    ))


def _candidate_registry_entity_ids(candidate: dict) -> set[str]:
    """Read only explicit registered names from trusted candidate text fields."""
    metadata = candidate.get("metadata") or {}
    text = " ".join(
        str(metadata.get(field) or "")
        for field in ("title", "summary", "evidence")
    )
    return set(query_entity_ids(text))


def _collapse_event_groups(
    scored: list[tuple[int, float, int, dict]], *, limit: int
) -> tuple[list[dict], dict[str, list[str]]]:
    """Give one main-list slot to an event while preserving its source ledger."""
    selected = []
    groups: dict[str, list[str]] = {}
    seen_groups = set()
    for _, _, _, candidate in scored:
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
