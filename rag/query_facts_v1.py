"""Deterministic, route-neutral facts copied from a public Query and context."""

from __future__ import annotations

import re
from dataclasses import dataclass


ATR_ID = re.compile(r"ATR-\d{8}-[A-Z0-9]{6}", re.IGNORECASE)
BOOK_TITLE = re.compile(r"《([^》]+)》")
QUOTED = re.compile(r"[“\"]([^”\"]+)[”\"]")
TIME_WINDOW = re.compile(
    r"(?:近|最近|过去)\s*(?:(?:\d+|一|两|三|半)\s*(?:小时|天|周|个月|月|年)|一年)"
)
GENERIC_RECENCY = re.compile(r"最近|近期|最新")
PERCENTAGE = re.compile(r"\d+(?:\.\d+)?\s*%")
REFERENCE_LITERALS = (
    "左边那条", "左侧那条", "右边那条", "右侧那条",
    "上述说法", "该说法", "这句话", "这个", "它",
)
WEB_DENIALS = ("不要联网", "禁止联网", "别联网", "无需联网")
RELATION_LITERALS = ("是否否定", "是否反驳", "是否支持")


@dataclass(frozen=True)
class QueryFacts:
    protected_spans: tuple[str, ...]
    item_locator_precision: str
    unresolved_reference_spans: tuple[str, ...]
    resolved_references: tuple[tuple[str, str], ...]


def extract_query_facts_v1(
    query: str,
    dimensions: dict,
    conversation_context: str | None = None,
) -> QueryFacts:
    """Extract literal constraints and references without deciding a task route."""
    context = conversation_context or ""
    protected: list[str] = []

    for match in ATR_ID.finditer(query):
        _append(protected, match.group(0).upper())
    for pattern in (BOOK_TITLE, QUOTED):
        for match in pattern.finditer(query):
            _append(protected, match.group(1))
    for match in TIME_WINDOW.finditer(query):
        _append(protected, match.group(0))
    if not TIME_WINDOW.search(query):
        recency = GENERIC_RECENCY.search(query)
        if recency:
            _append(protected, recency.group(0))
    for match in PERCENTAGE.finditer(query):
        if not any(match.group(0).replace(" ", "") in value.replace(" ", "") for value in protected):
            _append(protected, match.group(0))
    for phrase in (*WEB_DENIALS, *RELATION_LITERALS):
        if phrase in query:
            _append(protected, phrase)

    _add_dimension_targets(query, dimensions, protected)

    resolved = _resolve_spatial_references(query, context)
    resolved_literals = {literal for literal, _ in resolved}
    unresolved = []
    for literal in REFERENCE_LITERALS:
        if literal not in query or literal in resolved_literals:
            continue
        if literal in {"它", "这个", "该说法", "这句话", "上述说法"} and _has_antecedent(query, literal):
            continue
        _append(unresolved, literal)
    for literal, _ in resolved:
        _append(protected, literal)
    for literal in unresolved:
        _append(protected, literal)

    item_state = dimensions["item_lookup"]["state"]
    if item_state != "present":
        precision = "none"
    elif ATR_ID.search(query) or BOOK_TITLE.search(query) or QUOTED.search(query):
        precision = "exact"
    else:
        precision = "partial"

    return QueryFacts(
        protected_spans=tuple(sorted(protected, key=query.find)),
        item_locator_precision=precision,
        unresolved_reference_spans=tuple(sorted(unresolved, key=query.find)),
        resolved_references=tuple(sorted(resolved, key=lambda item: query.find(item[0]))),
    )


def _add_dimension_targets(query: str, dimensions: dict, protected: list[str]) -> None:
    if dimensions["recent_update_set"]["state"] == "present":
        for evidence in dimensions["recent_update_set"]["evidence_spans"]:
            value = re.sub(r"^(?:并|再)?(?:汇总|补充|列出|看看|查找)\s*", "", evidence)
            value = TIME_WINDOW.sub("", value, count=1)
            value = GENERIC_RECENCY.sub("", value, count=1)
            value = value.lstrip(" 的")
            value = re.split(r"(?:重要动态|近期动态|最新动态|热门趋势|动态|新闻)", value, maxsplit=1)[0]
            value = re.sub(r"(?:有?什么|有哪些)$", "", value)
            value = value.strip(" ，,。！？!?").removesuffix("的")
            if value:
                _append(protected, value)

    if dimensions["cross_time_or_entity_structure"]["state"] == "present":
        window = TIME_WINDOW.search(query)
        if window:
            prefix = query[:window.start()]
            prefix = re.sub(r"^(?:先)?(?:请|帮我|梳理|分析|解释|看看)\s*", "", prefix)
            entity = prefix.strip(" ，,。！？!?")
            if entity:
                _append(protected, entity)
            tail = query[window.end():]
            target = re.match(r"\s*(.+?)(?:如何|怎么|怎样)?(?:演变|演进|变化|发展|迁移|重排)", tail)
            if target:
                value = target.group(1).strip(" ，,。！？!?")
                if value:
                    _append(protected, value)

    if dimensions["explanation_or_comparison"]["state"] == "present" and "比较" in query:
        match = re.search(r"比较\s*(.+?)\s+和\s+(.+?)(?:分别|各自|有什么|的区别|适合)", query)
        if match:
            _append(protected, match.group(1).strip())
            _append(protected, match.group(2).strip())


def _resolve_spatial_references(query: str, context: str) -> list[tuple[str, str]]:
    result = []
    for side, literals in (
        ("左", ("左边那条", "左侧那条")),
        ("右", ("右边那条", "右侧那条")),
    ):
        literal = next((value for value in literals if value in query), None)
        if not literal:
            continue
        labelled = re.search(
            rf"{side}(?:侧|边)[^。；;]{{0,80}}?({ATR_ID.pattern})",
            context,
            re.IGNORECASE,
        )
        item_id = labelled.group(1).upper() if labelled else None
        if item_id:
            result.append((literal, item_id))
    return result


def _has_antecedent(query: str, literal: str) -> bool:
    position = query.rfind(literal)
    if position <= 0:
        return False
    prefix = query[:position]
    return bool(
        BOOK_TITLE.search(prefix)
        or QUOTED.search(prefix)
        or ATR_ID.search(prefix)
    )


def _append(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)
