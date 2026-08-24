"""Slice-1 contract tests for Ordered Semantic Frame v3.

These scripted frames test only validation and deterministic projection. They do
not measure model understanding.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from rag.ordered_semantic_frame_v3 import build_ordered_route_envelope_v3
from rag.route_contract_validation import validate_route_contract_semantics


ROOT = Path(__file__).resolve().parents[2]
ROUTE_SCHEMA = json.loads(
    (ROOT / "docs/rag-transformation/specs/route-contract-v2.schema.json").read_text()
)


def _delivery(
    task_family: str,
    evidence: str,
    output: str,
    locator: str = "none",
) -> dict:
    return {
        "task_family": task_family,
        "evidence_spans": [evidence],
        "requested_output_form": output,
        "locator_kind": locator,
    }


def _frame(
    *deliveries: dict,
    protected: list[str] | None = None,
    web: str = "on_demand",
    web_evidence: list[str] | None = None,
    unresolved: list[str] | None = None,
) -> dict:
    return {
        "schema_version": "atr.ordered-semantic-frame/3.0",
        "deliveries": list(deliveries),
        "protected_spans": protected or [],
        "web_permission": web,
        "web_evidence_spans": web_evidence or [],
        "unresolved_reference_spans": unresolved or [],
    }


@pytest.mark.parametrize(
    ("query", "protected"),
    [
        ("帮我看看。", []),
        ("打开或解释 Nova，哪一种都可以。", ["Nova"]),
    ],
)
def test_missing_or_ambiguous_delivery_fails_closed(
    query: str, protected: list[str]
) -> None:
    envelope = build_ordered_route_envelope_v3(
        query,
        _frame(protected=protected),
    )

    assert envelope["status"] == "clarification_required"
    assert envelope["contract"] is None
    assert envelope["reasons"]


def _resolved_contract(query: str, frame: dict, context: str | None = None) -> dict:
    envelope = build_ordered_route_envelope_v3(query, frame, context)
    assert envelope["status"] == "resolved", envelope
    contract = envelope["contract"]
    Draft202012Validator(ROUTE_SCHEMA).validate(contract)
    validate_route_contract_semantics(contract)
    return contract


@pytest.mark.parametrize(
    ("query", "deliveries", "expected_primary", "expected_supporting"),
    [
        (
            "解释量子安全路线，并找到标题里包含 Nova 的那条记录。",
            [
                _delivery("evidence_research", "解释量子安全路线", "explanation"),
                _delivery(
                    "item_navigation",
                    "找到标题里包含 Nova 的那条记录",
                    "item_disambiguation",
                    "title_fragment",
                ),
            ],
            "evidence_research",
            ["item_navigation"],
        ),
        (
            "找到《Nova 安全路线》这条记录，并解释它为什么重要。",
            [
                _delivery(
                    "item_navigation",
                    "找到《Nova 安全路线》这条记录",
                    "exact_item",
                    "full_title",
                ),
                _delivery("evidence_research", "解释它为什么重要", "explanation"),
            ],
            "item_navigation",
            ["evidence_research"],
        ),
    ],
)
def test_supporting_item_navigation_is_a_schema_valid_contract(
    query: str,
    deliveries: list[dict],
    expected_primary: str,
    expected_supporting: list[str],
) -> None:
    contract = _resolved_contract(query, _frame(*deliveries, protected=["Nova"]))

    assert contract["primary_task_family"] == expected_primary
    assert contract["supporting_task_families"] == expected_supporting
    assert [
        [item["task_family"], item["requested_output_form"], item["locator_kind"]]
        for item in contract["delivery_contracts"]
    ] == [
        [item["task_family"], item["requested_output_form"], item["locator_kind"]]
        for item in deliveries
    ]
    assert [item["task_family"] for item in contract["supporting_contracts"]] == expected_supporting
    if expected_supporting == ["item_navigation"]:
        supporting = contract["supporting_contracts"][0]
        assert supporting["requested_output_form"] == "item_disambiguation"
        assert supporting["locator_kind"] == "title_fragment"
        assert supporting["route_confidence"] < 1
        assert supporting["ambiguities"]


@pytest.mark.parametrize(
    ("query", "locator", "output", "expected_mode"),
    [
        ("打开 ATR-20260821-A1B2C3。", "atr_id", "exact_item", "exact_item"),
        ("找到《Nova 安全路线》这条记录。", "full_title", "exact_item", "exact_item"),
        (
            "找到标题里包含 Nova 的那条记录。",
            "title_fragment",
            "item_disambiguation",
            "item_disambiguation",
        ),
        (
            "找到昨天讨论的那个数据库条目。",
            "descriptive",
            "item_disambiguation",
            "item_disambiguation",
        ),
    ],
)
def test_locator_kind_maps_observable_form_to_navigation_mode(
    query: str, locator: str, output: str, expected_mode: str
) -> None:
    evidence = query.rstrip("。")
    contract = _resolved_contract(
        query,
        _frame(
            _delivery("item_navigation", evidence, output, locator),
            protected=[],
        ),
    )

    assert contract["answer_mode"] == expected_mode
    assert contract["delivery_contracts"][0]["locator_kind"] == locator
    assert (contract["route_confidence"] < 1) is (
        locator in {"title_fragment", "descriptive"}
    )


def test_temporal_and_source_literals_enter_dedicated_contract_fields() -> None:
    query = "不要联网，只看 OpenAI 官方在 2026 年 3 月和 2026 年 7 月发布的更新。"
    contract = _resolved_contract(
        query,
        _frame(
            _delivery(
                "temporal_relation_exploration",
                "2026 年 3 月和 2026 年 7 月发布的更新",
                "cross_sectional_trend",
            ),
            protected=["OpenAI", "2026 年 3 月", "2026 年 7 月"],
            web="forbidden",
            web_evidence=["不要联网"],
        ),
    )

    assert contract["temporal_constraint"] == {
        "mode": "absolute_range",
        "value": "2026 年 3 月 | 2026 年 7 月",
        "surface": "2026 年 3 月和 2026 年 7 月",
        "start": "2026-03-01",
        "end": "2026-07-31",
    }
    assert contract["source_constraint"] == {
        "requested_sources": ["OpenAI"],
        "official_first": True,
    }


def test_multiple_complete_dates_are_preserved_in_query_order() -> None:
    query = "对比 2026 年 3 月 1 日和 2026 年 7 月 2 日的部署状态。"
    contract = _resolved_contract(
        query,
        _frame(
            _delivery(
                "temporal_relation_exploration",
                query.rstrip("。"),
                "cross_sectional_trend",
            ),
        ),
    )

    assert contract["temporal_constraint"] == {
        "mode": "absolute_range",
        "value": "2026 年 3 月 1 日 | 2026 年 7 月 2 日",
        "surface": "2026 年 3 月 1 日和 2026 年 7 月 2 日",
        "start": "2026-03-01",
        "end": "2026-07-02",
    }


def test_delivery_contract_sequence_drift_is_rejected() -> None:
    query = "解释 Nova，并定位《Nova 安全路线》。"
    contract = _resolved_contract(
        query,
        _frame(
            _delivery("evidence_research", "解释 Nova", "explanation"),
            _delivery(
                "item_navigation",
                "定位《Nova 安全路线》",
                "exact_item",
                "full_title",
            ),
            protected=["Nova", "《Nova 安全路线》"],
        ),
    )
    contract["delivery_contracts"].reverse()

    with pytest.raises(Exception, match="delivery contracts"):
        validate_route_contract_semantics(contract)


@pytest.mark.parametrize(
    "delivery",
    [
        _delivery("temporal_relation_exploration", "解释", "explanation"),
        _delivery("evidence_research", "解释", "explanation", "descriptive"),
    ],
)
def test_semantically_illegal_delivery_combinations_are_rejected_by_schema(
    delivery: dict,
) -> None:
    with pytest.raises(Exception, match="schema violation"):
        build_ordered_route_envelope_v3(
            "请解释这个问题。",
            _frame(delivery, protected=["这个问题"]),
        )


@pytest.mark.parametrize(
    "deliveries",
    [
        [
            _delivery(
                "item_navigation",
                "找到标题里包含 Nova 的记录",
                "exact_item",
                "title_fragment",
            )
        ],
        [
            _delivery("evidence_research", "解释 Nova", "explanation"),
            _delivery(
                "item_navigation",
                "再找到标题里包含 Nova 的记录",
                "exact_item",
                "title_fragment",
            ),
        ],
    ],
)
def test_primary_and_supporting_navigation_reject_locator_output_conflicts(
    deliveries: list[dict],
) -> None:
    query = "解释 Nova，并再找到标题里包含 Nova 的记录。" if len(deliveries) == 2 else "找到标题里包含 Nova 的记录。"

    with pytest.raises(Exception, match="schema violation"):
        build_ordered_route_envelope_v3(
            query,
            _frame(*deliveries, protected=["Nova"]),
        )


@pytest.mark.parametrize(
    ("query", "family", "evidence", "output"),
    [
        (
            "梳理 Nimbus 过去三个月有哪些重要动态。",
            "trend_discovery",
            "有哪些重要动态",
            "important_news",
        ),
        (
            "梳理 Nimbus 过去三个月如何演变。",
            "temporal_relation_exploration",
            "如何演变",
            "timeline",
        ),
    ],
)
def test_same_entity_and_time_do_not_create_an_extra_route(
    query: str, family: str, evidence: str, output: str
) -> None:
    contract = _resolved_contract(
        query,
        _frame(_delivery(family, evidence, output), protected=["Nimbus", "过去三个月"]),
    )

    assert contract["primary_task_family"] == family
    assert contract["supporting_task_families"] == []


@pytest.mark.parametrize(
    ("suffix", "permission"),
    [
        ("不要联网。", "forbidden"),
        ("必要时可联网。", "on_demand"),
        ("请联网查。", "explicit"),
    ],
)
def test_web_permission_keeps_denial_permission_and_request_distinct(
    suffix: str, permission: str
) -> None:
    query = "解释 OpenAI 最近的产品调整，" + suffix
    contract = _resolved_contract(
        query,
        _frame(
            _delivery("evidence_research", "解释 OpenAI 最近的产品调整", "explanation"),
            protected=["OpenAI"],
            web=permission,
            web_evidence=[suffix.rstrip("。")],
        ),
    )

    assert contract["web_permission"] == permission
    assert suffix.rstrip("。") not in contract["protected_terms"]


def test_reference_contrasts_fail_closed_resolve_postposed_claim_and_public_map() -> None:
    vague_query = "解释这个为什么重要。"
    vague = build_ordered_route_envelope_v3(
        vague_query,
        _frame(
            _delivery("evidence_research", "解释这个为什么重要", "explanation"),
            unresolved=["这个"],
        ),
    )
    assert vague["status"] == "clarification_required"

    claim_query = "截至 2026 年 8 月 1 日，这个说法有证据支持吗：‘Nova R2 已经开源且允许商用’？禁止联网"
    claim = _resolved_contract(
        claim_query,
        _frame(
            _delivery("claim_verification", "这个说法有证据支持吗", "verification_verdict"),
            protected=["Nova R2 已经开源且允许商用"],
            web="forbidden",
            web_evidence=["禁止联网"],
        ),
    )
    assert "Nova R2 已经开源且允许商用" in claim["protected_terms"]
    assert "2026 年 8 月 1 日" in claim["protected_terms"]
    assert claim["web_permission"] == "forbidden"

    context_query = "解释左边那条为什么重要。"
    context = "左侧记录是 ATR-20260805-99E550《Nova 安全路线》。"
    context_contract = _resolved_contract(
        context_query,
        _frame(
            _delivery("evidence_research", "解释左边那条为什么重要", "explanation"),
            protected=["左边那条"],
        ),
        context,
    )
    assert context_contract["resolved_references"] == [
        {
            "reference_type": "item_id",
            "value": "ATR-20260805-99E550",
            "origin": "conversation_context",
        }
    ]


def test_contextual_claim_is_preserved_for_downstream_verification() -> None:
    query = "这个说法是否成立？同时解释支持或反对它的关键证据。"
    context = "上一轮用户提出的说法是：北辰 API 已把推理成本降低 40%。"

    contract = _resolved_contract(
        query,
        _frame(
            _delivery(
                "claim_verification",
                "这个说法是否成立",
                "verification_verdict",
            ),
            _delivery(
                "evidence_research",
                "解释支持或反对它的关键证据",
                "explanation",
            ),
            unresolved=["这个说法"],
        ),
        context,
    )

    assert contract["claims"] == ["北辰 API 已把推理成本降低 40%"]

    without_context = build_ordered_route_envelope_v3(
        "这个说法是否成立？",
        _frame(
            _delivery(
                "claim_verification",
                "这个说法是否成立",
                "verification_verdict",
            ),
            unresolved=["这个说法"],
        ),
    )
    assert without_context["status"] == "clarification_required"
    assert without_context["contract"] is None

    missing_model_signal = build_ordered_route_envelope_v3(
        "这个说法是否成立？",
        _frame(
            _delivery(
                "claim_verification",
                "这个说法是否成立",
                "verification_verdict",
            ),
            unresolved=[],
        ),
    )
    assert missing_model_signal["status"] == "clarification_required"
    assert missing_model_signal["contract"] is None


@pytest.mark.parametrize(
    "query",
    [
        "请帮我比较 OpenAI 和 Anthropic 的安全路线。",
        "麻烦比较一下 OpenAI 和 Anthropic 在安全路线上的差异。",
    ],
)
def test_politeness_changes_do_not_change_content_constraints(query: str) -> None:
    contract = _resolved_contract(
        query,
        _frame(
            _delivery("evidence_research", "比较", "comparison"),
            protected=["OpenAI", "Anthropic", "安全路线"],
        ),
    )

    assert contract["protected_terms"] == ["OpenAI", "Anthropic", "安全路线"]
