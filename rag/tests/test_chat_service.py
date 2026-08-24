"""Smoke tests for chat response wiring without FastAPI or real LLM services."""

import re
import unittest
from dataclasses import dataclass, field
from datetime import date

from rag.chat_service import (
    _apply_answer_evidence_budget,
    _external_search_cache,
    _format_citation_for_prompt,
    build_chat_response,
)
from rag.query_understanding import analyze_query
from rag.retrieval_gateway import EvidenceBundle
from rag.retriever.hybrid import ChannelOutcome, HybridSearchOutcome, RetrievedChunk


TODAY = date.today().isoformat()


def test_internal_evidence_prompt_preserves_local_navigation_url():
    rendered = _format_citation_for_prompt(
        1,
        {
            "date": "2026-08-11",
            "source": "OpenAI",
            "title": "Example",
            "citation_id": "ATR-20260811-A1B2C3",
            "local_url": "#2026-08-11/ai-topic-radar/item/ATR-20260811-A1B2C3",
            "excerpt": "Evidence",
        },
    )

    assert "#2026-08-11/ai-topic-radar/item/ATR-20260811-A1B2C3" in rendered


def test_internal_evidence_prompt_distinguishes_publication_and_collection_dates():
    rendered = _format_citation_for_prompt(
        1,
        {
            "date": "2026-08-11",
            "report_date": "2026-08-11",
            "publication_date": "2022-02-11",
            "publication_date_source": "upstream_declared",
            "source": "Official",
            "title": "Old article",
            "citation_id": "ATR-20260811-OLD001",
            "excerpt": "Evidence",
        },
    )

    assert "发布日期: 2022-02-11" in rendered
    assert "收录日期: 2026-08-11" in rendered


def test_internal_evidence_prompt_does_not_overclaim_legacy_date_as_verified_publication():
    rendered = _format_citation_for_prompt(
        1,
        {
            "report_date": "2026-08-11",
            "publication_date": "2022-02-11",
            "publication_date_source": "legacy_evidence",
            "source": "Official",
            "title": "Historical item",
            "citation_id": "ATR-20260811-LEG001",
            "excerpt": "Evidence",
        },
    )

    assert "历史记录日期: 2022-02-11（旧语料字段，未独立核验）" in rendered
    assert "发布日期: 2022-02-11" not in rendered


def test_internal_evidence_prompt_labels_report_date_fallback():
    rendered = _format_citation_for_prompt(
        1,
        {
            "date": "2026-08-11",
            "report_date": "2026-08-11",
            "source": "Official",
            "title": "Unknown publication date",
            "citation_id": "ATR-20260811-UNK001",
            "excerpt": "Evidence",
        },
    )

    assert "发布日期: 未知" in rendered
    assert "时间依据: 日报收录日期降级" in rendered


def test_timeline_answer_budget_never_drops_graph_reasoning_evidence():
    plan = analyze_query("OpenAI 的发展历程和变化是什么？")
    citations = [
        {"citation_id": f"text-{index}", "content_type": "topic_candidate"}
        for index in range(12)
    ] + [{
        "citation_id": "graph-reasoning/openai",
        "content_type": "graph_reasoning",
    }]

    selected = _apply_answer_evidence_budget(citations, plan)

    assert len(selected) == 6
    assert selected[-1]["citation_id"] == "graph-reasoning/openai"


@dataclass
class FakeChunk:
    text: str
    metadata: dict = field(default_factory=dict)


class FakeMessage:
    type = "ai"

    def __init__(self, content):
        self.content = content


class FakeAgent:
    def __init__(self):
        self.called = False

    async def ainvoke(self, payload, config=None):
        self.called = True
        self.payload = payload
        self.config = config
        evidence_ids = []
        for evidence_id in re.findall(r"\[(E\d+)\]", payload["messages"][0]["content"]):
            if evidence_id not in evidence_ids:
                evidence_ids.append(evidence_id)
        markers = " ".join(f"[{evidence_id}]" for evidence_id in evidence_ids)
        return {"messages": [FakeMessage(f"这是基于知识库证据生成的回答。{markers}")]}


class SequenceAgent:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    async def ainvoke(self, payload, config=None):
        self.calls.append({"payload": payload, "config": config})
        return {"messages": [FakeMessage(self.answers.pop(0))]}


class ExplodingAgent:
    async def ainvoke(self, payload, config=None):
        raise AssertionError("This execution path must not be used")


class FakeRetriever:
    def __init__(self, chunks):
        self.chunks = chunks

    async def search(self, query, k=5, where=None):
        self.query = query
        self.k = k
        self.where = where
        return self.chunks


class FakeExternalRegistry:
    def __init__(self, result):
        self.result = result
        self.requests = []

    async def search(self, request):
        self.requests.append(request)
        return self.result


class FakeExternalRegistryByProvider:
    def __init__(self, results):
        self.results = results
        self.requests = []

    async def search(self, request):
        self.requests.append(request)
        return self.results[request.provider]


class FakeGateway:
    def __init__(self):
        self.requests = []

    async def retrieve(self, request):
        self.requests.append(request)
        plan = analyze_query(request.question)
        return EvidenceBundle(
            status="ready",
            task_family="trend_discovery",
            records=[
                {
                    "evidence_type": "internal",
                    "date": "2026-08-05",
                    "source": "OpenAI",
                    "title": "Structured trend",
                    "citation_id": "occ-structured-trend",
                    "excerpt": "A structured trend candidate.",
                }
            ],
            analysis=plan,
            query_plan=plan.to_dict(),
            trace={"path": "trend_discovery", "candidate_count": 12},
            elapsed_ms=123.0,
        )


class FakeGraphGateway:
    async def retrieve(self, request):
        plan = analyze_query(request.question)
        return EvidenceBundle(
            status="ready",
            task_family="relation_exploration",
            records=[
                {
                    "evidence_type": "internal",
                    "date": "2026-08-05",
                    "source": "OpenAI",
                    "title": "OpenAI responds to Apple",
                    "citation_id": "ATR-20260805-ABC123",
                    "excerpt": "OpenAI responded to an Apple dispute.",
                },
                {
                    "evidence_type": "internal",
                    "content_type": "graph_reasoning",
                    "date": "2026-08-05",
                    "source": "Neo4j graph",
                    "title": "OpenAI graph relationship evidence",
                    "citation_id": "graph-reasoning/openai",
                    "excerpt": "OpenAI 在图谱中跨多个日期出现。",
                },
            ],
            analysis=plan,
            query_plan=plan.to_dict(),
            trace={"path": "evidence_search", "graph_evidence": {"status": "ready"}},
        )


