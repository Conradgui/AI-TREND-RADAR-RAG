"""Route-neutral SemanticParseV1 and deterministic Route Contract projection."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator

from rag.query_understanding_v2 import RouteContractV2, _ROUTE_POLICIES, _supporting_contract


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/rag-transformation/specs/semantic-parse-v1.schema.json"
_ATR_ID = re.compile(r"\bATR-\d{8}-[A-Z0-9]{6}\b", re.IGNORECASE)
_WEB_DENIALS = ("不要联网", "禁止联网", "别联网", "无需联网")

_ACTION_FAMILY = {
    "navigate": "item_navigation",
    "discover": "trend_discovery",
    "trace": "temporal_relation_exploration",
    "relate": "temporal_relation_exploration",
    "verify": "claim_verification",
    "explain": "evidence_research",
    "compare": "evidence_research",
    "recommend": "evidence_research",
    "research": "evidence_research",
}
_ACTION_SIGNAL = {
    "navigate": "navigation",
    "trace": "timeline",
    "relate": "relation",
    "verify": "verification",
    "explain": "explanation",
    "compare": "comparison",
    "recommend": "comparison",
    "research": "deep_research",
}


class SemanticParseViolation(ValueError):
    """The model output cannot be safely projected into a Route Contract."""


def validate_semantic_parse(query: str, context: str | None, parse: dict) -> None:
    """Reject schema violations, invented spans and invented context references."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(parse), key=lambda item: list(item.path))
    if errors:
        raise SemanticParseViolation("schema violation: " + "; ".join(error.message for error in errors))

    normalized_query = _normalized(query)
    for span in parse["literal_spans"]:
        if _normalized(span) not in normalized_query:
            raise SemanticParseViolation(f"literal span is not present in Query: {span}")
    for constraint in parse["constraints"]:
        if _normalized(constraint["literal_span"]) not in normalized_query:
            raise SemanticParseViolation(
                f"constraint literal span is not present in Query: {constraint['literal_span']}"
            )
    for reference in parse["references"]:
        if _normalized(reference["literal_span"]) not in normalized_query:
            raise SemanticParseViolation(
                f"reference literal span is not present in Query: {reference['literal_span']}"
            )
        value = reference["resolved_value"]
        if reference["status"] == "resolved_from_context":
            if not value or _normalized(value) not in _normalized(context or ""):
                raise SemanticParseViolation("resolved context reference is not present in context")
        elif reference["status"] == "unresolved" and value is not None:
            raise SemanticParseViolation("unresolved reference cannot have a resolved value")


def build_route_contract_from_semantic_parse(
    original_query: str,
    conversation_context: str | None,
    parse: dict,
) -> RouteContractV2:
    """Project semantic slots into one primary route and executable supports."""
    validate_semantic_parse(original_query, conversation_context, parse)
    if not parse["task_atoms"]:
        raise SemanticParseViolation("at least one task atom is required; fallback is forbidden")

    main_atoms = [item for item in parse["task_atoms"] if item["delivery_role"] == "main"]
    if len(main_atoms) != 1:
        raise SemanticParseViolation("exactly one main task atom is required")
    primary = _ACTION_FAMILY[main_atoms[0]["action"]]
    supporting = []
    for atom in parse["task_atoms"]:
        if atom["delivery_role"] != "supporting":
            continue
        family = _ACTION_FAMILY[atom["action"]]
        if family != primary and family not in supporting:
            supporting.append(family)

    intent_signals = _intent_signals(parse)
    ambiguities = list(parse["ambiguities"])
    for reference in parse["references"]:
        if reference["status"] == "unresolved" and "unresolved reference" not in ambiguities:
            ambiguities.append("unresolved reference")

    resolved_references = []
    for reference in parse["references"]:
        value = reference["resolved_value"]
        if reference["status"] == "resolved_from_context" and value:
            resolved_references.append(
                {"reference_type": "item_id", "value": value.upper(), "origin": "conversation_context"}
            )

    answer_mode = _answer_mode(primary, parse, intent_signals, ambiguities)
    web_permission = _web_permission(original_query, parse)
    if web_permission == "forbidden":
        intent_signals = [signal for signal in intent_signals if signal != "web_requested"]
    protected_terms = _literal_spans_in_query_order(original_query, parse["literal_spans"])
    common = dict(
        schema_version="atr.route/2.0",
        request_id=f"shadow-semantic-{uuid.uuid5(uuid.NAMESPACE_URL, original_query + chr(0) + (conversation_context or '')).hex}",
        original_query=original_query,
        protected_terms=protected_terms,
        intent_signals=intent_signals,
        primary_task_family=primary,
        supporting_task_families=supporting,
        answer_mode=answer_mode,
        route_confidence=min(parse["confidence"], 0.55) if ambiguities else parse["confidence"],
        ambiguities=ambiguities,
        resolved_references=resolved_references,
        supporting_contracts=[_supporting_contract(family) for family in supporting],
        subjects=list(parse["subjects"]),
        claims=list(parse["claims"]),
        web_permission=web_permission,
    )
    if primary == "item_navigation":
        return RouteContractV2(**common)

    rewrite, retrieval, prompt, output, budget = _ROUTE_POLICIES[primary]
    return RouteContractV2(
        **common,
        rewrite_policy_id=rewrite,
        retrieval_policy_id=retrieval,
        prompt_contract_id=prompt,
        answer_builder_contract_id=None,
        output_schema_id=output,
        budget_profile_id=budget,
    )


