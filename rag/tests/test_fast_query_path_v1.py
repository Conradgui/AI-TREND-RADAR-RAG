"""Frozen Fast Query Path v1 Gate: six accepts and three required fallbacks."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from rag.fast_query_path_v1 import parse_fast_query


ROOT = Path(__file__).resolve().parents[2]
QUERIES = ROOT / "docs/rag-transformation/evals/semantic-parse-v1-diagnostic-queries-2026-08-13.json"
GOLD = ROOT / "docs/rag-transformation/evals/semantic-parse-v1-diagnostic-gold-2026-08-13.json"

ACCEPT_IDS = (
    "RC2-SG-001", "RC2-SG-004", "RC2-SG-006", "RC2-SG-009",
    "RC2-SG-014", "RC2-SG-034",
)
FALLBACK_IDS = ("RC2-SG-017", "RC2-SG-020", "RC2-SG-039")


def _assets() -> tuple[dict, dict]:
    queries = {item["case_id"]: item for item in json.loads(QUERIES.read_text())["cases"]}
    gold = {item["case_id"]: item for item in json.loads(GOLD.read_text())["cases"]}
    return queries, gold


@pytest.mark.parametrize("case_id", ACCEPT_IDS)
def test_fast_path_accepts_only_frozen_high_confidence_cases(case_id: str) -> None:
    queries, gold = _assets()
    case = queries[case_id]
    expected = gold[case_id]

    outcome = parse_fast_query(case["query"], case.get("conversation_context"))

    assert outcome.status == "accepted", outcome.reason
    contract = outcome.contract.to_dict()
    assert contract["primary_task_family"] == expected["primary_task_family"]
    assert contract["answer_mode"] == expected["answer_mode"]
    assert contract["web_permission"] == expected["web_permission"]
    assert contract["resolved_references"] == expected["expected_resolved_references"]
    assert contract["protected_terms"] == expected["expected_protected_terms"]


@pytest.mark.parametrize("case_id", FALLBACK_IDS)
def test_fast_path_rejects_compound_queries_for_lean_fallback(case_id: str) -> None:
    queries, _ = _assets()
    case = queries[case_id]

    outcome = parse_fast_query(case["query"], case.get("conversation_context"))

    assert outcome.status == "fallback_required"
    assert outcome.contract is None
    assert "compound" in outcome.reason


def test_fast_path_gate_mean_latency_is_below_ten_milliseconds() -> None:
    queries, _ = _assets()
    started = time.perf_counter()
    for _ in range(100):
        for case_id in (*ACCEPT_IDS, *FALLBACK_IDS):
            case = queries[case_id]
            parse_fast_query(case["query"], case.get("conversation_context"))
    elapsed_ms = (time.perf_counter() - started) * 1000 / 900
    assert elapsed_ms < 10