class FakeImportantNewsGateway:
    async def retrieve(self, request):
        plan = analyze_query(request.question)
        return EvidenceBundle(
            status="ready",
            task_family="trend_discovery",
            records=[{
                "evidence_type": "internal",
                "date": "2026-08-12",
                "source": "OpenAI",
                "title": "Recent major event",
                "citation_id": "recent-event",
                "excerpt": "A recent important event.",
            }],
            background_records=[{
                "evidence_type": "internal",
                "date": "2026-07-20",
                "source": "OpenAI",
                "title": "Older major dispute",
                "citation_id": "older-dispute",
                "excerpt": "An important but older dispute.",
            }],
            analysis=plan,
            query_plan=plan.to_dict(),
            trace={"path": "trend_discovery"},
        )


class FakeNavigationGateway:
    async def retrieve(self, request):
        plan = analyze_query(request.question)
        return EvidenceBundle(
            status="ready",
            task_family="item_navigation",
            records=[
                {
                    "evidence_type": "internal",
                    "content_type": "topic_candidate",
                    "date": "2026-08-05",
                    "report_date": "2026-08-05",
                    "source": "OpenAI",
                    "title": "Introducing The OpenAI Economic Research Exchange",
                    "citation_id": "ATR-20260805-99E550",
                    "occurrence_id": "ATR-20260805-99E550",
                    "local_url": "#2026-08-05/ai-topic-radar/item/ATR-20260805-99E550",
                    "excerpt": "OpenAI introduced an economic research exchange.",
                }
            ],
            analysis=plan,
            query_plan=plan.to_dict(),
            trace={"path": "navigator", "candidate_count": 1},
            elapsed_ms=4.0,
        )


class ChatServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # 外部搜索缓存属于进程状态；每个测试必须从独立状态开始。
        _external_search_cache.clear()

    async def test_exact_item_navigation_returns_without_any_model_call(self):
        response = await build_chat_response(
            ExplodingAgent(),
            FakeRetriever([]),
            "ATR-20260805-99E550",
            [],
            answer_composer=ExplodingAgent(),
            retrieval_gateway=FakeNavigationGateway(),
        )

        self.assertEqual(response["query_understanding"]["task_family"], "item_navigation")
        self.assertEqual(response["tool_trace"]["execution_path"], "deterministic_navigation")
        self.assertEqual(response["tool_trace"]["execution_counts"]["model_turns"], 0)
        self.assertIn(
            "#2026-08-05/ai-topic-radar/item/ATR-20260805-99E550",
            response["answer"],
        )
        self.assertEqual(response["citations"][0]["evidence_id"], "E1")
        self.assertEqual(response["citations"][0]["display_label"], "I1")
        self.assertTrue(response["evidence_integrity"]["valid"])

    async def test_build_chat_response_emits_truthful_progress_in_execution_order(self):
        composer = FakeAgent()
        retriever = FakeRetriever([
            FakeChunk(
                text="Latest AI trend evidence",
                metadata={
                    "date": "2026-08-05",
                    "source": "Anthropic",
                    "title": "Latest AI trend",
                    "citation_id": "2026-08-05/topic-pool/0",
                },
            )
        ])
        events = []

        async def capture(event, data):
            events.append({"event": event, "data": data})

        await build_chat_response(
            ExplodingAgent(),
            retriever,
            "最近有什么热门趋势？",
            [],
            latest_corpus_date="2026-08-05",
            answer_composer=composer,
            progress_callback=capture,
        )

        self.assertEqual(
            [item["event"] for item in events],
            ["understanding", "retrieving", "routing_decided", "evidence_ready", "generating"],
        )
        self.assertEqual(events[0]["data"]["time_window"], "recent_corpus_first")
        self.assertFalse(events[2]["data"]["will_search_web"])
        self.assertEqual(events[3]["data"]["admitted_count"], 1)
        self.assertEqual(events[4]["data"]["execution_path"], "direct_composer")

    async def test_gateway_controls_initial_evidence_path_and_exposes_trace(self):
        gateway = FakeGateway()
        composer = FakeAgent()

        response = await build_chat_response(
            ExplodingAgent(),
            FakeRetriever([]),
            "最近有什么热门趋势？",
            [],
            latest_corpus_date="2026-08-05",
            answer_composer=composer,
            retrieval_gateway=gateway,
        )

        self.assertEqual(len(gateway.requests), 1)
        self.assertEqual(response["query_understanding"]["task_family"], "trend_discovery")
        self.assertEqual(
            response["query_understanding"]["retrieval_gateway"]["path"],
            "trend_discovery",
        )
        self.assertEqual(response["citations"][0]["citation_id"], "occ-structured-trend")
        self.assertEqual(response["tool_trace"]["timings"]["retrieval_ms"], 123.0)

    async def test_resolved_route_contract_is_forwarded_to_gateway_once(self):
        gateway = FakeGateway()
        calls = []
        contract = {
            "schema_version": "atr.route/2.0",
            "primary_task_family": "trend_discovery",
        }

        async def resolve_query_contract(message, context):
            calls.append((message, context))
            return {"status": "resolved", "contract": contract}, {"attempts": 1}

        response = await build_chat_response(
            ExplodingAgent(),
            FakeRetriever([]),
            "最近有什么热门趋势？",
            [],
            context={"date": "2026-08-05"},
            latest_corpus_date="2026-08-05",
            answer_composer=FakeAgent(),
            retrieval_gateway=gateway,
            query_contract_resolver=resolve_query_contract,
        )

        self.assertEqual(calls, [("最近有什么热门趋势？", {"date": "2026-08-05"})])
        self.assertIs(gateway.requests[0].route_contract, contract)
        self.assertEqual(
            response["query_understanding"]["ordered_route_contract"]["status"],
            "resolved",
        )

    async def test_route_contract_failure_is_an_explicit_legacy_fallback(self):
        gateway = FakeGateway()

        async def fail_query_contract(_message, _context):
            raise RuntimeError("provider unavailable")

        response = await build_chat_response(
            ExplodingAgent(),
            FakeRetriever([]),
            "最近有什么热门趋势？",
            [],
            latest_corpus_date="2026-08-05",
            answer_composer=FakeAgent(),
            retrieval_gateway=gateway,
            query_contract_resolver=fail_query_contract,
        )

        self.assertIsNone(gateway.requests[0].route_contract)
        self.assertEqual(
            response["query_understanding"]["ordered_route_contract"]["status"],
            "legacy_fallback",
        )
        self.assertEqual(
            response["query_understanding"]["ordered_route_contract"]["error_type"],
            "RuntimeError",
        )

    async def test_route_contract_clarification_stops_before_retrieval(self):
        class ExplodingGateway:
            async def retrieve(self, _request):
                raise AssertionError("clarification must stop before retrieval")

        async def require_clarification(_message, _context):
            return {
                "status": "clarification_required",
                "contract": None,
                "reasons": ["unresolved references: 它"],
            }, {"attempts": 1}

        response = await build_chat_response(
            ExplodingAgent(),
            FakeRetriever([]),
            "请解释它为什么重要。",
            [],
            answer_composer=ExplodingAgent(),
            retrieval_gateway=ExplodingGateway(),
            query_contract_resolver=require_clarification,
        )

        self.assertIn("请补充", response["answer"])
        self.assertEqual(response["citations"], [])
        self.assertEqual(
            response["query_understanding"]["ordered_route_contract"]["status"],
            "clarification_required",
        )

    async def test_important_news_answer_always_separates_historical_background(self):
        response = await build_chat_response(
            ExplodingAgent(),
            FakeRetriever([]),
            "OpenAI 最近有哪些重要动态？",
            [],
            latest_corpus_date="2026-08-12",
            answer_composer=FakeAgent(),
            retrieval_gateway=FakeImportantNewsGateway(),
        )

        self.assertIn("## 历史背景（不计入近期主榜）", response["answer"])
        self.assertIn("Older major dispute", response["answer"])
        self.assertIn("[E2]", response["answer"])
        self.assertNotIn("Older major dispute", response["answer"].split("## 历史背景")[0])

    async def test_graph_gateway_evidence_is_admitted_and_compiled_into_task_prompt(self):
        composer = FakeAgent()

        response = await build_chat_response(
            ExplodingAgent(),
            FakeRetriever([]),
            "OpenAI 是否跨多个日期反复出现？",
            [],
            answer_composer=composer,
            retrieval_gateway=FakeGraphGateway(),
        )

        prompt = composer.payload["messages"][0]["content"]
        self.assertIn("任务：解释关系", prompt)
        self.assertIn("graph-reasoning/openai", prompt)
        self.assertIn("Neo4j graph", prompt)
        self.assertEqual(
            [citation["citation_id"] for citation in response["citations"]],
            ["ATR-20260805-ABC123", "graph-reasoning/openai"],
        )
        self.assertEqual(
            [citation["evidence_id"] for citation in response["citations"]],
            ["E1", "E2"],
        )

    async def test_relation_answer_repairs_when_it_omits_required_graph_evidence(self):
        composer = SequenceAgent([
            "OpenAI 与 Apple 有关联。[E1]",
            "文本提供事件线索。[E1] 图谱显示跨日关系。[E2]",
        ])

        response = await build_chat_response(
            ExplodingAgent(),
            FakeRetriever([]),
            "OpenAI 是否跨多个日期反复出现？",
            [],
            answer_composer=composer,
            retrieval_gateway=FakeGraphGateway(),
        )

        self.assertEqual(len(composer.calls), 2)
        self.assertTrue(response["evidence_integrity"]["repair_attempted"])
        self.assertTrue(response["evidence_integrity"]["valid"])
        self.assertEqual(response["evidence_integrity"]["required_evidence_ids"], ["E2"])
        self.assertEqual(response["evidence_integrity"]["missing_required_evidence_ids"], [])
        self.assertEqual(
            [citation["citation_id"] for citation in response["citations"]],
            ["ATR-20260805-ABC123", "graph-reasoning/openai"],
        )

    async def test_build_chat_response_returns_agent_answer_with_citations(self):
        agent = FakeAgent()
        retriever = FakeRetriever([
            FakeChunk(
                text="Claude Code Artifacts evidence",
                metadata={
                    "date": "2026-06-21",
                    "source": "Product Hunt",
                    "title": "Claude Code Artifacts",
                    "citation_id": "2026-06-21/topic-pool/0",
                },
            )
        ])

        response = await build_chat_response(agent, retriever, "Claude 最近有什么动态？", [])

        self.assertTrue(agent.called)
        self.assertIn("检索证据", agent.payload["messages"][0]["content"])
        self.assertIn("回答策略", agent.payload["messages"][0]["content"])
        self.assertIn("来源审查", agent.payload["messages"][0]["content"])
        self.assertIn("2026-06-21/topic-pool/0", agent.payload["messages"][0]["content"])
        self.assertIn("Anthropic", retriever.query)
        # “最近”问题扩大候选池用于新鲜度重排，回答仍最多接收 top_k 条证据。
        self.assertEqual(retriever.k, 24)
        self.assertIn("证据范围", response["answer"])
        self.assertIn("这是基于知识库证据生成的回答。", response["answer"])
        self.assertEqual(response["citations"][0]["citation_id"], "2026-06-21/topic-pool/0")
        self.assertEqual(response["citations"][0]["evidence_id"], "E1")
        self.assertEqual(response["citations"][0]["display_label"], "I1")
        self.assertEqual(response["evidence_display_map"], {"E1": "I1"})
        self.assertIn("📚 仅内部语料", response["display_answer"])
        self.assertIn("[I1]", response["display_answer"])
        self.assertEqual(response["claim_evidence"][0]["evidence_ids"], ["E1"])
        self.assertEqual(response["query_understanding"]["intent"], "product_update")
        self.assertIn("Claude", response["query_understanding"]["entities"])
        self.assertEqual(response["query_understanding"]["answer_policy"]["mode"], "internal_grounded")
        self.assertEqual(response["query_understanding"]["tool_routing"]["status"], "internal_only_ready")
        self.assertEqual(response["query_understanding"]["source_review"]["status"], "internal_only")
        self.assertEqual(
            [step["tool"] for step in response["query_understanding"]["tool_routing"]["steps"]],
            ["search_corpus"],
        )
        self.assertEqual(
            set(response["tool_trace"]["timings"]),
            {"retrieval_ms", "agent_ms", "repair_ms", "total_ms"},
        )
        self.assertGreaterEqual(response["tool_trace"]["timings"]["retrieval_ms"], 0)
        self.assertGreaterEqual(response["tool_trace"]["timings"]["agent_ms"], 0)
        self.assertEqual(
            response["tool_trace"]["execution_counts"],
            {"model_turns": 1, "agent_tool_calls": 0, "planned_steps": 1},
        )

    async def test_claim_verification_returns_validated_machine_contract_without_exposing_marker(self):
        agent = SequenceAgent([
            "现有证据不足以证明该主张。[E1]\n"
            '<!--claim-result:{"verdict":"insufficient","rationale":"缺少商业结果",'
            '"evidence_ids":["E1"],"missing_criteria":["财务结果"],'
            '"direct_refutation":false}-->'
        ])
        retriever = FakeRetriever([FakeChunk(
            text="OpenAI announced a research exchange.",
            metadata={
                "date": "2026-08-05",
                "source": "OpenAI",
                "title": "Research Exchange",
                "citation_id": "ATR-20260805-CLAIM1",
            },
        )])

        response = await build_chat_response(
            agent,
            retriever,
            "请验证 OpenAI 已经取得商业成功的真实性和来源",
            [],
        )

        self.assertNotIn("claim-result", response["answer"])
        self.assertTrue(response["claim_verification"]["valid"])
        self.assertEqual(response["claim_verification"]["verdict"], "insufficient")

    async def test_simple_internal_question_uses_direct_composer_without_agent_tools(self):
        composer = FakeAgent()
        retriever = FakeRetriever([
            FakeChunk(
                text="Latest AI trend evidence",
                metadata={
                    "date": "2026-08-05",
                    "source": "Anthropic",
                    "title": "Latest AI trend",
                    "citation_id": "2026-08-05/topic-pool/0",
                },
            )
        ])

        response = await build_chat_response(
            ExplodingAgent(),
            retriever,
            "最近有什么热门趋势？",
            [],
            latest_corpus_date="2026-08-05",
            answer_composer=composer,
        )

        self.assertTrue(composer.called)
        self.assertEqual(response["tool_trace"]["execution_path"], "direct_composer")
        self.assertEqual(response["tool_trace"]["execution_counts"]["model_turns"], 1)
        self.assertEqual(response["tool_trace"]["execution_counts"]["agent_tool_calls"], 0)

    async def test_complex_internal_question_keeps_react_agent_path(self):
        agent = FakeAgent()
        retriever = FakeRetriever([
            FakeChunk(
                text="Claude and OpenAI comparison evidence",
                metadata={
                    "date": "2026-08-05",
                    "source": "ai-topic-radar",
                    "title": "Claude and OpenAI",
                    "citation_id": "2026-08-05/topic-pool/1",
                },
            )
        ])

        response = await build_chat_response(
            agent,
            retriever,
            "对比 Claude 和 OpenAI 最近的产品方向。",
            [],
            latest_corpus_date="2026-08-05",
            answer_composer=ExplodingAgent(),
        )

        self.assertTrue(agent.called)
        self.assertEqual(response["query_understanding"]["task_mode"], "compare")
        self.assertEqual(response["tool_trace"]["execution_path"], "react_agent")

    async def test_recent_trend_repairs_answer_that_uses_too_few_evidence_records(self):
        composer = SequenceAgent([
            "只覆盖一个趋势。[E1]",
            "趋势一。[E1]\n趋势二。[E2]\n趋势三。[E3]",
        ])
        retriever = FakeRetriever([
            FakeChunk(
                text=f"Evidence {index}",
                metadata={
                    "date": "2026-08-05",
                    "source": f"Source {index}",
                    "title": f"Trend {index}",
                    "citation_id": f"2026-08-05/topic-pool/{index}",
                },
            )
            for index in range(1, 4)
        ])

        response = await build_chat_response(
            ExplodingAgent(),
            retriever,
            "最近有什么热门趋势？",
            [],
            latest_corpus_date="2026-08-05",
            answer_composer=composer,
        )

        self.assertEqual(len(composer.calls), 2)
        self.assertTrue(response["evidence_integrity"]["valid"])
        self.assertTrue(response["evidence_integrity"]["repair_attempted"])
        self.assertEqual(response["evidence_integrity"]["minimum_evidence_markers"], 3)
        self.assertEqual(response["evidence_integrity"]["used_evidence_markers"], 3)
        self.assertEqual(len(response["citations"]), 3)

    async def test_recent_trend_caps_answer_ledger_but_keeps_wider_retrieval_pool(self):
        composer = FakeAgent()
        retriever = FakeRetriever([
            FakeChunk(
                text=f"Evidence {index}",
                metadata={
                    "date": "2026-08-05",
                    "source": f"Source {index}",
                    "title": f"Trend {index}",
                    "citation_id": f"2026-08-05/topic-pool/{index}",
                },
            )
            for index in range(1, 11)
        ])

        response = await build_chat_response(
            ExplodingAgent(),
            retriever,
            "最近有什么热门趋势？",
            [],
            latest_corpus_date="2026-08-05",
            answer_composer=composer,
        )

        self.assertEqual(retriever.k, 30)
        self.assertEqual(response["tool_trace"]["evidence_pool_count"], 6)
        self.assertEqual(len(response["citations"]), 6)
        self.assertNotIn("[E7]", composer.payload["messages"][0]["content"])

    async def test_build_chat_response_repairs_invalid_evidence_markers_once(self):
        agent = SequenceAgent([
            "这是缺少证据标记的结论。",
            "这是修复后的有据结论。[E1]",
        ])
        retriever = FakeRetriever([
            FakeChunk(
                text="Claude Code Artifacts evidence",
                metadata={
                    "date": "2026-06-21",
                    "source": "Product Hunt",
                    "title": "Claude Code Artifacts",
                    "citation_id": "2026-06-21/topic-pool/0",
                },
            )
        ])

        response = await build_chat_response(agent, retriever, "Claude 最近有什么动态？", [])

        self.assertEqual(len(agent.calls), 2)
        self.assertIn("修复后的有据结论", response["answer"])
        self.assertTrue(response["evidence_integrity"]["repair_attempted"])
        self.assertTrue(response["evidence_integrity"]["valid"])

    async def test_build_chat_response_only_displays_citations_used_by_answer(self):
        agent = SequenceAgent(["只应展示第二条证据支持的结论。[E2]"])
        retriever = FakeRetriever([
            FakeChunk(
                text="Unrelated candidate",
                metadata={
                    "date": "2026-06-21",
                    "source": "Product Hunt",
                    "title": "Unrelated",
                    "citation_id": "2026-06-21/topic-pool/0",
                },
            ),
            FakeChunk(
                text="Evidence used by the conclusion",
                metadata={
                    "date": "2026-06-21",
                    "source": "Anthropic",
                    "title": "Relevant evidence",
                    "citation_id": "2026-06-21/topic-pool/1",
                },
            ),
        ])

        response = await build_chat_response(agent, retriever, "Claude 最近有什么动态？", [])

        self.assertEqual([citation["evidence_id"] for citation in response["citations"]], ["E2"])
        self.assertEqual(response["claim_evidence"][0]["evidence_ids"], ["E2"])

    async def test_build_chat_response_withholds_answer_after_failed_marker_repair(self):
        agent = SequenceAgent([
            "这是缺少证据标记的结论。",
            "这次仍然没有标记。",
        ])
        retriever = FakeRetriever([
            FakeChunk(
                text="Claude Code Artifacts evidence",
                metadata={
                    "date": "2026-06-21",
                    "source": "Product Hunt",
                    "title": "Claude Code Artifacts",
                    "citation_id": "2026-06-21/topic-pool/0",
                },
            )
        ])

        response = await build_chat_response(agent, retriever, "Claude 最近有什么动态？", [])

        self.assertEqual(len(agent.calls), 2)
        self.assertIn("未展示未经核验的分析", response["answer"])
        self.assertEqual(response["claim_evidence"], [])
        self.assertFalse(response["evidence_integrity"]["valid"])

    async def test_build_chat_response_returns_evidence_insufficient_without_citations(self):
        agent = FakeAgent()
        retriever = FakeRetriever([])

        response = await build_chat_response(agent, retriever, "不存在的话题", [])

        self.assertFalse(agent.called)
        self.assertIn("证据", response["answer"])
        self.assertEqual(response["citations"], [])
        self.assertEqual(response["query_understanding"]["original_question"], "不存在的话题")

    async def test_required_graph_failure_blocks_relational_claims(self):
        agent = ExplodingAgent()

        class PartialRetriever:
            async def search_with_status(self, query, k=5, where=None, graph_requirement="optional"):
                self.graph_requirement = graph_requirement
                chunk = RetrievedChunk(
                    text="OpenAI and Apple text clue",
                    source="vector",
                    score=0.8,
                    metadata={
                        "date": "2026-08-05",
                        "source": "OpenAI",
                        "title": "Apple Is Getting This Wrong",
                        "citation_id": "clue-1",
                    },
                )
                return HybridSearchOutcome(
                    status="partial_error",
                    chunks=[chunk],
                    channels={
                        "vector": ChannelOutcome(status="success", chunks=[chunk]),
                        "graph": ChannelOutcome(status="error", error_code="RuntimeError"),
                    },
                    error_code="required_graph_unavailable",
                )

        retriever = PartialRetriever()
        response = await build_chat_response(
            agent,
            retriever,
            "请分析 OpenAI 与 Apple 最近一个月的跨日关联和趋势变化",
            [],
            latest_corpus_date="2026-08-05",
        )

        self.assertEqual(retriever.graph_requirement, "required")
        self.assertEqual(response["status"], "partial_error")
        self.assertEqual(response["error_code"], "required_graph_unavailable")
        self.assertIn("不生成关系性强结论", response["answer"])
        self.assertEqual(len(response["citations"]), 1)

    async def test_empty_internal_results_can_fall_back_to_web_in_always_mode(self):
        agent = FakeAgent()
        retriever = FakeRetriever([])
        external_registry = FakeExternalRegistry({
            "provider": "tavily",
            "available": True,
            "raw_results_count": 1,
            "errors": [],
            "citations": [{
                "evidence_type": "external",
                "provider": "tavily",
                "source": "openai.com",
                "source_quality": "official",
                "quality_score": 0.95,
                "title": "OpenAI release",
                "url": "https://openai.com/release",
                "retrieved_at": TODAY,
                "excerpt": "Official release evidence.",
            }],
        })

        response = await build_chat_response(
            agent,
            retriever,
            "请查官网核实 OpenAI 发布",
            [],
            web_search_mode="always",
            external_search_registry=external_registry,
            configured_search_providers={"tavily"},
            external_deep_fetcher=lambda url: {
                "ok": True,
                "url": url,
                "final_url": url,
                "fetched_at": f"{TODAY}T00:00:00+00:00",
                "title": "OpenAI release",
                "text_excerpt": "Verified official release evidence.",
                "error": "",
            },
        )

        self.assertTrue(external_registry.requests)
        self.assertTrue(agent.called)
        self.assertEqual(response["citations"][0]["evidence_type"], "external")
        self.assertIn("[W1 🌐]", response["display_answer"])
        self.assertEqual(response["query_understanding"]["web_search_decision"]["reason"], "user_forced")

    async def test_never_mode_does_not_call_external_registry(self):
        agent = FakeAgent()
        retriever = FakeRetriever([])
        external_registry = FakeExternalRegistry({"available": True, "citations": []})

        response = await build_chat_response(
            agent,
            retriever,
            "只基于内部语料回答",
            [],
            web_search_mode="never",
            external_search_registry=external_registry,
            configured_search_providers={"tavily"},
        )

        self.assertFalse(external_registry.requests)
        self.assertFalse(agent.called)
        self.assertEqual(response["query_understanding"]["web_search_decision"]["reason"], "internal_only_constraint")

    async def test_auto_mode_does_not_hide_internal_retrieval_error_with_web(self):
        class FailingRetriever:
            async def search(self, query, k=5, where=None):
                raise RuntimeError("database unavailable")

        external_registry = FakeExternalRegistry({"available": True, "citations": []})
        response = await build_chat_response(
            FakeAgent(),
            FailingRetriever(),
            "稳定知识问题",
            [],
            web_search_mode="auto",
            external_search_registry=external_registry,
            configured_search_providers={"tavily"},
        )

        self.assertFalse(external_registry.requests)
        self.assertIn("内部检索暂时不可用", response["answer"])
        self.assertEqual(response["query_understanding"]["internal_retrieval"]["status"], "error")

    async def test_build_chat_response_passes_metadata_filter_to_retriever(self):
        agent = FakeAgent()
        retriever = FakeRetriever([
            FakeChunk(
                text="GitHub evidence",
                metadata={
                    "date": "2026-06-21",
                    "source": "GitHub Trending",
                    "title": "AI Repo",
                    "citation_id": "2026-06-21/topic-pool/1",
                },
            )
        ])

        response = await build_chat_response(
            agent,
            retriever,
            "过去一周 GitHub 热榜上有什么值得关注的选题？",
            [],
            latest_corpus_date="2026-06-21",
        )

        self.assertEqual(
            retriever.where,
            {
                "$and": [
                    {"content_type": "topic_candidate"},
                    {"source_family": "GitHub"},
                    {
                        "effective_date": {
                            "$in": [
                                "2026-06-15",
                                "2026-06-16",
                                "2026-06-17",
                                "2026-06-18",
                                "2026-06-19",
                                "2026-06-20",
                                "2026-06-21",
                            ]
                        }
                    },
                ]
            },
        )
        self.assertEqual(response["query_understanding"]["latest_corpus_date"], "2026-06-21")
        self.assertEqual(response["query_understanding"]["metadata_filter"], retriever.where)

    async def test_build_chat_response_marks_needs_web_questions(self):
        agent = FakeAgent()
        retriever = FakeRetriever([
            FakeChunk(
                text="RAG evolution evidence",
                metadata={
                    "date": "2026-06-20",
                    "source": "ai-topic-radar",
                    "title": "RAG research map",
                    "citation_id": "2026-06-20/topic-pool/2",
                },
            )
        ])

        response = await build_chat_response(
            agent,
            retriever,
            "请帮我梳理一下 RAG 技术的发展演进路线，以及相关的论文、文章等资料。",
            [],
            configured_search_providers=set(),
        )

        self.assertIn("不要声称已经完成外部检索", agent.payload["messages"][0]["content"])
        self.assertIn("外部工具状态", agent.payload["messages"][0]["content"])
        self.assertIn("planned_unavailable", agent.payload["messages"][0]["content"])
        self.assertIn("仍需要外部证据", response["answer"])
        self.assertEqual(
            response["query_understanding"]["answer_policy"]["mode"],
            "needs_external_evidence",
        )
        self.assertEqual(
            response["query_understanding"]["tool_routing"]["status"],
            "external_required_not_available",
        )

    async def test_build_chat_response_merges_external_citations_for_needs_web_questions(self):
        agent = FakeAgent()
        retriever = FakeRetriever([
            FakeChunk(
                text="Internal RAG evolution evidence",
                metadata={
                    "date": "2026-06-20",
                    "source": "ai-topic-radar",
                    "title": "RAG research map",
                    "citation_id": "2026-06-20/topic-pool/2",
                },
            )
        ])
        external_registry = FakeExternalRegistry(
            {
                "provider": "tavily",
                "available": True,
                "query": "RAG evolution papers",
                "task_type": "research_paper",
                "raw_results_count": 1,
                "errors": [],
                "citations": [
                    {
                        "evidence_type": "external",
                        "provider": "tavily",
                        "source": "arxiv.org",
                        "source_quality": "academic",
                        "quality_score": 0.9,
                        "needs_deep_fetch": False,
                        "title": "Retrieval-Augmented Generation",
                        "url": "https://arxiv.org/abs/example",
                        "retrieved_at": TODAY,
                        "excerpt": "External paper evidence.",
                    }
                ],
            }
        )
        events = []

        async def capture(event, data):
            events.append({"event": event, "data": data})

        response = await build_chat_response(
            agent,
            retriever,
            "请帮我梳理一下 RAG 技术的发展演进路线，以及相关的论文、文章等资料。",
            [],
            external_search_registry=external_registry,
            configured_search_providers={"tavily"},
            progress_callback=capture,
        )

        self.assertTrue(external_registry.requests)
        self.assertEqual(external_registry.requests[0].task_type, "research_paper")
        self.assertEqual(len(response["citations"]), 2)
        self.assertEqual(response["citations"][1]["evidence_type"], "external")
        self.assertIn("外部证据", agent.payload["messages"][0]["content"])
        self.assertIn("primary_evidence", agent.payload["messages"][0]["content"])
        self.assertEqual(
            response["query_understanding"]["answer_policy"]["mode"],
            "internal_and_external_grounded",
        )
        self.assertEqual(
            response["query_understanding"]["external_search"]["provider"],
            "tavily",
        )
        self.assertEqual(
            response["query_understanding"]["source_review"]["status"],
            "primary_sources_available",
        )
        self.assertIn("外部证据", response["answer"])
        event_names = [item["event"] for item in events]
        self.assertIn("routing_decided", event_names)
        self.assertIn("web_searching", event_names)
        self.assertIn("web_results_ready", event_names)
        self.assertLess(event_names.index("web_searching"), event_names.index("web_results_ready"))

    async def test_build_chat_response_includes_deep_fetch_evidence_when_fetcher_is_provided(self):
        agent = FakeAgent()
        retriever = FakeRetriever([
            FakeChunk(
                text="Internal OKF evidence",
                metadata={
                    "date": "2026-06-21",
                    "source": "ai-topic-radar",
                    "title": "Google OKF",
                    "citation_id": "2026-06-21/topic-pool/5",
                },
            )
        ])
        external_registry = FakeExternalRegistry(
            {
                "provider": "tavily",
                "available": True,
                "query": "Google OKF ALM Wiki",
                "task_type": "official_source_lookup",
                "raw_results_count": 1,
                "errors": [],
                "citations": [
                    {
                        "evidence_type": "external",
                        "provider": "tavily",
                        "source": "cloud.google.com",
                        "source_quality": "official",
                        "quality_score": 0.95,
                        "needs_deep_fetch": False,
                        "title": "How the Open Knowledge Format can improve data sharing",
                        "url": "https://cloud.google.com/blog/okf",
                        "retrieved_at": TODAY,
                        "excerpt": "Provider snippet.",
                    }
                ],
            }
        )

        def fake_deep_fetcher(url):
            return {
                "ok": True,
                "url": url,
                "final_url": url,
                "fetched_at": "2026-06-22T00:00:00+00:00",
                "title": "Fetched OKF title",
                "text_excerpt": "Fetched OKF page evidence.",
                "error": "",
            }
        events = []

        async def capture(event, data):
            events.append({"event": event, "data": data})

        response = await build_chat_response(
            agent,
            retriever,
            "Google OKF 和 ALM Wiki 有什么关系？",
            [],
            external_search_registry=external_registry,
            configured_search_providers={"tavily"},
            external_deep_fetcher=fake_deep_fetcher,
            progress_callback=capture,
        )

        self.assertIn("深度抓取", agent.payload["messages"][0]["content"])
        self.assertIn("Fetched OKF page evidence.", agent.payload["messages"][0]["content"])
        self.assertTrue(response["citations"][1]["deep_fetch"]["ok"])
        self.assertEqual(response["query_understanding"]["deep_fetch"]["success_count"], 1)
        self.assertIn("deep_fetching", [item["event"] for item in events])
        fetch_step = [
            step for step in response["query_understanding"]["tool_routing"]["steps"]
            if step["tool"] == "fetch_url"
        ][0]
        self.assertEqual(fetch_step["state"], "executed")

    async def test_build_chat_response_demotes_internal_noise_when_external_evidence_exists(self):
        agent = FakeAgent()
        retriever = FakeRetriever([
            FakeChunk(
                text="Google agent ecosystem context",
                metadata={
                    "date": "2026-06-21",
                    "source": "InfoQ 中国",
                    "title": "Google 想为 AI Agent 打造下一个 Kubernetes",
                    "citation_id": "2026-06-21/topic-pool/google-agent",
                },
            ),
            FakeChunk(
                text="GLM benchmark unrelated to OKF",
                metadata={
                    "date": "2026-06-21",
                    "source": "掘金",
                    "title": "GLM5.2超过Opus4.8Think，全球第二了！",
                    "citation_id": "2026-06-21/topic-pool/glm",
                },
            ),
            FakeChunk(
                text="Vue3 coding assistant practices unrelated to OKF",
                metadata={
                    "date": "2026-06-20",
                    "source": "掘金",
                    "title": "告别 AI 乱码！Vue3+TS 项目的 AI 编码助手规范实践",
                    "citation_id": "2026-06-20/topic-pool/vue3",
                },
            ),
        ])
        external_registry = FakeExternalRegistry(
            {
                "provider": "tavily",
                "available": True,
                "query": "Google OKF ALM Wiki",
                "task_type": "official_source_lookup",
                "raw_results_count": 1,
                "errors": [],
                "citations": [
                    {
                        "evidence_type": "external",
                        "provider": "tavily",
                        "source": "cloud.google.com",
                        "source_quality": "official",
                        "quality_score": 0.95,
                        "needs_deep_fetch": False,
                        "title": "How the Open Knowledge Format can improve data sharing",
                        "url": "https://cloud.google.com/blog/okf",
                        "retrieved_at": TODAY,
                        "excerpt": "OKF official evidence.",
                    }
                ],
            }
        )

        response = await build_chat_response(
            agent,
            retriever,
            "Google OKF 和 ALM Wiki 有什么关系？",
            [],
            external_search_registry=external_registry,
            configured_search_providers={"tavily"},
        )

        titles = [citation["title"] for citation in response["citations"]]
        self.assertIn("How the Open Knowledge Format can improve data sharing", titles)
        self.assertIn("Google 想为 AI Agent 打造下一个 Kubernetes", titles)
        self.assertNotIn("GLM5.2超过Opus4.8Think，全球第二了！", titles)
        self.assertNotIn("告别 AI 乱码！Vue3+TS 项目的 AI 编码助手规范实践", titles)

    async def test_official_source_lookup_continues_until_official_citation(self):
        agent = FakeAgent()
        retriever = FakeRetriever([
            FakeChunk(
                text="Internal Google OKF context",
                metadata={
                    "date": "2026-06-21",
                    "source": "InfoQ 中国",
                    "title": "Google 想为 AI Agent 打造下一个 Kubernetes",
                    "citation_id": "2026-06-21/topic-pool/google-agent",
                },
            )
        ])
        external_registry = FakeExternalRegistryByProvider(
            {
                "tavily": {
                    "provider": "tavily",
                    "available": True,
                    "raw_results_count": 1,
                    "errors": [],
                    "citations": [
                        {
                            "evidence_type": "external",
                            "provider": "tavily",
                            "source": "tinycommand.com",
                            "source_quality": "generic",
                            "quality_score": 0.55,
                            "needs_deep_fetch": True,
                            "title": "Open Knowledge Format overview",
                            "url": "https://tinycommand.com/okf",
                            "retrieved_at": TODAY,
                            "excerpt": "Generic OKF context.",
                        }
                    ],
                },
                "brave": {
                    "provider": "brave",
                    "available": True,
                    "raw_results_count": 1,
                    "errors": [],
                    "citations": [
                        {
                            "evidence_type": "external",
                            "provider": "brave",
                            "source": "cloud.google.com",
                            "source_quality": "official",
                            "quality_score": 0.95,
                            "needs_deep_fetch": False,
                            "title": "How the Open Knowledge Format can improve data sharing",
                            "url": "https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing",
                            "retrieved_at": TODAY,
                            "excerpt": "Official OKF evidence.",
                        }
                    ],
                },
            }
        )

        response = await build_chat_response(
            agent,
            retriever,
            "Google OKF 和 ALM Wiki 有什么关系？",
            [],
            external_search_registry=external_registry,
            configured_search_providers={"tavily", "brave"},
        )

        self.assertEqual([request.provider for request in external_registry.requests], ["tavily", "brave"])
        self.assertEqual(response["query_understanding"]["external_search"]["provider"], "brave")
        self.assertEqual(response["citations"][-1]["source_quality"], "official")

    async def test_official_source_lookup_does_not_stop_at_vendor_navigation_page(self):
        agent = FakeAgent()
        retriever = FakeRetriever([])
        external_registry = FakeExternalRegistryByProvider(
            {
                "tavily": {
                    "provider": "tavily",
                    "available": True,
                    "raw_results_count": 1,
                    "errors": [],
                    "citations": [
                        {
                            "evidence_type": "external",
                            "provider": "tavily",
                            "source": "openai.com",
                            "source_quality": "official",
                            "quality_score": 0.95,
                            "needs_deep_fetch": False,
                            "title": "OpenAI Newsroom | Product | OpenAI",
                            "url": "https://openai.com/news/product-releases/",
                            "retrieved_at": TODAY,
                            "published_at": TODAY,
                            "excerpt": "Product release listing page.",
                        }
                    ],
                },
                "brave": {
                    "provider": "brave",
                    "available": True,
                    "raw_results_count": 1,
                    "errors": [],
                    "citations": [
                        {
                            "evidence_type": "external",
                            "provider": "brave",
                            "source": "openai.com",
                            "source_quality": "official",
                            "quality_score": 0.95,
                            "needs_deep_fetch": False,
                            "title": "Introducing a new OpenAI API capability",
                            "url": "https://openai.com/index/new-api-capability/",
                            "retrieved_at": TODAY,
                            "published_at": TODAY,
                            "excerpt": "OpenAI announced a new API capability.",
                        }
                    ],
                },
            }
        )

        response = await build_chat_response(
            agent,
            retriever,
            "请联网核实 OpenAI 过去 7 天有哪些官方技术发布",
            [],
            external_search_registry=external_registry,
            configured_search_providers={"tavily", "brave"},
            web_search_mode="always",
        )

        self.assertEqual([request.provider for request in external_registry.requests], ["tavily", "brave"])
        self.assertEqual(response["query_understanding"]["external_search"]["provider"], "brave")
        self.assertEqual(response["query_understanding"]["source_admission"]["provisional_admitted_count"], 1)
        self.assertEqual(response["query_understanding"]["source_admission"]["admitted_count"], 0)

    async def test_web_attempt_with_only_navigation_pages_is_reported_as_degraded_not_unavailable(self):
        agent = FakeAgent()
        retriever = FakeRetriever([
            FakeChunk(
                text="Internal OpenAI context",
                metadata={
                    "date": "2026-08-05",
                    "source": "OpenAI",
                    "title": "Internal OpenAI release candidate",
                    "citation_id": "2026-08-05/openai/release",
                },
            )
        ])
        external_registry = FakeExternalRegistryByProvider(
            {
                "tavily": {
                    "provider": "tavily",
                    "available": True,
                    "raw_results_count": 1,
                    "errors": [],
                    "citations": [
                        {
                            "evidence_type": "external",
                            "provider": "tavily",
                            "source": "openai.com",
                            "source_quality": "official",
                            "quality_score": 0.95,
                            "needs_deep_fetch": False,
                            "title": "OpenAI Newsroom | Product | OpenAI",
                            "url": "https://openai.com/news/product-releases/",
                            "retrieved_at": TODAY,
                            "published_at": TODAY,
                            "excerpt": "Product release listing page.",
                        }
                    ],
                }
            }
        )

        response = await build_chat_response(
            agent,
            retriever,
            "请联网核实 OpenAI 过去 7 天有哪些官方技术发布",
            [],
            external_search_registry=external_registry,
            configured_search_providers={"tavily"},
            web_search_mode="always",
        )

        route = response["query_understanding"]["tool_routing"]
        assert route["status"] == "external_degraded"
        assert next(step for step in route["steps"] if step["tool"] == "web_search")["state"] == "executed"
        assert response["display_answer"].startswith("⚠️ 已联网检索但没有结果达到正式引用标准")

    async def test_recent_verification_does_not_promote_unfetched_provider_snippet(self):
        agent = FakeAgent()
        retriever = FakeRetriever([
            FakeChunk(
                text="Internal OpenAI context",
                metadata={
                    "date": "2026-08-05",
                    "source": "OpenAI",
                    "title": "Internal OpenAI release candidate",
                    "citation_id": "2026-08-05/openai/release",
                },
            )
        ])
        external_registry = FakeExternalRegistryByProvider(
            {
                "tavily": {
                    "provider": "tavily",
                    "available": True,
                    "raw_results_count": 1,
                    "errors": [],
                    "citations": [
                        {
                            "evidence_type": "external",
                            "provider": "tavily",
                            "source": "openai.com",
                            "source_quality": "official",
                            "quality_score": 0.95,
                            "needs_deep_fetch": False,
                            "title": "Introducing a new OpenAI API capability",
                            "url": "https://openai.com/index/new-api-capability/",
                            "retrieved_at": TODAY,
                            "published_at": TODAY,
                            "excerpt": "OpenAI announced a new API capability.",
                        }
                    ],
                }
            }
        )

        response = await build_chat_response(
            agent,
            retriever,
            "请联网核实 OpenAI 过去 7 天有哪些官方技术发布",
            [],
            external_search_registry=external_registry,
            configured_search_providers={"tavily"},
            external_deep_fetcher=None,
            web_search_mode="always",
        )

        assert all(citation.get("evidence_type") != "external" for citation in response["citations"])
        assert response["search_references"][0]["not_admitted_reason"] == "deep_fetch_required"
        assert response["query_understanding"]["source_admission"]["admitted_count"] == 0


if __name__ == "__main__":
    unittest.main()
