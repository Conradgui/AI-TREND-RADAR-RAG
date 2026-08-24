"""Offline contract and degradation tests for narrow semantic decisions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from rag.narrow_semantic_decisions_v1 import (
    DIMENSION_TO_ROUTE,
    NarrowDecisionViolation,
    project_narrow_decisions,
    validate_narrow_decisions,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "docs/rag-transformation/specs/narrow-semantic-decisions-v1.schema.json"
DATASET = ROOT / "docs/rag-transformation/evals/narrow-semantic-decisions-v1-calibration-2026-08-13.json"


def _payload(case: dict) -> dict:
    dimensions = {}
    for name in DIMENSION_TO_ROUTE:
        if name in case["present"]:
            state, spans = "present", case["present"][name]
        elif name in case["uncertain"]:
            state, spans = "uncertain", case["uncertain"][name]
        else:
            state, spans = "absent", []
        dimensions[name] = {"state": state, "evidence_spans": spans}
    return {
        "schema_version": "atr.semantic-decisions/1.0",
        "dimensions": dimensions,
        "protected_spans": case.get("protected_spans", []),
        "item_locator_precision": case.get("item_locator_precision", "none"),
        "unresolved_reference_spans": case["unresolved_reference_spans"],
        "resolved_references": case.get("resolved_references", []),
    }


def test_schema_and_twelve_case_asset_are_valid() -> None:
    schema = json.loads(SCHEMA.read_text())
    cases = json.loads(DATASET.read_text())["cases"]
    assert len(cases) == 12
    assert len({case["case_id"] for case in cases}) == 12
    for case in cases:
        Draft202012Validator(schema).validate(_payload(case))


@pytest.mark.parametrize("case", json.loads(DATASET.read_text())["cases"], ids=lambda case: case["case_id"])
def test_visible_calibration_projects_expected_primary_and_supporting(case: dict) -> None:
    result = project_narrow_decisions(
        case["query"], _payload(case), case.get("conversation_context")
    )
    assert result.status == case["expected_status"]
    assert result.primary_task_family == case["expected_primary"]
    assert list(result.supporting_task_families) == case["expected_supporting"]


def test_route_or_policy_fields_are_forbidden() -> None:
    case = json.loads(DATASET.read_text())["cases"][2]
    value = _payload(case)
    value["primary_task_family"] = "trend_discovery"
    with pytest.raises(NarrowDecisionViolation, match="schema"):
        validate_narrow_decisions(case["query"], value)


def test_l1_cannot_self_report_or_replace_the_real_query() -> None:
    case = json.loads(DATASET.read_text())["cases"][2]
    value = _payload(case)
    value["original_query"] = case["query"]
    with pytest.raises(NarrowDecisionViolation, match="schema"):
        validate_narrow_decisions(case["query"], value)

    value = _payload(case)
    value["dimensions"]["recent_update_set"]["evidence_spans"] = ["伪造的动态请求"]
    with pytest.raises(NarrowDecisionViolation, match="literal"):
        validate_narrow_decisions(case["query"], value)


def test_present_or_uncertain_judgment_requires_literal_evidence() -> None:
    case = json.loads(DATASET.read_text())["cases"][2]
    value = _payload(case)
    value["dimensions"]["recent_update_set"]["evidence_spans"] = []
    with pytest.raises(NarrowDecisionViolation, match="evidence"):
        validate_narrow_decisions(case["query"], value)

    value = _payload(case)
    value["dimensions"]["recent_update_set"]["evidence_spans"] = ["模型水印生态"]
    with pytest.raises(NarrowDecisionViolation, match="literal"):
        validate_narrow_decisions(case["query"], value)


def test_absent_judgment_cannot_carry_evidence() -> None:
    case = json.loads(DATASET.read_text())["cases"][5]
    value = _payload(case)
    value["dimensions"]["item_lookup"]["evidence_spans"] = ["比较"]
    with pytest.raises(NarrowDecisionViolation, match="absent"):
        validate_narrow_decisions(case["query"], value)


def test_uncertainty_unresolved_reference_and_empty_delivery_fail_closed() -> None:
    cases = json.loads(DATASET.read_text())["cases"]
    for index in (8, 9, 11):
        result = project_narrow_decisions(cases[index]["query"], _payload(cases[index]))
        assert result.status == "clarification_required"
        assert result.primary_task_family is None
        assert result.supporting_task_families == ()


def test_query_order_not_model_preference_selects_primary_delivery() -> None:
    cases = json.loads(DATASET.read_text())["cases"]
    b_then_d = project_narrow_decisions(cases[2]["query"], _payload(cases[2]))
    d_then_b = project_narrow_decisions(cases[3]["query"], _payload(cases[3]))
    assert (b_then_d.primary_task_family, b_then_d.supporting_task_families) == (
        "trend_discovery", ("claim_verification",)
    )
    assert (d_then_b.primary_task_family, d_then_b.supporting_task_families) == (
        "claim_verification", ("trend_discovery",)
    )


def test_same_evidence_start_for_two_dimensions_requires_clarification() -> None:
    query = "梳理近期变化"
    value = _payload({
        "query": query,
        "present": {
            "recent_update_set": [query],
            "cross_time_or_entity_structure": [query],
        },
        "uncertain": {}, "unresolved_reference_spans": [],
    })
    result = project_narrow_decisions(query, value)
    assert result.status == "clarification_required"
    assert any("same evidence position" in reason for reason in result.reasons)


def test_explanation_modality_does_not_override_a_more_specific_delivery() -> None:
    query = "解释 OpenAI 过去一年 Agent 战略如何演变。"
    value = _payload({
        "query": query,
        "present": {
            "cross_time_or_entity_structure": ["OpenAI 过去一年 Agent 战略如何演变"],
            "explanation_or_comparison": ["解释 OpenAI 过去一年 Agent 战略如何演变"],
        },
        "uncertain": {}, "unresolved_reference_spans": [],
    })

    result = project_narrow_decisions(query, value)

    assert result.status == "resolved"
    assert result.primary_task_family == "temporal_relation_exploration"
    assert result.supporting_task_families == ()


def test_bare_framing_verb_does_not_override_a_specific_temporal_delivery() -> None:
    query = "梳理 Nimbus 过去两年安全路线如何演变。"
    value = _payload({
        "query": query,
        "present": {
            "cross_time_or_entity_structure": ["过去两年安全路线如何演变"],
            "explanation_or_comparison": ["梳理"],
        },
        "uncertain": {}, "unresolved_reference_spans": [],
    })

    result = project_narrow_decisions(query, value)

    assert result.status == "resolved"
    assert result.primary_task_family == "temporal_relation_exploration"
    assert result.supporting_task_families == ()


def test_context_item_references_survive_projection_and_are_verified() -> None:
    case = json.loads(DATASET.read_text())["cases"][6]
    result = project_narrow_decisions(
        case["query"], _payload(case), case["conversation_context"]
    )
    assert result.resolved_references == (
        ("左边那条", "ATR-20260702-D6M1QH", "conversation_context"),
        ("右边那条", "ATR-20260708-W3P9ZA", "conversation_context"),
    )

    value = _payload(case)
    value["resolved_references"][0]["item_id"] = "ATR-20260101-AAAAAA"
    with pytest.raises(NarrowDecisionViolation, match="public context"):
        project_narrow_decisions(case["query"], value, case["conversation_context"])


def test_protected_spans_must_be_literal_and_locator_precision_matches_item_lookup() -> None:
    exact = _payload(json.loads(DATASET.read_text())["cases"][0])
    validate_narrow_decisions("找 ATR-20260805-99E550 这条记录。", exact)

    exact["protected_spans"] = ["不存在的标题"]
    with pytest.raises(NarrowDecisionViolation, match="protected span"):
        validate_narrow_decisions("找 ATR-20260805-99E550 这条记录。", exact)

    non_navigation = _payload(json.loads(DATASET.read_text())["cases"][2])
    non_navigation["item_locator_precision"] = "partial"
    with pytest.raises(NarrowDecisionViolation, match="locator precision"):
        validate_narrow_decisions(json.loads(DATASET.read_text())["cases"][2]["query"], non_navigation)
