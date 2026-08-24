"""Safety and routing tests for the SemanticParseV1 shadow boundary."""

from __future__ import annotations

import pytest

from rag.semantic_parse_v1 import (
    SemanticParseViolation,
    build_route_contract_from_semantic_parse,
    validate_semantic_parse,
)


def _parse(**overrides) -> dict:
    value = {
        "subjects": ["模型水印"],
        "claims": ["所有主流厂商都已默认开启水印"],
        "locators": [],
        "constraints": [
            {"kind": "time", "value": "30 days", "literal_span": "近 30 天"},
            {"kind": "importance", "value": "important", "literal_span": "重要动态"},
        ],
        "references": [],
        "task_atoms": [
            {"action": "discover", "target": "模型水印", "success_criterion": "汇总重要动态", "delivery_role": "main"},
            {"action": "verify", "target": "所有主流厂商都已默认开启水印", "success_criterion": "给出核验结论", "delivery_role": "supporting"},
        ],
        "literal_spans": ["近 30 天", "模型水印", "所有主流厂商都已默认开启水印"],
        "confidence": 0.95,
        "ambiguities": [],
    }
    value.update(overrides)
    return value


def test_semantic_parse_cannot_choose_a_route() -> None:
    parse = _parse(primary_task_family="trend_discovery")
    with pytest.raises(SemanticParseViolation, match="schema"):
        validate_semantic_parse("汇总近 30 天模型水印的重要动态", None, parse)


def test_semantic_parse_rejects_literal_spans_not_found_in_query() -> None:
    parse = _parse(literal_spans=["模型水印", "编造的限制"])
    with pytest.raises(SemanticParseViolation, match="literal span"):
        validate_semantic_parse("汇总近 30 天模型水印的重要动态", None, parse)


def test_compound_discovery_and_verification_builds_one_primary_and_support() -> None:
    query = "汇总近 30 天模型水印的重要动态，并核验其中“所有主流厂商都已默认开启水印”这句话。"
    contract = build_route_contract_from_semantic_parse(query, None, _parse()).to_dict()

    assert contract["primary_task_family"] == "trend_discovery"
    assert contract["supporting_task_families"] == ["claim_verification"]
    assert contract["answer_mode"] == "important_news"
    assert contract["route_confidence"] >= 0.8


def test_hard_web_denial_cannot_be_reversed_by_model_constraints() -> None:
    query = "不要联网，只用库内资料总结最近两周端侧语音模型的新动向。"
    parse = _parse(
        subjects=["端侧语音模型"],
        claims=[],
        constraints=[
            {"kind": "web_permission", "value": "explicit", "literal_span": "不要联网"},
            {"kind": "time", "value": "two weeks", "literal_span": "最近两周"},
            {"kind": "source", "value": "internal", "literal_span": "只用库内资料"},
        ],
        task_atoms=[
            {"action": "discover", "target": "端侧语音模型", "success_criterion": "按主题总结新动向", "delivery_role": "main"}
        ],
        literal_spans=["不要联网", "只用库内资料", "最近两周", "端侧语音模型"],
    )
    contract = build_route_contract_from_semantic_parse(query, None, parse).to_dict()
    assert contract["web_permission"] == "forbidden"
    assert "web_requested" not in contract["intent_signals"]


def test_context_references_are_resolved_without_model_inventing_ids() -> None:
    query = "先打开左边那条，再打开右边那条。"
    context = "当前结果从左到右依次为 ATR-20260214-H3J7KS 和 ATR-20260215-P6W2BX。"
    parse = _parse(
        subjects=[], claims=[], constraints=[],
        locators=[
            {"kind": "spatial_reference", "value": "左边那条", "exact": True},
            {"kind": "spatial_reference", "value": "右边那条", "exact": True},
        ],
        references=[
            {"literal_span": "左边那条", "status": "resolved_from_context", "resolved_value": "ATR-20260214-H3J7KS"},
            {"literal_span": "右边那条", "status": "resolved_from_context", "resolved_value": "ATR-20260215-P6W2BX"},
        ],
        task_atoms=[
            {"action": "navigate", "target": "左边那条", "success_criterion": "打开条目", "delivery_role": "main"},
            {"action": "navigate", "target": "右边那条", "success_criterion": "打开条目", "delivery_role": "evidence_step"},
        ],
        literal_spans=["左边那条", "右边那条"],
    )
    contract = build_route_contract_from_semantic_parse(query, context, parse).to_dict()
    assert contract["primary_task_family"] == "item_navigation"
    assert [item["value"] for item in contract["resolved_references"]] == [
        "ATR-20260214-H3J7KS", "ATR-20260215-P6W2BX"
    ]


def test_empty_task_atoms_fail_instead_of_falling_back_to_research() -> None:
    with pytest.raises(SemanticParseViolation, match="task atom"):
        build_route_contract_from_semantic_parse(
            "汇总近 30 天模型水印的重要动态，并核验所有主流厂商都已默认开启水印",
            None,
            _parse(task_atoms=[], confidence=0.2),
        )
