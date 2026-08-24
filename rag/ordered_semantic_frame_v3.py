"""Validate an ordered semantic frame and project it to Route Contract v2.

This is a shadow-only Slice-1 seam. It does not call a model, rewrite a query,
retrieve evidence, or modify the production chat path.
"""

from __future__ import annotations

import json
import re
import uuid
from calendar import monthrange
from pathlib import Path

from jsonschema import Draft202012Validator

from rag.query_understanding_v2 import RouteContractV2, _ROUTE_POLICIES, _supporting_contract


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/rag-transformation/specs/ordered-semantic-frame-v3.schema.json"

_ATR_ID = re.compile(r"ATR-\d{8}-[A-Z0-9]{6}", re.IGNORECASE)
_BOOK_TITLE = re.compile(r"《([^》]+)》")
_QUOTED = re.compile(r"[“\"‘']([^”\"’']+)[”\"’']")
_TIME_WINDOW = re.compile(
    r"(?:近|最近|过去)\s*(?:(?:\d+|一|两|三|半)\s*(?:小时|天|周|个月|月|年)|一年)"
)
_ABSOLUTE_DATE = re.compile(r"20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
_ABSOLUTE_PERIOD = re.compile(
    r"20\d{2}\s*年(?:\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?)?"
)
_LATEST = re.compile(r"最近|近期|最新")
_OFFICIAL_SOURCE = re.compile(
    r"([A-Za-z][A-Za-z0-9._-]*(?:\s+[A-Za-z0-9._-]+){0,2})\s*官方",
    re.IGNORECASE,
)
_CONTEXT_CLAIM = re.compile(
    r"(?:说法|主张)(?:是|为)\s*[：:]\s*[“\"‘']?(.+?)[”\"’']?(?:[。！？]|$)"
)
_CLAIM_REFERENCES = ("这个说法", "该说法", "上述说法")
_BARE_REFERENCE = re.compile(
    r"(?<![A-Za-z0-9])(?:它|该项|这项发布|该发布|这件事|那件事|前者|后者)(?![A-Za-z0-9])"
)

_OUTPUT_FORMS = {
    "item_navigation": {"exact_item", "item_disambiguation"},
    "trend_discovery": {"important_news", "trend_clusters"},
    "temporal_relation_exploration": {
        "timeline", "relation", "longitudinal_trend", "cross_sectional_trend"
    },
    "claim_verification": {"verification_verdict"},
    "evidence_research": {"explanation", "comparison", "deep_research"},
}
_INTENT_SIGNAL = {
    "item_navigation": "navigation",
    "trend_discovery": "recency",
    "temporal_relation_exploration": "timeline",
    "claim_verification": "verification",
    "evidence_research": "explanation",
}


class OrderedSemanticFrameViolation(ValueError):
    pass


def validate_ordered_semantic_frame_v3(query: str, frame: dict) -> None:
    errors = sorted(
        Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).iter_errors(frame),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        raise OrderedSemanticFrameViolation(
            "schema violation: " + "; ".join(error.message for error in errors)
        )

    for delivery in frame["deliveries"]:
        family = delivery["task_family"]
        output = delivery["requested_output_form"]
        locator = delivery["locator_kind"]
        if output not in _OUTPUT_FORMS[family]:
            raise OrderedSemanticFrameViolation(
                f"{output} is not valid for {family}"
            )
        if family == "item_navigation" and locator == "none":
            raise OrderedSemanticFrameViolation("item_navigation requires locator_kind")
        if family != "item_navigation" and locator != "none":
            raise OrderedSemanticFrameViolation(
                "locator_kind is only valid for item_navigation"
            )
        _require_literal_spans(query, delivery["evidence_spans"])

    _require_literal_spans(query, frame["protected_spans"])
    _require_literal_spans(query, frame.get("claim_spans", []))
    _require_literal_spans(query, frame.get("subject_spans", []))
    _require_literal_spans(query, frame.get("source_spans", []))
    _require_literal_spans(query, frame["web_evidence_spans"])
    _require_literal_spans(query, frame["unresolved_reference_spans"])
    if frame["web_permission"] in {"forbidden", "explicit"} and not frame["web_evidence_spans"]:
        raise OrderedSemanticFrameViolation(
            f'{frame["web_permission"]} web permission requires evidence'
        )


def build_ordered_route_envelope_v3(
    original_query: str,
    frame: dict,
    conversation_context: str | None = None,
) -> dict:
    """Project one scripted or model-produced Frame to the stable route envelope."""
    query = original_query.strip()
    if not query:
        raise OrderedSemanticFrameViolation("original_query cannot be empty")
    validate_ordered_semantic_frame_v3(query, frame)

    if not frame["deliveries"]:
        return {
            "status": "clarification_required",
            "contract": None,
            "reasons": ["no unambiguous user delivery was identified"],
        }

    context = conversation_context or ""
    references = _resolve_public_references(query, context)
    contextual_claims = _resolve_context_claims(query, context)
    resolved_literals = {
        literal for literal, _ in [*references, *contextual_claims]
    }
    unresolved_candidates = list(frame["unresolved_reference_spans"])
    for span in _detect_unresolved_claim_references(query, contextual_claims):
        _append(unresolved_candidates, span)
    if not context:
        for match in _BARE_REFERENCE.finditer(query):
            if not _has_preceding_query_antecedent(query, match.start(), frame):
                _append(unresolved_candidates, match.group(0))
    unresolved = [
        span for span in unresolved_candidates
        if span not in resolved_literals
    ]
    if unresolved:
        return {
            "status": "clarification_required",
            "contract": None,
            "reasons": ["unresolved references: " + ", ".join(unresolved)],
        }

    deliveries = _merge_deliveries(frame["deliveries"])
    primary_delivery = deliveries[0]
    primary = primary_delivery["task_family"]
    supporting = [delivery["task_family"] for delivery in deliveries[1:]]
    locator = primary_delivery["locator_kind"]
    protected = _protected_terms(query, frame, references)
    try:
        temporal = _temporal_constraint(query)
    except (OrderedSemanticFrameViolation, ValueError) as exc:
        return {
            "status": "clarification_required",
            "contract": None,
            "reasons": [str(exc)],
        }
    if (
        temporal["mode"] == "absolute_range"
        and temporal["start"] > temporal["end"]
    ):
        return {
            "status": "clarification_required",
            "contract": None,
            "reasons": ["absolute time range starts after it ends"],
        }

    common = dict(
        schema_version="atr.route/2.0",
        request_id="shadow-frame-v3-" + uuid.uuid5(
            uuid.NAMESPACE_URL, query + "\0" + (conversation_context or "")
        ).hex,
        original_query=query,
        protected_terms=protected,
        intent_signals=_intent_signals(deliveries, frame["web_permission"]),
        primary_task_family=primary,
        supporting_task_families=supporting,
        answer_mode=(
            _navigation_output(locator)
            if primary == "item_navigation"
            else primary_delivery["requested_output_form"]
        ),
        route_confidence=0.65 if locator in {"title_fragment", "descriptive"} else 1.0,
        ambiguities=(
            ["item locator may match multiple records"]
            if primary == "item_navigation" and locator in {"title_fragment", "descriptive"}
            else []
        ),
        delivery_contracts=[
            {
                "task_family": delivery["task_family"],
                "requested_output_form": delivery["requested_output_form"],
                "locator_kind": delivery["locator_kind"],
            }
            for delivery in deliveries
        ],
        resolved_references=[
            {
                "reference_type": "item_id",
                "value": item_id,
                "origin": "conversation_context",
            }
            for _, item_id in references
        ],
        supporting_contracts=[
            _supporting_contract(
                delivery["task_family"],
                requested_output_form=(
                    _navigation_output(delivery["locator_kind"])
                    if delivery["task_family"] == "item_navigation"
                    else delivery["requested_output_form"]
                ),
                locator_kind=delivery["locator_kind"],
            )
            for delivery in deliveries[1:]
        ],
        subjects=list(frame.get("subject_spans", [])),
        claims=_ordered_unique([
            *[claim for _, claim in contextual_claims],
            *frame.get("claim_spans", []),
        ]),
        temporal_constraint=temporal,
        source_constraint=_source_constraint(query, frame.get("source_spans", [])),
        web_permission=frame["web_permission"],
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


def _require_literal_spans(query: str, spans: list[str]) -> None:
    for span in spans:
        if span not in query:
            raise OrderedSemanticFrameViolation(
                f"span is not literal Query text: {span}"
            )


def _navigation_output(locator_kind: str) -> str:
    return (
        "item_disambiguation"
        if locator_kind in {"title_fragment", "descriptive"}
        else "exact_item"
    )


def _merge_deliveries(deliveries: list[dict]) -> list[dict]:
    merged = []
    by_family = {}
    for delivery in deliveries:
        family = delivery["task_family"]
        previous = by_family.get(family)
        if previous is None:
            copy = {**delivery, "evidence_spans": list(delivery["evidence_spans"])}
            by_family[family] = copy
            merged.append(copy)
            continue
        if (
            previous["requested_output_form"] != delivery["requested_output_form"]
            or previous["locator_kind"] != delivery["locator_kind"]
        ):
            raise OrderedSemanticFrameViolation(
                f"conflicting duplicate delivery for {family}"
            )
        for span in delivery["evidence_spans"]:
            if span not in previous["evidence_spans"]:
                previous["evidence_spans"].append(span)
    return merged


def _protected_terms(query: str, frame: dict, references: list[tuple[str, str]]) -> list[str]:
    terms = list(frame["protected_spans"])
    for pattern in (_ATR_ID, _TIME_WINDOW, _ABSOLUTE_DATE):
        for match in pattern.finditer(query):
            _append(terms, match.group(0).upper() if pattern is _ATR_ID else match.group(0))
    for pattern in (_BOOK_TITLE, _QUOTED):
        for match in pattern.finditer(query):
            _append(terms, match.group(1))
    for literal, _ in references:
        _append(terms, literal)
    for literal in frame["unresolved_reference_spans"]:
        _append(terms, literal)
    return sorted(terms, key=query.find)


def _resolve_public_references(query: str, context: str) -> list[tuple[str, str]]:
    result = []
    for side, literals in (
        ("左", ("左边那条", "左侧那条")),
        ("右", ("右边那条", "右侧那条")),
    ):
        literal = next((candidate for candidate in literals if candidate in query), None)
        if not literal:
            continue
        match = re.search(
            rf"{side}(?:侧|边)[^。；;]{{0,80}}?({_ATR_ID.pattern})",
            context,
            re.IGNORECASE,
        )
        if match:
            result.append((literal, match.group(1).upper()))
    return result


def _resolve_context_claims(query: str, context: str) -> list[tuple[str, str]]:
    literal = next((candidate for candidate in _CLAIM_REFERENCES if candidate in query), None)
    if not literal or not context:
        return []
    match = _CONTEXT_CLAIM.search(context)
    if not match:
        return []
    claim = match.group(1).strip().strip("“”\"‘’'")
    return [(literal, claim)] if claim else []


def _detect_unresolved_claim_references(
    query: str,
    contextual_claims: list[tuple[str, str]],
) -> list[str]:
    if contextual_claims:
        return []
    literal = next((candidate for candidate in _CLAIM_REFERENCES if candidate in query), None)
    if not literal:
        return []
    suffix = query.split(literal, 1)[1]
    if _QUOTED.search(suffix) or re.search(r"[：:]\s*\S{4,}", suffix):
        return []
    return [literal]


def _has_preceding_query_antecedent(query: str, reference_start: int, frame: dict) -> bool:
    """Accept only an observable earlier subject in the same Query."""
    for pattern in (_ATR_ID, _BOOK_TITLE):
        if any(match.start() < reference_start for match in pattern.finditer(query)):
            return True
    return any(
        isinstance(span, str)
        and span
        and query.find(span) != -1
        and query.find(span) < reference_start
        for span in frame.get("subject_spans", [])
    )


def _intent_signals(deliveries: list[dict], web_permission: str) -> list[str]:
    signals = []
    for delivery in deliveries:
        signal = _INTENT_SIGNAL[delivery["task_family"]]
        if delivery["requested_output_form"] in {"comparison", "deep_research", "relation"}:
            signal = delivery["requested_output_form"]
        _append(signals, signal)
    if web_permission == "explicit":
        _append(signals, "web_requested")
    return signals


def _temporal_constraint(query: str) -> dict:
    match = _TIME_WINDOW.search(query)
    if match:
        return {"mode": "relative_window", "value": match.group(0)}
    period_matches = list(_ABSOLUTE_PERIOD.finditer(query))
    periods = list(dict.fromkeys(match.group(0) for match in period_matches))
    if periods:
        start, _ = _absolute_period_bounds(periods[0])
        _, end = _absolute_period_bounds(periods[-1])
        return {
            "mode": "absolute_range",
            "value": " | ".join(periods),
            "surface": query[period_matches[0].start():period_matches[-1].end()],
            "start": start,
            "end": end,
        }
    latest = _LATEST.search(query)
    if latest:
        return {"mode": "latest", "value": latest.group(0)}
    return {"mode": "none", "value": None}


def _absolute_period_bounds(surface: str) -> tuple[str, str]:
    match = re.fullmatch(
        r"(?P<year>20\d{2})\s*年(?:\s*(?P<month>\d{1,2})\s*月(?:\s*(?P<day>\d{1,2})\s*日)?)?",
        surface,
    )
    if not match:
        raise OrderedSemanticFrameViolation(f"invalid absolute period: {surface}")
    year = int(match.group("year"))
    month = int(match.group("month") or 1)
    day = int(match.group("day") or 1)
    start = f"{year:04d}-{month:02d}-{day:02d}"
    if match.group("day"):
        return start, start
    if match.group("month"):
        return start, f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}"
    return start, f"{year:04d}-12-31"


def _source_constraint(query: str, source_spans: list[str] | None = None) -> dict:
    requested = []
    for literal in ("内部日报", "内部语料", "内部知识库"):
        if literal in query:
            _append(requested, literal)
    for match in _OFFICIAL_SOURCE.finditer(query):
        _append(requested, match.group(1).strip())
    for source in source_spans or []:
        _append(requested, source)
    return {"requested_sources": requested, "official_first": "官方" in query}


def _append(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _ordered_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        _append(result, value)
    return result
