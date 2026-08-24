"""TDD contract for the dimensions-only L1 v2 replacement."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from rag.dimensions_only_l1_v2 import (
    DimensionsOnlyViolation,
    assemble_narrow_decisions_v2,
    validate_dimensions_only_v2,
)
from rag.narrow_route_contract_v2 import build_narrow_route_envelope


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "docs/rag-transformation/specs/dimensions-only-l1-v2.schema.json").read_text()
)
CALIBRATION = json.loads(
    (ROOT / "docs/rag-transformation/evals/narrow-semantic-decisions-v1-calibration-2026-08-13.json").read_text()
)["cases"]


def _dimensions(**present: str) -> dict:
    names = (
        "item_lookup",
        "recent_update_set",
        "cross_time_or_entity_structure",
        "truth_assessable_claim",
        "explanation_or_comparison",
    )
    return {
        "schema_version": "atr.semantic-dimensions/2.0",
        "dimensions": {
            name: {
                "state": "present" if name in present else "absent",
                "evidence_spans": [present[name]] if name in present else [],
            }
            for name in names
        },
    }


def _dimensions_from_case(case: dict) -> dict:
    value = _dimensions()
    for name, judgment in value["dimensions"].items():
        if name in case["present"]:
            judgment.update(state="present", evidence_spans=case["present"][name])
        elif name in case["uncertain"]:
            judgment.update(state="uncertain", evidence_spans=case["uncertain"][name])
    return value


def _legacy_gold(case: dict) -> dict:
    return {
        "schema_version": "atr.semantic-decisions/1.0",
        "dimensions": deepcopy(_dimensions_from_case(case)["dimensions"]),
        "protected_spans": case.get("protected_spans", []),
        "item_locator_precision": case.get("item_locator_precision", "none"),
        "unresolved_reference_spans": case["unresolved_reference_spans"],
        "resolved_references": case.get("resolved_references", []),
    }


def test_model_schema_contains_only_version_and_five_dimensions() -> None:
    properties = SCHEMA["properties"]

    assert set(properties) == {"schema_version", "dimensions"}
    assert SCHEMA["additionalProperties"] is False
    assert set(properties["dimensions"]["properties"]) == {
        "item_lookup",
        "recent_update_set",
        "cross_time_or_entity_structure",
        "truth_assessable_claim",
        "explanation_or_comparison",
    }
    encoded = json.dumps(SCHEMA, ensure_ascii=False)
    for forbidden in (
        "protected_spans",
        "item_locator_precision",
        "resolved_references",
        "unresolved_reference_spans",
        "primary_task_family",
    ):
        assert forbidden not in encoded


def test_dimensions_require_literal_query_evidence() -> None:
    query = "最近有什么热门趋势？"
    value = _dimensions(recent_update_set="伪造片段")

    Draft202012Validator(SCHEMA).validate(value)
    with pytest.raises(DimensionsOnlyViolation, match="literal Query text"):
        validate_dimensions_only_v2(query, value)


def test_complex_context_references_are_deterministic_not_model_fields() -> None:
    query = "核验左边那条所说的“延迟下降 40%”，并判断右边那条是否否定了它。"
    context = (
        "左侧是 ATR-20260702-D6M1QH《FjordServe 公布延迟测试》，"
        "右侧是 ATR-20260708-W3P9ZA《独立实验室复测 FjordServe》。"
    )
    model_value = _dimensions(
        truth_assessable_claim="核验左边那条所说的“延迟下降 40%”，并判断右边那条是否否定了它"
    )

    decisions = assemble_narrow_decisions_v2(query, model_value, context)
    envelope = build_narrow_route_envelope(query, decisions, context)

    assert envelope["status"] == "resolved"
    assert envelope["contract"]["primary_task_family"] == "claim_verification"
    assert decisions["resolved_references"] == [
        {"literal_span": "左边那条", "item_id": "ATR-20260702-D6M1QH"},
        {"literal_span": "右边那条", "item_id": "ATR-20260708-W3P9ZA"},
    ]
    assert decisions["unresolved_reference_spans"] == []
    assert {"左边那条", "延迟下降 40%", "右边那条", "是否否定"}.issubset(
        decisions["protected_spans"]
    )


def test_vague_reference_without_context_fails_closed() -> None:
    query = "解释这个为什么重要。"
    model_value = _dimensions(explanation_or_comparison="解释这个为什么重要")

    decisions = assemble_narrow_decisions_v2(query, model_value)
    envelope = build_narrow_route_envelope(query, decisions)

    assert decisions["unresolved_reference_spans"] == ["这个"]
    assert envelope["status"] == "clarification_required"
    assert envelope["contract"] is None


def test_unrelated_latin_token_does_not_resolve_a_vague_reference() -> None:
    query = "请用 JSON 输出，然后解释这个为什么重要。"
    model_value = _dimensions(
        explanation_or_comparison="解释这个为什么重要"
    )

    decisions = assemble_narrow_decisions_v2(query, model_value)

    assert decisions["unresolved_reference_spans"] == ["这个"]


def test_unlabelled_context_order_is_not_treated_as_left_right_evidence() -> None:
    query = "核验左边那条，并判断右边那条是否反驳它。"
    context = "候选记录包括 ATR-20260801-AA11BB 和 ATR-20260802-CC22DD。"
    model_value = _dimensions(
        truth_assessable_claim="核验左边那条，并判断右边那条是否反驳它"
    )

    decisions = assemble_narrow_decisions_v2(query, model_value, context)

    assert decisions["resolved_references"] == []
    assert decisions["unresolved_reference_spans"] == ["左边那条", "右边那条", "它"]


def test_exact_title_stays_navigation_with_explanation_support() -> None:
    query = "找到《Apple Is Getting This Wrong》这条新闻，并解释它为什么重要。"
    model_value = _dimensions(
        item_lookup="找到《Apple Is Getting This Wrong》这条新闻",
        explanation_or_comparison="解释它为什么重要",
    )

    decisions = assemble_narrow_decisions_v2(query, model_value)
    envelope = build_narrow_route_envelope(query, decisions)

    assert decisions["item_locator_precision"] == "exact"
    assert decisions["unresolved_reference_spans"] == []
    assert envelope["contract"]["primary_task_family"] == "item_navigation"
    assert envelope["contract"]["supporting_task_families"] == ["evidence_research"]
    assert "Apple Is Getting This Wrong" in envelope["contract"]["protected_terms"]


@pytest.mark.parametrize("case", CALIBRATION, ids=lambda case: case["case_id"])
def test_deterministic_assembler_preserves_visible_route_contract(case: dict) -> None:
    query = case["query"]
    context = case.get("conversation_context")
    expected = build_narrow_route_envelope(query, _legacy_gold(case), context)
    decisions = assemble_narrow_decisions_v2(
        query, _dimensions_from_case(case), context
    )
    actual = build_narrow_route_envelope(query, decisions, context)

    assert actual["status"] == expected["status"]
    if actual["status"] == "resolved":
        for field in (
            "primary_task_family",
            "supporting_task_families",
            "answer_mode",
            "protected_terms",
            "resolved_references",
            "web_permission",
        ):
            assert actual["contract"][field] == expected["contract"][field]
