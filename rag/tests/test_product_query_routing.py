"""Product-facing routing regression through the public resolver seam."""

from __future__ import annotations

import pytest

from rag.product_query_catalog import HOME_SUGGESTED_QUESTIONS, PRODUCT_QUERY_CASES
from rag.query_route_resolver import QueryRouteResolver
from rag.query_understanding_v2 import understand_query_v2


@pytest.mark.asyncio
async def test_home_suggestions_resolve_without_semantic_model() -> None:
    async def forbidden_fallback(_query: str, _context: dict):
        raise AssertionError("homepage suggestions must not call the semantic model")

    resolver = QueryRouteResolver(semantic_fallback=forbidden_fallback)

    assert HOME_SUGGESTED_QUESTIONS == (
        "最近有什么热门趋势？",
        "推荐值得深挖的选题",
        "Claude 最近有什么动态？",
    )
    for question in HOME_SUGGESTED_QUESTIONS:
        envelope, metadata = await resolver(question, {})
        assert envelope["status"] == "resolved"
        assert metadata["route_source"] == "product_catalog"
        assert metadata["model_calls"] == 0


@pytest.mark.asyncio
async def test_product_query_cases_match_their_route_contracts() -> None:
    resolver = QueryRouteResolver()

    for case in PRODUCT_QUERY_CASES:
        envelope, metadata = await resolver(case.question, {})
        contract = envelope["contract"]
        assert envelope["status"] == "resolved", case.case_id
        assert contract["primary_task_family"] == case.task_family, case.case_id
        assert contract["answer_mode"] == case.answer_mode, case.case_id
        assert contract["ambiguities"] == [], case.case_id
        assert metadata["model_calls"] == 0, case.case_id


@pytest.mark.asyncio
async def test_subject_specific_suggestion_preserves_retrieval_subject() -> None:
    resolver = QueryRouteResolver()

    envelope, _ = await resolver("Claude 最近有什么动态？", {})

    assert "Claude" in envelope["contract"]["subjects"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "最近Claude有什么新的趋势吗?",
        "最近 Anthropic 有什么新趋势？",
        "最近OpenAI有什么新的趋势吗?",
    ],
)
async def test_recent_subject_trend_variants_use_trend_discovery(question: str) -> None:
    resolver = QueryRouteResolver()

    envelope, _ = await resolver(question, {})

    assert envelope["status"] == "resolved"
    assert envelope["contract"]["primary_task_family"] == "trend_discovery"
    assert envelope["contract"]["answer_mode"] == "important_news"


@pytest.mark.asyncio
async def test_low_confidence_query_uses_one_semantic_fallback() -> None:
    calls = []

    async def fallback(query: str, context: dict):
        calls.append((query, context))
        return {
            "status": "clarification_required",
            "contract": None,
            "reasons": ["missing subject"],
        }, {"attempts": 1}

    resolver = QueryRouteResolver(semantic_fallback=fallback)
    envelope, metadata = await resolver("你觉得这个怎么样？", {})

    assert envelope["status"] == "clarification_required"
    assert calls == [("你觉得这个怎么样？", {})]
    assert metadata["route_source"] == "semantic_fallback"
    assert metadata["model_calls"] == 1


@pytest.mark.asyncio
async def test_known_subject_without_user_goal_requests_clarification_without_model() -> None:
    calls = []

    async def forbidden_fallback(query: str, context: dict):
        calls.append((query, context))
        contract = understand_query_v2(query).to_dict()
        contract["ambiguities"] = []
        contract["route_confidence"] = 0.9
        return {"status": "resolved", "contract": contract, "reasons": []}, {
            "attempts": 1,
        }

    resolver = QueryRouteResolver(semantic_fallback=forbidden_fallback)
    envelope, metadata = await resolver("open ai", {})

    assert envelope["status"] == "clarification_required"
    assert "request lacks a concrete subject or success criterion" in envelope["reasons"]
    assert calls == []
    assert metadata["route_source"] == "deterministic_clarification"
    assert metadata["model_calls"] == 0


@pytest.mark.asyncio
async def test_unresolved_contextual_comparison_clarifies_without_semantic_model() -> None:
    calls = []

    async def forbidden_fallback(query: str, context: dict):
        calls.append((query, context))
        raise AssertionError("unresolved conversation reference must clarify locally")

    resolver = QueryRouteResolver(semantic_fallback=forbidden_fallback)
    envelope, metadata = await resolver(
        "比较刚才那两个产品在上下文保留方面的差异。",
        {},
    )

    assert envelope["status"] == "clarification_required"
    assert calls == []
    assert metadata["route_source"] == "deterministic_clarification"
    assert metadata["model_calls"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "打开 8 月 11 日那条说 Claude Code 默认启用自动模式的记录。",
        "找那个能把代码库文档、SQL schema 和配置转成知识图谱的项目。",
    ],
)
async def test_explicit_item_requests_are_not_mistaken_for_bare_entity_queries(question: str) -> None:
    resolver = QueryRouteResolver()

    envelope, _ = await resolver(question, {})

    assert envelope["status"] != "clarification_required"


@pytest.mark.asyncio
async def test_explicit_two_product_comparison_is_not_mistaken_for_a_bare_entity_query() -> None:
    resolver = QueryRouteResolver()

    envelope, _ = await resolver(
        "Graphify 和 claude-mem 在保留和检索上下文上分别做什么？",
        {},
    )

    assert envelope["status"] != "clarification_required"


def test_lowercase_hyphenated_product_name_is_preserved_for_retrieval() -> None:
    contract = understand_query_v2(
        "Graphify 和 claude-mem 在保留和检索上下文上分别做什么？"
    ).to_dict()

    assert "Graphify" in contract["protected_terms"]
    assert "claude-mem" in contract["protected_terms"]


@pytest.mark.asyncio
async def test_unregistered_named_subject_uses_semantic_fallback_once() -> None:
    calls = []

    async def fallback(query: str, context: dict):
        calls.append((query, context))
        contract = understand_query_v2(query).to_dict()
        contract["subjects"] = ["NovaFlow"]
        return {"status": "resolved", "contract": contract, "reasons": []}, {
            "attempts": 1,
        }

    resolver = QueryRouteResolver(semantic_fallback=fallback)
    envelope, metadata = await resolver("NovaFlow 最近有什么动态？", {})

    assert calls == [("NovaFlow 最近有什么动态？", {})]
    assert envelope["contract"]["subjects"] == ["NovaFlow"]
    assert metadata["route_source"] == "semantic_fallback"
    assert metadata["model_calls"] == 1


@pytest.mark.asyncio
async def test_semantic_fallback_has_a_hard_timeout() -> None:
    async def fallback(_query: str, _context: dict):
        await __import__("asyncio").sleep(1)

    resolver = QueryRouteResolver(
        semantic_fallback=fallback,
        fallback_timeout_seconds=0.01,
    )
    envelope, metadata = await resolver("你觉得这个怎么样？", {})

    assert envelope["status"] == "clarification_required"
    assert envelope["reasons"] == ["semantic_route_timeout"]
    assert metadata["route_source"] == "semantic_fallback_timeout"
    assert metadata["model_calls"] == 1


def test_server_keeps_deterministic_resolver_without_provider_key(monkeypatch) -> None:
    from rag import server

    monkeypatch.setattr(server, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(server, "DEEPSEEK_API_KEY", "")

    resolver = server._build_query_contract_resolver()

    assert isinstance(resolver, QueryRouteResolver)
