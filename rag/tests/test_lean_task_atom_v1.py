"""Contract tests for the route-neutral Lean Task Atom fallback."""

from __future__ import annotations

import pytest

from rag.lean_task_atom_client import (
    LeanTaskAtomCallError,
    build_strict_tool,
    strict_beta_url,
    validate_reference_statuses,
)
from rag.lean_task_atom_v1 import LeanTaskAtomViolation, project_lean_task_atoms


def _payload(main_action: str, main_target: str, supporting: list[dict] | None = None) -> dict:
    return {
        "main": {
            "action": main_action,
            "target_span": main_target,
            "success_criterion": "完成用户明确要求的主要交付",
        },
        "supporting": supporting or [],
        "references": [],
        "confidence": 0.95,
        "ambiguities": [],
    }


def test_lean_output_cannot_emit_route_or_policy() -> None:
    value = _payload("discover", "模型水印")
    value["primary_task_family"] = "trend_discovery"
    with pytest.raises(LeanTaskAtomViolation, match="schema"):
        project_lean_task_atoms("汇总近 30 天模型水印的重要动态。", None, value)


def test_discovery_with_verification_support_projects_to_b_plus_d() -> None:
    query = "汇总近 30 天模型水印的重要动态，并核验其中“所有主流厂商都已默认开启水印”这句话。"
    value = _payload("discover", "模型水印", [{
        "action": "verify",
        "target_span": "所有主流厂商都已默认开启水印",
        "success_criterion": "给出独立核验结论",
    }])
    contract = project_lean_task_atoms(query, None, value).to_dict()
    assert contract["primary_task_family"] == "trend_discovery"
    assert contract["supporting_task_families"] == ["claim_verification"]
    assert contract["answer_mode"] == "important_news"
    assert contract["protected_terms"] == [
        "近 30 天", "模型水印", "所有主流厂商都已默认开启水印"
    ]


def test_verification_can_use_relation_as_evidence_without_support_route() -> None:
    query = "核验左边那条所说的“延迟下降 40%”，并判断右边那条是否否定了它。"
    context = "左侧是 ATR-20260702-D6M1QH，右侧是 ATR-20260708-W3P9ZA。"
    value = _payload("verify", "延迟下降 40%")
    value["references"] = [
        {"literal_span": "左边那条", "status": "resolved_from_context", "resolved_value": "ATR-20260702-D6M1QH"},
        {"literal_span": "右边那条", "status": "resolved_from_context", "resolved_value": "ATR-20260708-W3P9ZA"},
    ]
    contract = project_lean_task_atoms(query, context, value).to_dict()
    assert contract["primary_task_family"] == "claim_verification"
    assert contract["supporting_task_families"] == []
    assert contract["intent_signals"] == ["verification", "relation"]
    assert contract["protected_terms"] == [
        "左边那条", "延迟下降 40%", "右边那条", "是否否定"
    ]
    assert [item["value"] for item in contract["resolved_references"]] == [
        "ATR-20260702-D6M1QH", "ATR-20260708-W3P9ZA"
    ]


def test_target_span_must_be_literal_query_text() -> None:
    with pytest.raises(LeanTaskAtomViolation, match="target span"):
        project_lean_task_atoms(
            "汇总近 30 天模型水印的重要动态。",
            None,
            _payload("discover", "模型水印生态"),
        )


def test_strict_tool_schema_matches_deepseek_beta_requirements() -> None:
    function = build_strict_tool()["function"]

    assert function["strict"] is True
    assert function["name"] == "submit_lean_task_atoms"

    def assert_object_contract(schema: dict) -> None:
        if schema.get("type") == "object":
            assert schema.get("additionalProperties") is False
            assert set(schema.get("required", [])) == set(schema.get("properties", {}))
            for child in schema["properties"].values():
                assert_object_contract(child)
        if schema.get("type") == "array":
            assert "maxItems" not in schema
            assert_object_contract(schema["items"])
        assert "minLength" not in schema
        assert not isinstance(schema.get("type"), list)

    assert_object_contract(function["parameters"])


def test_beta_url_is_derived_without_duplicating_suffix() -> None:
    assert strict_beta_url("https://api.deepseek.com") == "https://api.deepseek.com/beta"
    assert strict_beta_url("https://api.deepseek.com/") == "https://api.deepseek.com/beta"
    assert strict_beta_url("https://api.deepseek.com/beta") == "https://api.deepseek.com/beta"


def test_reference_status_contract_uses_empty_string_only_for_unresolved() -> None:
    validate_reference_statuses([{
        "literal_span": "它", "status": "unresolved", "resolved_value": "",
    }])
    validate_reference_statuses([{
        "literal_span": "右边那条", "status": "resolved_from_context",
        "resolved_value": "ATR-20260421-Y7K3DG",
    }])

    with pytest.raises(LeanTaskAtomCallError, match="unresolved"):
        validate_reference_statuses([{
            "literal_span": "它", "status": "unresolved",
            "resolved_value": "ATR-20260421-Y7K3DG",
        }])
    with pytest.raises(LeanTaskAtomCallError, match="must be non-empty"):
        validate_reference_statuses([{
            "literal_span": "右边那条", "status": "resolved_from_context",
            "resolved_value": "",
        }])
