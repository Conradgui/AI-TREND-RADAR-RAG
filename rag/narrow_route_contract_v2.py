"""Shadow projection from narrow semantic facts to a complete Route Contract v2."""

from __future__ import annotations

import re
import uuid

from rag.narrow_semantic_decisions_v1 import project_narrow_decisions
from rag.query_understanding_v2 import RouteContractV2, _ROUTE_POLICIES, _supporting_contract


_QUOTED = re.compile(r"[“\"]([^”\"]+)[”\"]")
_BOOK_TITLE = re.compile(r"^《([^》]+)》$")
_WRAPPED_QUOTE = re.compile(r"^[“\"]([^”\"]+)[”\"]$")
_RELATIVE_WINDOW = re.compile(
    r"(?:近|最近|过去)\s*(?:\d+|一|两|三|半)\s*(?:小时|天|周|个月|月|年)"
)
_GENERIC_TASK_PROTECTED = {"热门趋势", "重要动态", "近期动态", "最新动态"}


def build_narrow_route_envelope(
    original_query: str,
    l1_fixture: dict,
    conversation_context: str | None = None,
) -> dict:
    """Return either one complete shadow contract or an explicit clarification."""
    projection = project_narrow_decisions(
        original_query, l1_fixture, conversation_context
    )
    if projection.status != "resolved":
        return {
            "status": "clarification_required",
            "contract": None,
            "reasons": list(projection.reasons),
        }

    primary = projection.primary_task_family
    supporting = list(projection.supporting_task_families)
    common = dict(
        schema_version="atr.route/2.0",
        request_id=_request_id(original_query, conversation_context),
        original_query=original_query,
        protected_terms=_protected_terms(original_query, l1_fixture),
        intent_signals=_intent_signals(original_query, l1_fixture),
        primary_task_family=primary,
        supporting_task_families=supporting,
        answer_mode=_answer_mode(original_query, primary, l1_fixture),
        route_confidence=0.55 if l1_fixture["item_locator_precision"] == "partial" else 1.0,
        ambiguities=["item locator may match multiple records"] if l1_fixture["item_locator_precision"] == "partial" else [],
        resolved_references=[
            {"reference_type": "item_id", "value": item_id, "origin": origin}
            for _, item_id, origin in projection.resolved_references
        ],
        supporting_contracts=[_supporting_contract(route) for route in supporting],
        subjects=[],
        claims=_claims(original_query, primary, supporting),
        temporal_constraint=_temporal_constraint(original_query),
        source_constraint={"requested_sources": [], "official_first": "官方" in original_query},
        web_permission=_web_permission(original_query, primary, supporting),
    )
    if primary == "item_navigation":
        contract = RouteContractV2(**common)
    else:
        rewrite, retrieval, prompt, output, budget = _ROUTE_POLICIES[primary]
        contract = RouteContractV2(
            **common,
            rewrite_policy_id=rewrite,
            retrieval_policy_id=retrieval,
            prompt_contract_id=prompt,
            answer_builder_contract_id=None,
            output_schema_id=output,
            budget_profile_id=budget,
        )
    return {"status": "resolved", "contract": contract.to_dict(), "reasons": []}


def _request_id(query: str, context: str | None) -> str:
    return "shadow-narrow-" + uuid.uuid5(
        uuid.NAMESPACE_URL, query + "\0" + (context or "")
    ).hex


