"""TDD tests for the one-attempt Ordered Frame v3 model adapter."""

from __future__ import annotations

import json

import pytest

from rag.ordered_frame_client_v3 import (
    OrderedFrameClientV3,
    OrderedFrameExtractionError,
    SYSTEM_PROMPT,
    build_strict_tool_v3,
    understand_ordered_query_v3,
)


def _frame() -> dict:
    return {
        "schema_version": "atr.ordered-semantic-frame/3.0",
        "deliveries": [
            {
                "task_family": "trend_discovery",
                "evidence_spans": ["最近有哪些重要动态"],
                "requested_output_form": "important_news",
                "locator_kind": "none",
            }
        ],
        "protected_spans": ["OpenAI", "最近"],
        "claim_spans": [],
        "subject_spans": [],
        "source_spans": [],
        "web_permission": "on_demand",
        "web_evidence_spans": [],
        "unresolved_reference_spans": [],
    }


class ScriptedModel:
    model = "scripted"

    def __init__(self, value: dict):
        self.value = value
        self.calls = 0

    def complete(self, query: str, conversation_context: str | None):
        self.calls += 1
        return self.value, {"total_tokens": 10}


def test_adapter_makes_exactly_one_call_and_projects_the_route_contract() -> None:
    model = ScriptedModel(_frame())
    client = OrderedFrameClientV3(model)

    envelope, metadata = understand_ordered_query_v3(
        "OpenAI 最近有哪些重要动态？", client
    )

    assert model.calls == 1
    assert metadata["attempts"] == 1
    assert envelope["contract"]["primary_task_family"] == "trend_discovery"
    assert envelope["contract"]["web_permission"] == "on_demand"


def test_invalid_frame_fails_after_one_call_without_correction_retry() -> None:
    value = _frame()
    value["deliveries"][0]["evidence_spans"] = ["伪造片段"]
    model = ScriptedModel(value)

    with pytest.raises(OrderedFrameExtractionError, match="single attempt"):
        OrderedFrameClientV3(model).extract("OpenAI 最近有哪些重要动态？")

    assert model.calls == 1


def test_non_query_protected_span_is_dropped_and_audited_without_retry() -> None:
    value = _frame()
    value["protected_spans"].append("左边列表中昨天新增的那条")
    model = ScriptedModel(value)

    frame, metadata = OrderedFrameClientV3(model).extract(
        "OpenAI 最近有哪些重要动态？",
        "用户上一条消息：左边列表中昨天新增的那条不是目标。",
    )

    assert model.calls == 1
    assert frame["protected_spans"] == ["OpenAI", "最近"]
    assert metadata["dropped_non_query_protected_spans"] == [
        "左边列表中昨天新增的那条"
    ]


def test_retrieval_hints_are_bounded_and_reject_invented_record_ids() -> None:
    value = _frame()
    value["retrieval_hints"] = [
        "persistent context across sessions",
        "ATR-20260821-F3CB2B",
        "persistent context across sessions",
        "x" * 161,
    ]

    frame, metadata = OrderedFrameClientV3(ScriptedModel(value)).extract(
        "OpenAI 最近有哪些重要动态？"
    )

    assert frame["retrieval_hints"] == ["persistent context across sessions"]
    assert metadata["retrieval_hint_count"] == 1


@pytest.mark.parametrize(
    ("query", "expected_locator"),
    [
        ("定位《苍穹编排器发布说明》。", "full_title"),
        ("打开 ATR-20260818-Q7M2K9。", "atr_id"),
    ],
)
def test_observable_exact_locator_normalizes_navigation_without_retry(
    query: str, expected_locator: str
) -> None:
    value = {
        **_frame(),
        "deliveries": [{
            "task_family": "item_navigation",
            "evidence_spans": [query.rstrip("。")],
            "requested_output_form": "item_disambiguation",
            "locator_kind": "title_fragment",
        }],
        "protected_spans": [],
    }
    model = ScriptedModel(value)

    frame, metadata = OrderedFrameClientV3(model).extract(query)

    assert model.calls == 1
    assert frame["deliveries"][0]["locator_kind"] == expected_locator
    assert frame["deliveries"][0]["requested_output_form"] == "exact_item"
    assert metadata["normalized_observable_locators"] == [expected_locator]


def test_explicit_web_denial_overrides_model_permission_without_retry() -> None:
    value = _frame()
    value["web_permission"] = "on_demand"
    model = ScriptedModel(value)

    frame, metadata = OrderedFrameClientV3(model).extract(
        "OpenAI 最近有哪些重要动态？不要联网"
    )

    assert frame["web_permission"] == "forbidden"
    assert frame["web_evidence_spans"] == ["不要联网"]
    assert metadata["normalized_web_permission"] == "forbidden"


def test_strict_tool_contains_only_frame_fields_and_no_rewrite_output() -> None:
    function = build_strict_tool_v3()["function"]
    properties = function["parameters"]["properties"]

    assert function["strict"] is True
    assert set(properties) == {
        "schema_version",
        "deliveries",
        "protected_spans",
        "claim_spans",
        "subject_spans",
        "retrieval_hints",
        "source_spans",
        "web_permission",
        "web_evidence_spans",
        "unresolved_reference_spans",
    }
    assert "retrieval_hints" in function["parameters"]["required"]
    assert "persistent context across sessions" in SYSTEM_PROMPT
    assert "codebase knowledge graph" in SYSTEM_PROMPT
    assert "standalone_query" not in str(function)


def test_provider_tool_uses_flat_anyof_instead_of_unsupported_conditionals() -> None:
    parameters = build_strict_tool_v3()["function"]["parameters"]
    encoded = json.dumps(parameters)

    assert "anyOf" in parameters["properties"]["deliveries"]["items"]
    assert '"allOf"' not in encoded
    assert '"if"' not in encoded
    assert '"then"' not in encoded
    assert parameters["properties"]["schema_version"]["type"] == "string"
    assert parameters["properties"]["web_permission"]["type"] == "string"


def test_v3_2_prompt_contract_contains_the_revised_decision_boundaries() -> None:
    assert "Do not auto-upgrade important_news to trend_clusters" in SYSTEM_PROMPT
    assert "Every explicitly requested distinct task family remains a delivery" in SYSTEM_PROMPT
    assert "Comparing the same entity across time" in SYSTEM_PROMPT
    assert "Use timeline only when" in SYSTEM_PROMPT
    assert "use longitudinal_trend for continuous change" in SYSTEM_PROMPT
    assert "use cross_sectional_trend when" in SYSTEM_PROMPT
    assert "Use relation for non-temporal relationships" in SYSTEM_PROMPT
    assert "relationships among named entities" in SYSTEM_PROMPT
    assert "cooperation from co-occurrence" in SYSTEM_PROMPT
    assert "Use deep_research only when" in SYSTEM_PROMPT
    assert "ordinary impact analysis remains explanation" in SYSTEM_PROMPT
    assert "Unresolved references do not erase an otherwise explicit delivery" in SYSTEM_PROMPT
    assert "Do not duplicate web-permission phrases" in SYSTEM_PROMPT
    assert "trend_clusters subsumes important_news" not in SYSTEM_PROMPT
    assert "choose the richest output form" not in SYSTEM_PROMPT
