"""Generalization tests for Query Signals and task-route resolution."""

from __future__ import annotations

import pytest

from rag.query_signal_extraction import extract_query_signals
from rag.query_understanding_v2 import understand_query_v2
from rag.route_contract_scoring import score_protected_terms
from rag.task_route_resolution import resolve_task_route


@pytest.mark.parametrize(
    ("query", "expected_route"),
    [
        ("找到 OpenAI 最近的重要动态", "trend_discovery"),
        ("找到证据解释 GraphRAG 为什么有效", "evidence_research"),
        ("今天 OpenAI 有什么更新？", "trend_discovery"),
        ("过去一年 AI Agent 领域形成了哪些趋势？", "temporal_relation_exploration"),
        ("OpenAI 的 Agent 路线有什么变化？", "temporal_relation_exploration"),
        ("OpenAI 是否已经发布 GPT-6？", "claim_verification"),
        ("OpenAI 是否值得企业采用？", "evidence_research"),
    ],
)
def test_task_success_criteria_generalize_beyond_development_phrases(
    query: str,
    expected_route: str,
) -> None:
    decision = resolve_task_route(extract_query_signals(query))
    assert decision.primary_task_family == expected_route


def test_navigation_requires_a_locatable_object() -> None:
    exact = resolve_task_route(extract_query_signals("打开“Scaling Laws for Agentic Search”的原条目"))
    broad = resolve_task_route(extract_query_signals("找到 OpenAI 最近的重要动态"))

    assert exact.primary_task_family == "item_navigation"
    assert broad.primary_task_family != "item_navigation"


def test_protected_terms_are_independent_tokens_not_the_whole_query() -> None:
    query = "OpenAI 是否已经在 8 月 12 日正式发布 GPT-6？"
    signals = extract_query_signals(query)

    assert {"OpenAI", "8 月 12 日", "GPT-6"}.issubset(set(signals.protected_terms))
    assert query not in signals.protected_terms


def test_ambiguous_contextual_navigation_is_exposed() -> None:
    signals = extract_query_signals("我刚点开的这条新闻不要分析，直接带我回它的原条目")
    decision = resolve_task_route(signals)

    assert decision.primary_task_family == "item_navigation"
    assert decision.answer_mode == "item_disambiguation"
    assert decision.ambiguities


@pytest.mark.parametrize(
    ("query", "expected_route"),
    [
        ("最近 Moonshot 有啥大动静？", "trend_discovery"),
        ("半年内 Nova 的方向经历了哪几个阶段？", "temporal_relation_exploration"),
        ("OpenAI 没有发布新模型，对不对？", "claim_verification"),
        ("回到标题为《Nova Agents Need Guardrails》的那篇原文", "item_navigation"),
    ],
)
def test_unseen_entities_and_paraphrases_use_task_criteria(
    query: str,
    expected_route: str,
) -> None:
    contract = understand_query_v2(query).to_dict()
    assert contract["primary_task_family"] == expected_route


def test_negative_web_instruction_overrides_web_keyword() -> None:
    contract = understand_query_v2("不要联网，只用内部库解释 Nova 的路线").to_dict()
    assert contract["web_permission"] == "forbidden"
    assert "不要联网" in contract["protected_terms"]
    assert "web_requested" not in contract["intent_signals"]


def test_navigation_context_is_only_resolved_by_a_real_locator() -> None:
    unresolved = understand_query_v2("带我回这条新闻的原条目", "刚才聊过一些新闻").to_dict()
    resolved = understand_query_v2(
        "带我回这条新闻的原条目",
        "current_item_id=ATR-20260812-AB12CD",
    ).to_dict()

    assert unresolved["ambiguities"]
    assert not resolved["ambiguities"]
    assert resolved["resolved_references"] == [
        {
            "reference_type": "item_id",
            "value": "ATR-20260812-AB12CD",
            "origin": "conversation_context",
        }
    ]


def test_context_item_is_not_injected_without_a_contextual_reference() -> None:
    contract = understand_query_v2(
        "最近有哪些重要新闻？",
        "current_item_id=ATR-20260812-AB12CD",
    ).to_dict()
    assert contract["resolved_references"] == []


def test_context_item_resolves_a_bare_pronoun_for_research() -> None:
    contract = understand_query_v2(
        "解释它为什么重要",
        "current_item_id=ATR-20260812-AB12CD",
    ).to_dict()

    assert contract["resolved_references"] == [
        {
            "reference_type": "item_id",
            "value": "ATR-20260812-AB12CD",
            "origin": "conversation_context",
        }
    ]
    assert contract["ambiguities"] == []
    assert contract["route_confidence"] >= 0.8


def test_unresolved_pronoun_is_not_hidden_by_another_concrete_subject() -> None:
    unresolved = understand_query_v2("比较它和 Nova").to_dict()
    resolved = understand_query_v2(
        "比较它和 Nova",
        "current_item_id=ATR-20260812-AB12CD",
    ).to_dict()

    assert unresolved["ambiguities"]
    assert unresolved["route_confidence"] < 0.5
    assert resolved["ambiguities"] == []
    assert resolved["resolved_references"][0]["value"] == "ATR-20260812-AB12CD"


