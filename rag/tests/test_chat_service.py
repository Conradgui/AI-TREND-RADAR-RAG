"""Smoke tests for chat response wiring without FastAPI or real LLM services."""

import unittest
from dataclasses import dataclass, field
from datetime import date

from rag import chat_service
from rag.agent.llm import DirectLLMAgent
from rag.chat_service import build_chat_response


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
        return {"messages": [FakeMessage("这是基于知识库证据生成的回答。")]}


class FakeLLM:
    async def ainvoke(self, messages, config=None):
        self.messages = messages
        self.config = config
        return FakeMessage("Direct LLM answer")


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
        chat_service._external_search_cache.clear()

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
        self.assertEqual(agent.config, {"recursion_limit": 11})
        self.assertIn("检索证据", agent.payload["messages"][0]["content"])
        self.assertIn("回答策略", agent.payload["messages"][0]["content"])
        self.assertIn("来源审查", agent.payload["messages"][0]["content"])
        self.assertIn("2026-06-21/topic-pool/0", agent.payload["messages"][0]["content"])
        self.assertIn("Anthropic", retriever.query)
        self.assertEqual(retriever.k, 8)
        self.assertIn("证据范围", response["answer"])
        self.assertIn("这是基于知识库证据生成的回答。", response["answer"])
        self.assertEqual(response["citations"][0]["citation_id"], "2026-06-21/topic-pool/0")
        self.assertEqual(response["query_understanding"]["intent"], "product_update")
        self.assertIn("Claude", response["query_understanding"]["entities"])
        self.assertEqual(response["query_understanding"]["answer_policy"]["mode"], "internal_grounded")
        self.assertEqual(response["query_understanding"]["tool_routing"]["status"], "internal_only_ready")
        self.assertEqual(response["query_understanding"]["source_review"]["status"], "internal_only")
        self.assertEqual(
            [step["tool"] for step in response["query_understanding"]["tool_routing"]["steps"]],
            ["search_corpus"],
        )

    async def test_build_chat_response_returns_evidence_insufficient_without_citations(self):
        agent = FakeAgent()
        retriever = FakeRetriever([])

        response = await build_chat_response(agent, retriever, "不存在的话题", [])

        self.assertFalse(agent.called)
        self.assertIn("证据", response["answer"])
        self.assertEqual(response["citations"], [])
        self.assertEqual(response["query_understanding"]["original_question"], "不存在的话题")

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
                        "retrieved_at": date.today().isoformat(),
                        "excerpt": "External paper evidence.",
                    }
                ],
            }
        )

        response = await build_chat_response(
            agent,
            retriever,
            "请帮我梳理一下 RAG 技术的发展演进路线，以及相关的论文、文章等资料。",
            [],
            external_search_registry=external_registry,
            configured_search_providers={"tavily"},
        )

        self.assertTrue(external_registry.requests)
        self.assertEqual(external_registry.requests[0].query, "RAG evolution papers survey")
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
                        "retrieved_at": date.today().isoformat(),
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

        response = await build_chat_response(
            agent,
            retriever,
            "Google OKF 和 ALM Wiki 有什么关系？",
            [],
            external_search_registry=external_registry,
            configured_search_providers={"tavily"},
            external_deep_fetcher=fake_deep_fetcher,
        )

        self.assertIn("深度抓取", agent.payload["messages"][0]["content"])
        self.assertIn("Fetched OKF page evidence.", agent.payload["messages"][0]["content"])
        self.assertTrue(response["citations"][1]["deep_fetch"]["ok"])
        self.assertEqual(response["query_understanding"]["deep_fetch"]["success_count"], 1)
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
                        "retrieved_at": date.today().isoformat(),
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
                            "retrieved_at": date.today().isoformat(),
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
                            "retrieved_at": date.today().isoformat(),
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

    async def test_direct_llm_agent_accepts_the_shared_agent_config(self):
        llm = FakeLLM()
        agent = DirectLLMAgent(llm)

        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "hello"}]},
            config={"recursion_limit": 11},
        )

        self.assertEqual(llm.config, {"recursion_limit": 11})
        self.assertEqual(result["messages"][0].content, "Direct LLM answer")

    async def test_cached_external_evidence_is_not_reported_as_new_search_execution(self):
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
        external_registry = FakeExternalRegistry(
            {
                "provider": "tavily",
                "available": True,
                "raw_results_count": 1,
                "errors": [],
                "citations": [{
                    "evidence_type": "external",
                    "provider": "tavily",
                    "source": "arxiv.org",
                    "source_quality": "academic",
                    "quality_score": 0.9,
                    "needs_deep_fetch": False,
                    "title": "Retrieval-Augmented Generation",
                    "url": "https://arxiv.org/abs/example",
                    "retrieved_at": date.today().isoformat(),
                    "excerpt": "External paper evidence.",
                }],
            }
        )
        question = "请帮我梳理一下 RAG 技术的发展演进路线，以及相关的论文、文章等资料。"

        await build_chat_response(
            agent, retriever, question, [], external_search_registry=external_registry,
            configured_search_providers={"tavily"},
        )
        cached_response = await build_chat_response(
            agent, retriever, question, [], external_search_registry=external_registry,
            configured_search_providers={"tavily"},
        )

        self.assertEqual(len(external_registry.requests), 1)
        self.assertTrue(cached_response["query_understanding"]["external_search"]["from_cache"])
        web_search_step = next(
            step for step in cached_response["query_understanding"]["tool_routing"]["steps"]
            if step["tool"] == "web_search"
        )
        self.assertEqual(web_search_step["state"], "reused_cached_result")


if __name__ == "__main__":
    unittest.main()
