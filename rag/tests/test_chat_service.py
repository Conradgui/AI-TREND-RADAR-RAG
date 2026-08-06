"""Smoke tests for chat response wiring without FastAPI or real LLM services."""

import re
import unittest
from dataclasses import dataclass, field
from datetime import date

from rag.chat_service import _external_search_cache, build_chat_response


TODAY = date.today().isoformat()


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


class ChatServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # 外部搜索缓存属于进程状态；每个测试必须从独立状态开始。
        _external_search_cache.clear()

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
                    {"source_family": "GitHub"},
                    {
                        "date": {
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
