"""Deterministic minimum gold set for request-scoped web-search routing."""

from __future__ import annotations

from dataclasses import dataclass

from rag.query_understanding import analyze_query
from rag.web_search_policy import decide_web_search


@dataclass(frozen=True)
class RoutingGoldCase:
    case_id: str
    question: str
    requested_mode: str
    retrieval_status: str
    citations: list[dict]
    capability_available: bool
    expected_web: bool
    expected_reason: str


def evaluate_minimum_routing_gold_set(*, today: str) -> dict:
    cases = _minimum_gold_cases(today)
    rows = []
    for case in cases:
        decision = decide_web_search(
            analyze_query(case.question),
            requested_mode=case.requested_mode,
            retrieval_status=case.retrieval_status,
            citations=case.citations,
            capability_available=case.capability_available,
            today=today,
        )
        passed = (
            decision.should_search == case.expected_web
            and decision.reason == case.expected_reason
        )
        rows.append(
            {
                "case_id": case.case_id,
                "expected_web": case.expected_web,
                "actual_web": decision.should_search,
                "expected_reason": case.expected_reason,
                "actual_reason": decision.reason,
                "passed": passed,
            }
        )

    expected_web_rows = [row for row in rows if row["expected_web"]]
    expected_internal_rows = [row for row in rows if not row["expected_web"]]
    missed = sum(1 for row in expected_web_rows if not row["actual_web"])
    unnecessary = sum(1 for row in expected_internal_rows if row["actual_web"])
    return {
        "case_count": len(rows),
        "missed_web_rate": missed / len(expected_web_rows) if expected_web_rows else 0,
        "unnecessary_web_rate": (
            unnecessary / len(expected_internal_rows) if expected_internal_rows else 0
        ),
        "failed_cases": [row for row in rows if not row["passed"]],
        "rows": rows,
    }


def _minimum_gold_cases(today: str) -> list[RoutingGoldCase]:
    ready = {
        "date": today,
        "source": "内部日报",
        "title": "稳定知识",
        "citation_id": "gold/internal/1",
        "excerpt": "可引用的内部证据",
    }
    return [
        RoutingGoldCase("internal_ready", "解释一个稳定概念", "auto", "ready", [ready], True, False, "internal_ready"),
        RoutingGoldCase("explicit_web", "请联网搜索官方发布", "always", "ready", [ready], True, True, "user_forced"),
        RoutingGoldCase("explicit_internal", "只基于内部语料回答，不要联网", "always", "ready", [ready], True, False, "internal_only_constraint"),
        RoutingGoldCase("internal_empty", "一个内部没有的话题", "auto", "empty", [], True, True, "internal_empty"),
        RoutingGoldCase("internal_error", "稳定问题", "auto", "error", [], True, False, "internal_error"),
        RoutingGoldCase("capability_off", "请联网搜索", "always", "empty", [], False, False, "capability_unavailable"),
        RoutingGoldCase("freshness_gap", "OpenAI 最近有什么动态", "auto", "ready", [{**ready, "date": "2026-01-01"}], True, True, "freshness_gap"),
        RoutingGoldCase("entity_partial", "OpenAI 的产品策略是什么", "auto", "ready", [ready], True, True, "internal_partial"),
    ]
