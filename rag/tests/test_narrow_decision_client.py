"""Contract tests for the narrow L1 external-model adapter."""

from __future__ import annotations

import json

import pytest

from rag.narrow_decision_client import (
    NarrowDecisionClient,
    NarrowDecisionExtractionError,
    build_strict_tool,
)


QUERY = "汇总近 30 天模型水印的重要动态。"


def _valid_dimensions() -> dict:
    return {
        "schema_version": "atr.semantic-dimensions/2.0",
        "dimensions": {
            "item_lookup": {"state": "absent", "evidence_spans": []},
            "recent_update_set": {
                "state": "present",
                "evidence_spans": ["汇总近 30 天模型水印的重要动态"],
            },
            "cross_time_or_entity_structure": {"state": "absent", "evidence_spans": []},
            "truth_assessable_claim": {"state": "absent", "evidence_spans": []},
            "explanation_or_comparison": {"state": "absent", "evidence_spans": []},
        },
    }


class ScriptedModel:
    model = "scripted"

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    def complete(self, query: str, conversation_context: str | None, correction: str | None):
        self.calls.append((query, conversation_context, correction))
        output = self.outputs[len(self.calls) - 1]
        if isinstance(output, Exception):
            raise output
        return output, {"model": self.model, "total_tokens": 10}


def test_invalid_first_output_is_corrected_once_then_validated() -> None:
    invalid = _valid_dimensions()
    invalid["dimensions"]["recent_update_set"]["evidence_spans"] = ["伪造片段"]
    model = ScriptedModel(invalid, _valid_dimensions())

    value, diagnostics = NarrowDecisionClient(model).extract(QUERY)

    assert value["schema_version"] == "atr.semantic-decisions/1.0"
    assert value["dimensions"] == _valid_dimensions()["dimensions"]
    assert value["protected_spans"] == ["近 30 天", "模型水印"]
    assert diagnostics["attempts"] == 2
    assert model.calls[0][2] is None
    assert "literal" in model.calls[1][2]


def test_two_invalid_outputs_raise_a_bounded_error() -> None:
    invalid = _valid_dimensions()
    invalid["dimensions"]["recent_update_set"]["evidence_spans"] = ["伪造片段"]
    model = ScriptedModel(invalid, invalid)

    with pytest.raises(NarrowDecisionExtractionError, match="two attempts"):
        NarrowDecisionClient(model).extract(QUERY)

    assert len(model.calls) == 2


def test_model_transport_failure_is_not_retried_as_a_semantic_correction() -> None:
    model = ScriptedModel(TimeoutError("provider unavailable"))

    with pytest.raises(TimeoutError):
        NarrowDecisionClient(model).extract(QUERY)

    assert len(model.calls) == 1


def test_strict_tool_exposes_only_route_neutral_l1_fields() -> None:
    tool = build_strict_tool()
    encoded = json.dumps(tool, ensure_ascii=False)

    assert tool["function"]["strict"] is True
    assert "primary_task_family" not in encoded
    assert "answer_mode" not in encoded
    assert "prompt_contract" not in encoded
    assert "retrieval_policy" not in encoded
    assert set(tool["function"]["parameters"]["properties"]) == {
        "schema_version", "dimensions"
    }


def test_public_left_and_right_context_are_resolved_deterministically() -> None:
    query = "核验左边那条所说的“吞吐提升 25%”，并判断右边那条是否反驳它。"
    context = (
        "左侧 ATR-20260801-AA11BB《Nimbus 基准》，"
        "右侧 ATR-20260802-CC22DD《独立复测》。"
    )
    value = _valid_dimensions()
    value["dimensions"]["recent_update_set"] = {"state": "absent", "evidence_spans": []}
    value["dimensions"]["truth_assessable_claim"] = {
        "state": "present",
        "evidence_spans": ["核验左边那条所说的“吞吐提升 25%”，并判断右边那条是否反驳它"],
    }
    model = ScriptedModel(value)

    decisions, _ = NarrowDecisionClient(model).extract(query, context)

    assert decisions["unresolved_reference_spans"] == []
    assert decisions["resolved_references"] == [
        {"literal_span": "左边那条", "item_id": "ATR-20260801-AA11BB"},
        {"literal_span": "右边那条", "item_id": "ATR-20260802-CC22DD"},
    ]


def test_vague_reference_without_an_in_query_antecedent_stays_unresolved() -> None:
    query = "解释这个为什么重要。"
    value = _valid_dimensions()
    value["dimensions"]["recent_update_set"] = {"state": "absent", "evidence_spans": []}
    value["dimensions"]["explanation_or_comparison"] = {
        "state": "present", "evidence_spans": ["解释这个为什么重要"]
    }

    decisions, _ = NarrowDecisionClient(ScriptedModel(value)).extract(query)

    assert decisions["unresolved_reference_spans"] == ["这个"]
    assert decisions["resolved_references"] == []
