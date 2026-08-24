"""Conservative deterministic Fast Path for high-confidence Query contracts."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from rag.query_understanding_v2 import RouteContractV2, _ROUTE_POLICIES


_ATR_ID = re.compile(r"\bATR-\d{8}-[A-Z0-9]{6}\b", re.IGNORECASE)
_BOOK_TITLE = re.compile(r"《([^》]+)》")
_QUOTED = re.compile(r"[“\"]([^”\"]+)[”\"]")
_FULL_CN_DATE = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
_RECENT_PERIOD = re.compile(r"(?:近|最近|过去)\s*(?:\d+|一|两|三|半)\s*(?:小时|天|周|个月|月|季度|年)")
_CONTEXT_ITEM = re.compile(r"ATR-\d{8}-[A-Z0-9]{6}", re.IGNORECASE)
_WEB_DENIALS = ("不要联网", "禁止联网", "别联网", "无需联网")


@dataclass(frozen=True)
class FastPathOutcome:
    status: str
    reason: str
    contract: RouteContractV2 | None = None


def parse_fast_query(query: str, conversation_context: str | None = None) -> FastPathOutcome:
    """Accept only deterministic single-task Queries; otherwise require fallback."""
    original = query.strip()
    if not original:
        return FastPathOutcome("fallback_required", "empty query")
    if _is_compound(original):
        return FastPathOutcome("fallback_required", "compound task requires Task Atom fallback")

    navigation = _navigation_contract(original, conversation_context)
    if navigation is not None:
        return FastPathOutcome("accepted", "deterministic item locator", navigation)

    verification = _verification_contract(original)
    if verification is not None:
        return FastPathOutcome("accepted", "deterministic verification claim", verification)

    discovery = _discovery_contract(original)
    if discovery is not None:
        return FastPathOutcome("accepted", "deterministic recent trend request", discovery)

    return FastPathOutcome("fallback_required", "no high-confidence fast-path contract")


def _navigation_contract(query: str, context: str | None) -> RouteContractV2 | None:
    if not any(term in query for term in ("打开", "查看", "定位", "条目", "记录", "那篇")):
        return None
    protected: list[str] = []
    ambiguities: list[str] = []
    resolved = []
    exact = True

    book = _BOOK_TITLE.search(query)
    date = _FULL_CN_DATE.search(query)
    quoted = _QUOTED.search(query)
    spatial = [term for term in ("左边那条", "右边那条") if term in query]

    if spatial:
        ids = [match.group(0).upper() for match in _CONTEXT_ITEM.finditer(context or "")]
        if len(ids) < 2:
            return FastPathOutcome("fallback_required", "spatial reference lacks stable context").contract
        mapping = {"左边那条": ids[0], "右边那条": ids[1]}
        for term in spatial:
            protected.append(term)
            resolved.append({
                "reference_type": "item_id", "value": mapping[term],
                "origin": "conversation_context",
            })
    elif date and quoted and "来源" in query:
        source_match = re.search(r"来源(?:为|是)?\s*([^、，,]+)", query)
        if not source_match:
            return None
        protected.extend((date.group(0), source_match.group(1).strip(), quoted.group(1)))
    elif book and "标题" not in query:
        protected.append(book.group(1))
    elif quoted and any(term in query for term in ("标题里有", "标题含", "标题包含", "题目包含")):
        protected.append(quoted.group(1))
        exact = False
        ambiguities.append("title fragment may match multiple records")
    else:
        atr = _ATR_ID.search(query)
        if not atr:
            return None
        protected.append(atr.group(0).upper())

    return RouteContractV2(
        schema_version="atr.route/2.0",
        request_id=_request_id(query, context),
        original_query=query,
        protected_terms=protected,
        intent_signals=["navigation"],
        primary_task_family="item_navigation",
        supporting_task_families=[],
        answer_mode="exact_item" if exact else "item_disambiguation",
        route_confidence=1.0 if exact else 0.55,
        ambiguities=ambiguities,
        resolved_references=resolved,
        web_permission="on_demand",
    )


def _verification_contract(query: str) -> RouteContractV2 | None:
    if not any(term in query for term in ("核验", "验证", "判断", "是真的吗", "是否属实", "对吗")):
        return None
    quoted = _QUOTED.search(query)
    if not quoted:
        return None
    claim = quoted.group(1)
    subject, predicate = _split_claim(claim)
    protected = _hard_prefix_spans(query)
    for value in ("库内证据" if "库内证据" in query else None, subject, predicate):
        if value and value not in protected:
            protected.append(value)
    return _non_navigation_contract(
        query=query,
        route="claim_verification",
        mode="verification_verdict",
        signals=["verification", *( ["source_specific"] if "库内" in query else [])],
        protected=protected,
        subjects=[subject],
        claims=[claim],
        web_permission="forbidden" if any(term in query for term in _WEB_DENIALS) else "on_demand",
    )


def _discovery_contract(query: str) -> RouteContractV2 | None:
    period = _RECENT_PERIOD.search(query)
    if not period or not any(term in query for term in ("动向", "动态", "趋势", "热点", "消息", "新闻")):
        return None
    if not any(term in query for term in ("总结", "汇总", "梳理", "有哪些", "找出")):
        return None
    subject_match = re.search(
        re.escape(period.group(0)) + r"(.+?)(?:的)?(?:新动向|重要动态|动态|趋势|热点|消息|新闻)",
        query,
    )
    if not subject_match:
        return None
    subject = subject_match.group(1).strip("，, 的")
    protected = _hard_prefix_spans(query)
    if "只用库内资料" in query:
        protected.append("只用库内资料")
    protected.extend(value for value in (period.group(0), subject) if value not in protected)
    signals = ["recency", "trend"]
    if "库内" in query:
        signals.append("source_specific")
    return _non_navigation_contract(
        query=query,
        route="trend_discovery",
        mode="trend_clusters",
        signals=signals,
        protected=protected,
        subjects=[subject],
        claims=[],
        web_permission="forbidden" if any(term in query for term in _WEB_DENIALS) else "on_demand",
    )


def _non_navigation_contract(
    *, query: str, route: str, mode: str, signals: list[str], protected: list[str],
    subjects: list[str], claims: list[str], web_permission: str,
) -> RouteContractV2:
    rewrite, retrieval, prompt, output, budget = _ROUTE_POLICIES[route]
    return RouteContractV2(
        schema_version="atr.route/2.0", request_id=_request_id(query, None),
        original_query=query, protected_terms=protected, intent_signals=signals,
        primary_task_family=route, supporting_task_families=[], answer_mode=mode,
        route_confidence=0.98, ambiguities=[], subjects=subjects, claims=claims,
        web_permission=web_permission, rewrite_policy_id=rewrite,
        retrieval_policy_id=retrieval, prompt_contract_id=prompt,
        answer_builder_contract_id=None, output_schema_id=output, budget_profile_id=budget,
    )


def _is_compound(query: str) -> bool:
    action_groups = (
        ("打开", "定位", "查看"),
        ("汇总", "总结", "找", "梳理"),
        ("核验", "验证", "判断"),
        ("合作方", "关系", "否定"),
    )
    present = sum(any(term in query for term in group) for group in action_groups)
    return present >= 2 and any(term in query for term in ("并", "再", "同时", "是否否定"))


def _hard_prefix_spans(query: str) -> list[str]:
    return [term for term in _WEB_DENIALS if term in query]


def _split_claim(claim: str) -> tuple[str, str]:
    match = re.match(r"(.+?)(并未|没有|已经|已)(.+)", claim)
    if match:
        return match.group(1), match.group(2) + match.group(3)
    return claim, claim


def _request_id(query: str, context: str | None) -> str:
    return f"shadow-fast-{uuid.uuid5(uuid.NAMESPACE_URL, query + chr(0) + (context or '')).hex}"
