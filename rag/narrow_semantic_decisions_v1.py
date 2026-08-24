"""Validate route-neutral narrow decisions and project them through L2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/rag-transformation/specs/narrow-semantic-decisions-v1.schema.json"
DIMENSION_TO_ROUTE = {
    "item_lookup": "item_navigation",
    "recent_update_set": "trend_discovery",
    "cross_time_or_entity_structure": "temporal_relation_exploration",
    "truth_assessable_claim": "claim_verification",
    "explanation_or_comparison": "evidence_research",
}


class NarrowDecisionViolation(ValueError):
    pass


@dataclass(frozen=True)
class NarrowRouteProjection:
    status: str
    primary_task_family: str | None
    supporting_task_families: tuple[str, ...]
    reasons: tuple[str, ...]
    resolved_references: tuple[tuple[str, str, str], ...]


def validate_narrow_decisions(
    query: str, value: dict, conversation_context: str | None = None
) -> None:
    errors = sorted(
        Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        raise NarrowDecisionViolation(
            "schema violation: " + "; ".join(error.message for error in errors)
        )
    for name, judgment in value["dimensions"].items():
        spans = judgment["evidence_spans"]
        if judgment["state"] in {"present", "uncertain"} and not spans:
            raise NarrowDecisionViolation(f"{name} requires evidence spans")
        if judgment["state"] == "absent" and spans:
            raise NarrowDecisionViolation(f"absent {name} cannot carry evidence")
        for span in spans:
            if span not in query:
                raise NarrowDecisionViolation(f"evidence span is not literal Query text: {span}")
    for span in value["unresolved_reference_spans"]:
        if span not in query:
            raise NarrowDecisionViolation(f"unresolved reference is not literal Query text: {span}")
    for span in value["protected_spans"]:
        if span not in query:
            raise NarrowDecisionViolation(f"protected span is not literal Query text: {span}")
    item_present = value["dimensions"]["item_lookup"]["state"] == "present"
    if item_present != (value["item_locator_precision"] != "none"):
        raise NarrowDecisionViolation("item locator precision must match item_lookup state")
    for reference in value["resolved_references"]:
        if reference["literal_span"] not in query:
            raise NarrowDecisionViolation("resolved reference span is not literal Query text")
        if reference["item_id"].casefold() not in (conversation_context or "").casefold():
            raise NarrowDecisionViolation("resolved reference item is absent from public context")


def project_narrow_decisions(
    query: str, value: dict, conversation_context: str | None = None
) -> NarrowRouteProjection:
    validate_narrow_decisions(query, value, conversation_context)
    reasons = []
    references = tuple(
        (reference["literal_span"], reference["item_id"], "conversation_context")
        for reference in value["resolved_references"]
    )
    if value["unresolved_reference_spans"]:
        reasons.append("unresolved references require clarification")
    uncertain = [
        name for name, judgment in value["dimensions"].items()
        if judgment["state"] == "uncertain"
    ]
    if uncertain:
        reasons.append("uncertain semantic decisions require clarification")
    deliveries = []
    for name, judgment in value["dimensions"].items():
        if judgment["state"] != "present":
            continue
        start = min(query.find(span) for span in judgment["evidence_spans"])
        deliveries.append((start, DIMENSION_TO_ROUTE[name], name, tuple(judgment["evidence_spans"])))
    deliveries = _drop_subsumed_explanation_modality(query, deliveries)
    if not deliveries:
        reasons.append("no explicit delivery found")
    if reasons:
        return NarrowRouteProjection(
            "clarification_required", None, (), tuple(reasons), references
        )

    deliveries.sort(key=lambda item: item[0])
    first_start = deliveries[0][0]
    if sum(start == first_start for start, _, _, _ in deliveries) > 1:
        return NarrowRouteProjection(
            "clarification_required", None, (),
            ("multiple deliveries start at the same evidence position",), references,
        )
    primary = deliveries[0][1]
    supporting = []
    for _, route, _, _ in deliveries[1:]:
        if route != primary and route not in supporting:
            supporting.append(route)
    return NarrowRouteProjection("resolved", primary, tuple(supporting), (), references)


def _drop_subsumed_explanation_modality(
    query: str, deliveries: list[tuple[int, str, str, tuple[str, ...]]]
) -> list[tuple[int, str, str, tuple[str, ...]]]:
    """Treat E as wording, not a second delivery, when it wraps a specific task."""
    specific_ranges = []
    for _, route, _, spans in deliveries:
        if route == "evidence_research":
            continue
        specific_ranges.extend(_span_range(query, span) for span in spans)
    if not specific_ranges:
        return deliveries

    result = []
    for delivery in deliveries:
        _, route, _, spans = delivery
        if route != "evidence_research":
            result.append(delivery)
            continue
        if _is_bare_framing_modality(spans):
            continue
        modality_ranges = [_span_range(query, span) for span in spans]
        if modality_ranges and all(
            any(_ranges_overlap(modality, specific) for specific in specific_ranges)
            for modality in modality_ranges
        ):
            continue
        result.append(delivery)
    return result


def _is_bare_framing_modality(spans: tuple[str, ...]) -> bool:
    bare_verbs = {"梳理", "解释", "分析", "研究", "看看", "讲清楚"}
    normalized = []
    for span in spans:
        value = span.strip(" ，,。！？!?")
        for prefix in ("请", "帮我", "麻烦"):
            if value.startswith(prefix):
                value = value[len(prefix):]
                break
        if value.endswith("一下"):
            value = value[:-2]
        normalized.append(value)
    return bool(normalized) and all(value in bare_verbs for value in normalized)


def _span_range(query: str, span: str) -> tuple[int, int]:
    start = query.find(span)
    return start, start + len(span)


def _ranges_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])