def _intent_signals(parse: dict) -> list[str]:
    signals = []
    for atom in parse["task_atoms"]:
        signal = _ACTION_SIGNAL.get(atom["action"])
        if signal and signal not in signals:
            signals.append(signal)
        text = f"{atom['target']} {atom['success_criterion']}"
        if atom["action"] == "discover":
            if any(term in text for term in ("趋势", "动向", "聚类", "主题")):
                _append(signals, "trend")
            if any(term in text for term in ("重要", "最值得", "大新闻")):
                _append(signals, "importance")
        if atom["action"] == "trace":
            _append(signals, "trend")
        if atom["action"] == "research":
            _append(signals, "deep_research")

    for constraint in parse["constraints"]:
        if constraint["kind"] == "time":
            if any(atom["action"] == "discover" for atom in parse["task_atoms"]):
                _append(signals, "recency")
        elif constraint["kind"] == "importance":
            _append(signals, "importance")
        elif constraint["kind"] == "source":
            _append(signals, "source_specific")
        elif constraint["kind"] == "web_permission" and constraint["value"] == "explicit":
            _append(signals, "web_requested")
    return signals


def _answer_mode(primary: str, parse: dict, signals: list[str], ambiguities: list[str]) -> str:
    actions = [
        item["action"] for item in parse["task_atoms"]
        if item["delivery_role"] == "main" and _ACTION_FAMILY[item["action"]] == primary
    ]
    if primary == "item_navigation":
        exact = bool(parse["locators"]) and all(locator["exact"] for locator in parse["locators"])
        return "exact_item" if exact and not ambiguities else "item_disambiguation"
    if primary == "trend_discovery":
        return "trend_clusters" if "trend" in signals and "importance" not in signals else "important_news"
    if primary == "temporal_relation_exploration":
        return "timeline" if "trace" in actions else "relation"
    if primary == "claim_verification":
        return "verification_verdict"
    if "research" in actions or "recommend" in actions:
        return "deep_research"
    if "compare" in actions:
        return "comparison"
    return "explanation"


def _web_permission(query: str, parse: dict) -> str:
    if any(term in query for term in _WEB_DENIALS):
        return "forbidden"
    for constraint in parse["constraints"]:
        if constraint["kind"] == "web_permission" and constraint["value"] == "explicit":
            return "explicit"
    return "on_demand"


def _literal_spans_in_query_order(query: str, spans: list[str]) -> list[str]:
    unique = []
    for span in spans:
        if span not in unique:
            unique.append(span)
    return sorted(unique, key=lambda span: query.find(span))


def _append(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())
