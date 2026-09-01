"""Behavior tests for the Route Contract v2 shadow understanding seam."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator

from rag.query_understanding_v2 import understand_query_v2
from rag.route_contract_validation import validate_route_contract_semantics


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "docs/rag-transformation/specs/route-contract-v2.schema.json").read_text(
        encoding="utf-8"
    )
)
VALIDATOR = Draft202012Validator(SCHEMA)
DATASET = json.loads(
    (ROOT / "docs/rag-transformation/evals/route-contract-v2-development-2026-08-13.json").read_text(
        encoding="utf-8"
    )
)


def test_exact_atr_query_returns_a_valid_deterministic_navigation_contract() -> None:
    contract = understand_query_v2("打开 ATR-20260805-99E550").to_dict()

    VALIDATOR.validate(contract)
    validate_route_contract_semantics(contract)
    assert contract["original_query"] == "打开 ATR-20260805-99E550"
    assert contract["primary_task_family"] == "item_navigation"
    assert contract["answer_mode"] == "exact_item"
    assert contract["protected_terms"] == ["ATR-20260805-99E550"]
    assert contract["prompt_contract_id"] is None
    assert contract["answer_builder_contract_id"] == "atr.answer_builder/item_navigation/1.0"


def test_explicit_iso_cutoff_is_preserved_as_a_machine_readable_time_bound() -> None:
    contract = understand_query_v2(
        "Graphify 和 claude-mem 截至 2026-08-21 分别做什么？"
    ).to_dict()

    VALIDATOR.validate(contract)
    validate_route_contract_semantics(contract)
    assert contract["temporal_constraint"] == {
        "mode": "absolute_range",
        "value": "2000-01-01 | 2026-08-21",
        "surface": "截至 2026-08-21",
        "start": "2000-01-01",
        "end": "2026-08-21",
    }


def test_month_day_cutoff_overrides_relative_recency_and_anchors_the_window() -> None:
    contract = understand_query_v2(
        "截至 8 月 21 日，过去一周 OpenAI 有哪些值得关注的业务或产品动态？"
    ).to_dict()

    assert contract["temporal_constraint"] == {
        "mode": "absolute_range",
        "value": f"{date.today().year:04d}-08-15 | {date.today().year:04d}-08-21",
        "surface": "截至 8 月 21 日",
        "start": f"{date.today().year:04d}-08-15",
        "end": f"{date.today().year:04d}-08-21",
    }


def test_all_navigation_development_cases_use_the_deterministic_a_route() -> None:
    cases = [
        case
        for case in DATASET["cases"]
        if case["expected"]["primary_task_family"] == "item_navigation"
    ]
    assert len(cases) == 5

    for case in cases:
        contract = understand_query_v2(case["query"]).to_dict()
        expected = case["expected"]
        VALIDATOR.validate(contract)
        validate_route_contract_semantics(contract)
        assert contract["original_query"] == expected["original_query"]
        assert contract["primary_task_family"] == "item_navigation"
        assert contract["answer_mode"] == expected["answer_mode"]
        assert contract["prompt_contract_id"] is None
        assert contract["answer_builder_contract_id"] == expected["answer_builder_contract_id"]


def test_all_25_development_queries_match_the_confirmed_route_projection() -> None:
    assert len(DATASET["cases"]) == 25

    for case in DATASET["cases"]:
        contract = understand_query_v2(case["query"]).to_dict()
        expected = case["expected"]
        VALIDATOR.validate(contract)
        validate_route_contract_semantics(contract)

        assert contract["original_query"] == expected["original_query"], case["case_id"]
        assert set(contract["intent_signals"]) == set(expected["intent_signals"]), case["case_id"]
        assert contract["primary_task_family"] == expected["primary_task_family"], case["case_id"]
        assert contract["supporting_task_families"] == expected["supporting_task_families"], case["case_id"]
        assert contract["answer_mode"] == expected["answer_mode"], case["case_id"]
        assert contract["web_permission"] == expected["web_permission"], case["case_id"]
        assert contract["prompt_contract_id"] == expected["prompt_contract_id"], case["case_id"]
        assert contract["answer_builder_contract_id"] == expected["answer_builder_contract_id"], case["case_id"]

        for term in expected["preserve_tokens"]:
            assert any(term.casefold() in protected.casefold() for protected in contract["protected_terms"]), (
                case["case_id"],
                term,
                contract["protected_terms"],
            )
