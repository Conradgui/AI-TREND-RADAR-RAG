"""Behavior tests for the Route Contract v2 shadow understanding seam."""

from __future__ import annotations

import json
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
