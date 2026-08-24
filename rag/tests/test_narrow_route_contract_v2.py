"""Shadow end-to-end projection from L0 Query and L1 fixtures to Route v2."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from rag.narrow_route_contract_v2 import build_narrow_route_envelope
from rag.route_contract_validation import validate_route_contract_semantics
from rag.tests.test_narrow_semantic_decisions_v1 import _payload


ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "docs/rag-transformation/evals/narrow-semantic-decisions-v1-calibration-2026-08-13.json").read_text())["cases"]
ROUTE_SCHEMA = json.loads((ROOT / "docs/rag-transformation/specs/route-contract-v2.schema.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["case_id"])
def test_twelve_fixtures_reach_contract_or_explicit_clarification(case: dict) -> None:
    envelope = build_narrow_route_envelope(
        case["query"], _payload(case), case.get("conversation_context")
    )
    assert envelope["status"] == case["expected_status"]
    if envelope["status"] == "clarification_required":
        assert envelope["contract"] is None
        assert envelope["reasons"]
        return

    contract = envelope["contract"]
    Draft202012Validator(ROUTE_SCHEMA).validate(contract)
    validate_route_contract_semantics(contract)
    assert contract["original_query"] == case["query"]
    assert contract["primary_task_family"] == case["expected_primary"]
    assert contract["supporting_task_families"] == case["expected_supporting"]
    assert [item["task_family"] for item in contract["supporting_contracts"]] == case["expected_supporting"]


def test_public_context_references_survive_as_bare_atr_ids() -> None:
    case = CASES[6]
    contract = build_narrow_route_envelope(
        case["query"], _payload(case), case["conversation_context"]
    )["contract"]
    assert [item["value"] for item in contract["resolved_references"]] == [
        "ATR-20260702-D6M1QH", "ATR-20260708-W3P9ZA"
    ]


def test_web_permission_is_derived_from_real_query_not_l1_fixture() -> None:
    case = deepcopy(CASES[2])
    query = case["query"] + " 不要联网。"
    value = _payload(case)
    contract = build_narrow_route_envelope(query, value)["contract"]
    assert contract["web_permission"] == "forbidden"
    assert "web_requested" not in contract["intent_signals"]
    assert "不要联网" in contract["protected_terms"]


@pytest.mark.parametrize("phrase", ["不要联网", "禁止联网", "别联网", "无需联网"])
def test_all_web_denials_are_forbidden_protected_and_not_web_requested(phrase: str) -> None:
    case = CASES[2]
    query = case["query"] + f" {phrase}。"
    contract = build_narrow_route_envelope(query, _payload(case))["contract"]
    assert contract["web_permission"] == "forbidden"
    assert phrase in contract["protected_terms"]
    assert "web_requested" not in contract["intent_signals"]


def test_title_topic_time_and_claim_survive_as_protected_terms() -> None:
    navigation = build_narrow_route_envelope(CASES[1]["query"], _payload(CASES[1]))["contract"]
    discovery = build_narrow_route_envelope(CASES[2]["query"], _payload(CASES[2]))["contract"]
    assert "Apple Is Getting This Wrong" in navigation["protected_terms"]
    assert {"近 30 天", "模型水印", "所有主流厂商都已默认开启水印"}.issubset(
        discovery["protected_terms"]
    )


def test_wrapped_title_protected_span_is_normalized_to_its_searchable_value() -> None:
    value = _payload(CASES[1])
    value["protected_spans"] = ["《Apple Is Getting This Wrong》"]

    contract = build_narrow_route_envelope(CASES[1]["query"], value)["contract"]

    assert "Apple Is Getting This Wrong" in contract["protected_terms"]
    assert "《Apple Is Getting This Wrong》" not in contract["protected_terms"]


def test_protected_terms_keep_structural_target_but_drop_generic_task_label() -> None:
    temporal_query = "梳理 Nimbus 过去两年安全路线如何演变。"
    temporal_value = _payload({
        "query": temporal_query,
        "present": {
            "cross_time_or_entity_structure": ["过去两年安全路线如何演变"],
            "explanation_or_comparison": ["梳理"],
        },
        "uncertain": {}, "unresolved_reference_spans": [],
        "protected_spans": ["Nimbus", "过去两年", "安全"],
    })
    discovery_query = "最近有什么热门趋势？"
    discovery_value = _payload({
        "query": discovery_query,
        "present": {"recent_update_set": ["最近有什么热门趋势"]},
        "uncertain": {}, "unresolved_reference_spans": [],
        "protected_spans": ["最近", "热门趋势"],
    })

    temporal = build_narrow_route_envelope(temporal_query, temporal_value)["contract"]
    discovery = build_narrow_route_envelope(discovery_query, discovery_value)["contract"]

    assert temporal["protected_terms"] == ["Nimbus", "过去两年", "安全路线"]
    assert discovery["protected_terms"] == ["最近"]


def test_partial_item_locator_requires_disambiguation() -> None:
    query = "找到标题包含 Nova 的记录。"
    fixture = _payload({
        "query": query,
        "present": {"item_lookup": ["找到标题包含 Nova 的记录"]},
        "uncertain": {}, "unresolved_reference_spans": [],
        "protected_spans": ["Nova"], "item_locator_precision": "partial",
    })
    contract = build_narrow_route_envelope(query, fixture)["contract"]
    assert contract["answer_mode"] == "item_disambiguation"
    assert contract["route_confidence"] < 1
    assert contract["ambiguities"]


def test_faults_fail_closed_before_a_route_contract_is_emitted() -> None:
    case = CASES[2]
    value = _payload(case)
    value["dimensions"]["recent_update_set"]["state"] = "uncertain"
    envelope = build_narrow_route_envelope(case["query"], value)
    assert envelope["status"] == "clarification_required"
    assert envelope["contract"] is None


def test_tampered_reference_and_missing_support_contract_cannot_pass() -> None:
    case = CASES[6]
    value = _payload(case)
    value["resolved_references"][0]["item_id"] = "ATR-20260101-AAAAAA"
    with pytest.raises(ValueError, match="public context"):
        build_narrow_route_envelope(case["query"], value, case["conversation_context"])

    contract = build_narrow_route_envelope(CASES[2]["query"], _payload(CASES[2]))["contract"]
    contract["supporting_contracts"] = []
    with pytest.raises(ValueError, match="supporting contracts"):
        validate_route_contract_semantics(contract)