def _protected_terms(query: str, value: dict) -> list[str]:
    terms = [_searchable_protected_value(span) for span in value["protected_spans"]]
    structural_target = None
    if value["dimensions"]["cross_time_or_entity_structure"]["state"] == "present":
        structural_target = _structural_target(query)
        if structural_target:
            terms.append(structural_target)
    for judgment in value["dimensions"].values():
        if judgment["state"] != "present":
            continue
        for span in judgment["evidence_spans"]:
            for match in _QUOTED.finditer(span):
                if match.group(1) not in terms:
                    terms.append(match.group(1))
    for reference in value["resolved_references"]:
        if reference["literal_span"] not in terms:
            terms.append(reference["literal_span"])
    for phrase in ("不要联网", "禁止联网", "别联网", "无需联网"):
        if phrase in query and phrase not in terms:
            terms.append(phrase)
    for pattern in (
        r"(?:近|最近|过去)\s*\d+\s*(?:小时|天|周|个月|月|年)",
        r"过去一年",
        r"ATR-\d{8}-[A-Z0-9]{6}",
    ):
        for match in re.finditer(pattern, query, re.I):
            if match.group(0) not in terms:
                terms.append(match.group(0))
    terms = [term for term in dict.fromkeys(terms) if term not in _GENERIC_TASK_PROTECTED]
    if structural_target:
        terms = [
            term for term in terms
            if term == structural_target or term not in structural_target
        ]
    return sorted(terms, key=query.find)


def _searchable_protected_value(span: str) -> str:
    """Remove presentation-only wrappers while preserving the literal inner value."""
    for pattern in (_BOOK_TITLE, _WRAPPED_QUOTE):
        match = pattern.fullmatch(span)
        if match:
            return match.group(1)
    return span


def _structural_target(query: str) -> str | None:
    window = _RELATIVE_WINDOW.search(query)
    if not window:
        return None
    tail = query[window.end():]
    match = re.match(
        r"\s*(.+?)(?:如何|怎么|怎样)?(?:演变|演进|变化|发展|迁移|重排)",
        tail,
    )
    if not match:
        return None
    value = match.group(1).strip(" ，,。！？!?")
    return value or None


def _intent_signals(query: str, value: dict) -> list[str]:
    signals = []
    mapping = {
        "item_lookup": "navigation",
        "recent_update_set": "recency",
        "cross_time_or_entity_structure": "timeline",
        "truth_assessable_claim": "verification",
        "explanation_or_comparison": "comparison" if "比较" in query else "explanation",
    }
    for dimension, signal in mapping.items():
        if value["dimensions"][dimension]["state"] == "present" and signal not in signals:
            signals.append(signal)
    if value["dimensions"]["recent_update_set"]["state"] == "present" and any(
        term in query for term in ("重要", "热门", "值得关注")
    ):
        signals.append("importance")
    if value["dimensions"]["cross_time_or_entity_structure"]["state"] == "present" and any(
        term in query for term in ("关系", "否定", "合作方")
    ):
        signals.append("relation")
    if "联网" in query and not any(
        term in query for term in ("不要联网", "禁止联网", "别联网", "无需联网")
    ):
        signals.append("web_requested")
    return signals


def _answer_mode(query: str, route: str, value: dict) -> str:
    if route == "item_navigation":
        return "item_disambiguation" if value["item_locator_precision"] == "partial" else "exact_item"
    if route == "trend_discovery":
        return "trend_clusters" if "热门趋势" in query else "important_news"
    if route == "temporal_relation_exploration":
        return "relation" if any(term in query for term in ("关系", "否定", "合作方")) else "timeline"
    if route == "claim_verification":
        return "verification_verdict"
    if "比较" in query:
        return "comparison"
    if any(term in query for term in ("深挖", "深入研究")):
        return "deep_research"
    return "explanation"


def _claims(query: str, primary: str, supporting: list[str]) -> list[str]:
    if primary != "claim_verification" and "claim_verification" not in supporting:
        return []
    return [match.group(1) for match in _QUOTED.finditer(query)]


def _temporal_constraint(query: str) -> dict:
    match = _RELATIVE_WINDOW.search(query)
    return {"mode": "relative_window", "value": match.group(0)} if match else {"mode": "none", "value": None}


def _web_permission(query: str, primary: str, supporting: list[str]) -> str:
    if any(term in query for term in ("不要联网", "禁止联网", "别联网", "无需联网")):
        return "forbidden"
    if "联网" in query:
        return "explicit"
    if primary == "item_navigation" and not supporting:
        return "forbidden"
    return "on_demand"