@pytest.mark.parametrize(
    "query",
    [
        "比较 Nova 和它",
        "解释它，并比较它和 Nova",
    ],
)
def test_right_hand_and_repeated_pronouns_require_context(query: str) -> None:
    unresolved = understand_query_v2(query).to_dict()
    resolved = understand_query_v2(
        query,
        "current_item_id=ATR-20260812-AB12CD",
    ).to_dict()

    assert unresolved["ambiguities"]
    assert unresolved["route_confidence"] < 0.5
    assert resolved["ambiguities"] == []
    assert resolved["resolved_references"][0]["value"] == "ATR-20260812-AB12CD"


def test_in_query_antecedent_does_not_require_conversation_context() -> None:
    contract = understand_query_v2(
        "Anthropic 调整生物安全回退机制，是否说明它降低了安全标准？"
    ).to_dict()

    assert contract["resolved_references"] == []
    assert contract["ambiguities"] == []


def test_disambiguation_contract_always_reports_ambiguity_and_lower_confidence() -> None:
    contract = understand_query_v2(
        "定位 2026-08-09 Product Hunt 标题包含 Nova 的原条目"
    ).to_dict()

    assert contract["answer_mode"] == "item_disambiguation"
    assert contract["ambiguities"]
    assert contract["route_confidence"] < 1


def test_navigation_can_keep_research_as_a_supporting_task() -> None:
    contract = understand_query_v2(
        "打开 ATR-20260812-AB12CD，并解释它为什么重要"
    ).to_dict()
    assert contract["primary_task_family"] == "item_navigation"
    assert contract["supporting_task_families"] == ["evidence_research"]
    assert contract["supporting_contracts"][0]["task_family"] == "evidence_research"
    assert contract["supporting_contracts"][0]["prompt_contract_id"] == "atr.prompt/evidence_research/1.0"


def test_navigation_comparison_and_explicit_web_have_executable_support_contract() -> None:
    contract = understand_query_v2(
        "打开 ATR-20260812-AB12CD，联网比较它和 Nova 的差异"
    ).to_dict()
    assert contract["supporting_task_families"] == ["evidence_research"]
    assert contract["web_permission"] == "explicit"
    assert contract["supporting_contracts"][0]["task_family"] == "evidence_research"


def test_underspecified_request_is_not_a_high_confidence_research_route() -> None:
    contract = understand_query_v2("你觉得这个怎么样？").to_dict()
    assert contract["primary_task_family"] == "evidence_research"
    assert contract["route_confidence"] < 0.5
    assert contract["ambiguities"]


@pytest.mark.parametrize("query", ["解释一下这个", "比较一下这两个", "研究一下它"])
def test_task_verbs_with_only_vague_pronouns_remain_ambiguous(query: str) -> None:
    contract = understand_query_v2(query).to_dict()
    assert contract["route_confidence"] < 0.5
    assert contract["ambiguities"]


@pytest.mark.parametrize(
    "query",
    ["解释一下这个，不要联网", "研究一下它，今天", "比较一下这两个，禁止联网"],
)
def test_constraints_do_not_count_as_a_concrete_research_subject(query: str) -> None:
    contract = understand_query_v2(query).to_dict()
    assert contract["route_confidence"] < 0.5
    assert contract["ambiguities"]


@pytest.mark.parametrize("negative", ["不要联网", "禁止联网", "别联网", "无需联网"])
def test_all_web_denials_are_preserved_as_complete_spans(negative: str) -> None:
    contract = understand_query_v2(f"{negative}，只用内部库解释 Nova").to_dict()
    assert negative in contract["protected_terms"]
    assert contract["web_permission"] == "forbidden"
    assert "web_requested" not in contract["intent_signals"]


def test_short_window_news_structure_generalizes_without_exact_phrase() -> None:
    contract = understand_query_v2("这两天有哪些大动作？").to_dict()
    assert contract["primary_task_family"] == "trend_discovery"


def test_shadow_contract_is_reproducible_and_preserves_raw_query() -> None:
    query = "  最近 Moonshot 有啥大动静？  "
    first = understand_query_v2(query).to_dict()
    second = understand_query_v2(query).to_dict()
    assert first["original_query"] == query
    assert first["request_id"] == second["request_id"]


def test_strict_protected_term_score_penalizes_extra_tokens() -> None:
    perfect = score_protected_terms(["Moonshot", "今天"], ["Moonshot", "今天"])
    overreported = score_protected_terms(
        ["Moonshot", "今天", "最近 Moonshot 有啥大动静"],
        ["Moonshot", "今天"],
    )
    assert perfect.f1 == 1.0
    assert overreported.precision < perfect.precision
