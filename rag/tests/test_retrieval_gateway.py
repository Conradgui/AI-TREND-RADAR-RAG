import unittest

from rag.retrieval_gateway import EvidenceRetrievalGateway, ResearchRequest
from rag.retriever.hybrid import RetrievedChunk


class _FailingRetriever:
    async def search(self, *args, **kwargs):
        raise AssertionError("generic retriever should not be called")


class _NavigatorStore:
    def search(self, query, k=5, where=None):
        return [
            {
                "text": "Apple 正在错误理解 AI 产品竞争。",
                "match_type": "exact_title",
                "lexical_score": 0.0,
                "metadata": {
                    "content_type": "topic_candidate",
                    "date": "2026-08-05",
                    "source": "OpenAI",
                    "title": "Apple Is Getting This Wrong",
                    "citation_id": "occ-apple",
                    "occurrence_id": "occ-apple",
                    "content_id": "content-apple",
                    "local_url": "#2026-08-05/ai-topic-radar/item/occ-apple",
                    "url": "https://example.com/apple",
                    "evidence": "Apple 正在错误理解 AI 产品竞争。",
                },
            }
        ]


class _NonExactStore:
    def search(self, query, k=5, where=None):
        return [
            {
                "text": "A loosely related record",
                "match_type": "lexical",
                "lexical_score": 1.0,
                "metadata": {},
            }
        ]


class _EvidenceRetriever:
    def __init__(self):
        self.calls = 0

    async def search(self, query, k=5, where=None):
        self.calls += 1
        return [
            RetrievedChunk(
                text="RAG evidence",
                source="vector",
                score=0.8,
                metadata={
                    "date": "2026-08-05",
                    "source": "GitHub",
                    "title": "RAG evidence",
                    "citation_id": "occ-rag",
                },
            )
        ]


class _TaskAwareRetriever:
    def __init__(self):
        self.graph_requirement = None

    async def search_with_status(self, query, k=5, where=None, graph_requirement="optional"):
        from rag.retriever.hybrid import ChannelOutcome, HybridSearchOutcome

        self.graph_requirement = graph_requirement
        chunk = RetrievedChunk(
            text="OpenAI responded to an Apple dispute.",
            source="graph" if graph_requirement == "required" else "vector",
            score=0.8,
            metadata={
                "date": "2026-08-05",
                "source": "OpenAI",
                "title": "OpenAI responds to Apple",
                "citation_id": "ATR-20260805-ABC123",
                "occurrence_id": "ATR-20260805-ABC123",
                "local_url": "#2026-08-05/ai-topic-radar/item/ATR-20260805-ABC123",
            },
        )
        unrelated = RetrievedChunk(
            text="Android Studio added multi-agent workflows.",
            source="vector",
            score=0.7,
            metadata={
                "date": "2026-08-04",
                "source": "Google",
                "title": "Android Studio Agents",
                "citation_id": "ATR-20260804-NOISE1",
            },
        )
        channel = ChannelOutcome(status="success", chunks=[chunk, unrelated])
        return HybridSearchOutcome(
            status="ready",
            chunks=[chunk, unrelated],
            channels={"graph": channel, "vector": channel},
        )


class _GraphDriver:
    async def execute_query(self, cypher, **params):
        if "repeated_content_count" in cypher:
            return [{"repeated_content_count": 2, "repeated_observation_count": 5}]
        if "previous_link_count" in cypher:
            return [{"previous_link_count": 3}]
        return [{
            "entity": "OpenAI",
            "observation_count": 7,
            "content_count": 4,
            "date_count": 3,
            "first_observed_date": "2026-08-01",
            "latest_observed_date": "2026-08-05",
            "source_count": 2,
            "category_count": 2,
            "sample_paths": [{
                "entity": "OpenAI", "title": "OpenAI update",
                "content_id": "content-1", "date": "2026-08-05",
                "source": "OpenAI", "category": "模型与技术突破",
            }],
        }]


class _BrokenGraphDriver:
    async def execute_query(self, *_args, **_kwargs):
        raise RuntimeError("neo4j unavailable")


class _RequiredGraphChannelFailureRetriever(_TaskAwareRetriever):
    async def search_with_status(self, query, k=5, where=None, graph_requirement="optional"):
        outcome = await super().search_with_status(
            query, k=k, where=where, graph_requirement=graph_requirement
        )
        from rag.retriever.hybrid import ChannelOutcome, HybridSearchOutcome

        return HybridSearchOutcome(
            status="partial_error",
            chunks=outcome.chunks,
            channels={
                **outcome.channels,
                "graph": ChannelOutcome(status="error", error_code="graph_search_failed"),
            },
            error_code="required_graph_unavailable",
        )


class _StructuredEntityRetriever:
    def __init__(self):
        self.where = None

    async def search(self, query, k=5, where=None):
        self.where = where
        return [
            RetrievedChunk(
                text="A new research collaboration.",
                source="vector",
                score=0.9,
                metadata={
                    "date": "2026-08-05",
                    "source": "Official research blog",
                    "title": "Economic Research Exchange",
                    "citation_id": "ATR-20260805-MATCH1",
                    "entity_ids": ["openai"],
                },
            ),
            RetrievedChunk(
                text="OpenAI is mentioned only as lexical noise.",
                source="vector",
                score=0.8,
                metadata={
                    "date": "2026-08-05",
                    "source": "Another vendor",
                    "title": "OpenAI compatibility layer",
                    "citation_id": "ATR-20260805-NOISE1",
                    "entity_ids": ["google"],
                },
            ),
        ]


class _EventStructuredImportantNewsStore:
    """A shadow view where subject and mention roles are independently labelled."""

    def search(self, *args, **kwargs):
        return []

    def recent(self, limit=100, where=None):
        def item(identity, title, *, subject, mentioned, kind, event_type):
            entity_ids = list(dict.fromkeys([*subject, *mentioned]))
            return {
                "text": title,
                "match_type": "browse",
                "metadata": {
                    "content_type": "topic_candidate",
                    "date": "2026-08-05",
                    "effective_date": "2026-08-05",
                    "publication_date": "2026-08-04",
                    "temporal_confidence": "high",
                    "source": "Calibration",
                    "title": title,
                    "citation_id": identity,
                    "occurrence_id": identity,
                    "content_id": identity,
                    "entity_ids": entity_ids,
                    "subject_entity_ids": subject,
                    "mentioned_entity_ids": mentioned,
                    "content_kind": kind,
                    "event_type": event_type,
                    "local_url": f"#2026-08-05/ai-topic-radar/item/{identity}",
                    "url": f"https://example.com/{identity}",
                    "score": 90,
                    "evidence": title,
                },
            }

        return [
            item(
                "ATR-20260805-MAIN01",
                "OpenAI launches a major economic research exchange",
                subject=["openai"], mentioned=[], kind="news_event", event_type="product_launch",
            ),
            item(
                "ATR-20260805-NOISE1",
                "Open WebUI supports the OpenAI API",
                subject=["open-webui"], mentioned=["openai"],
                kind="project_listing", event_type="compatibility",
            ),
            item(
                "ATR-20260805-NOISE2",
                "How to export ChatGPT conversations",
                subject=["tutorial-author"], mentioned=["openai"],
                kind="tutorial", event_type="how_to",
            ),
            item(
                "ATR-20260805-MAIN02",
                "OpenAI settlement resolves a major employment investigation",
                subject=["openai"], mentioned=[], kind="news_event", event_type="litigation",
            ),
        ][:limit]


class _EventGroupedImportantNewsStore:
    def search(self, *args, **kwargs):
        return []

    def recent(self, limit=100, where=None):
        def item(identity, title, *, group, confidence, source, score):
            return {
                "text": title,
                "match_type": "browse",
                "metadata": {
                    "content_type": "topic_candidate",
                    "date": "2026-08-05",
                    "effective_date": "2026-08-05",
                    "publication_date": "2026-08-04" if confidence == "high" else "",
                    "temporal_confidence": confidence,
                    "source": source,
                    "title": title,
                    "citation_id": identity,
                    "occurrence_id": identity,
                    "content_id": identity,
                    "entity_ids": ["openai"],
                    "subject_entity_ids": ["openai"],
                    "mentioned_entity_ids": [],
                    "content_kind": "news_event",
                    "event_type": "litigation",
                    "event_group_id": group,
                    "local_url": f"#2026-08-05/ai-topic-radar/item/{identity}",
                    "url": f"https://example.com/{identity}",
                    "score": score,
                    "evidence": title,
                },
            }

        return [
            item("OFFICIAL", "OpenAI responds to Apple", group="apple-dispute", confidence="high", source="OpenAI", score=98),
            item("MEDIA", "Media covers the Apple dispute", group="apple-dispute", confidence="high", source="News", score=90),
            item("UNKNOWN-TIME", "OpenAI announces another major event", group="unknown-event", confidence="low", source="OpenAI", score=99),
        ][:limit]


class _TrendStore:
    def search(self, *args, **kwargs):
        raise AssertionError("trend discovery must not use free-text search")

    def recent(self, limit=100, where=None):
        return [
            {
                "text": "OpenAI 发布新的智能体研究。",
                "match_type": "browse",
                "metadata": {
                    "date": "2026-08-05",
                    "source": "OpenAI",
                    "title": "OpenAI Agent Research",
                    "citation_id": "occ-openai-agent",
                    "occurrence_id": "occ-openai-agent",
                    "content_id": "content-openai-agent",
                    "local_url": "#2026-08-05/ai-topic-radar/item/occ-openai-agent",
                    "url": "https://example.com/openai-agent",
                    "score": 96,
                    "category": "AI Agent",
                    "evidence": "OpenAI 发布新的智能体研究。",
                },
            },
            {
                "text": "新的多语言检索模型发布。",
                "match_type": "browse",
                "metadata": {
                    "date": "2026-08-04",
                    "source": "GitHub",
                    "title": "Multilingual Retrieval Model",
                    "citation_id": "occ-multilingual",
                    "occurrence_id": "occ-multilingual",
                    "content_id": "content-multilingual",
                    "local_url": "#2026-08-04/ai-topic-radar/item/occ-multilingual",
                    "url": "https://example.com/multilingual",
                    "score": 90,
                    "category": "RAG",
                    "evidence": "新的多语言检索模型发布。",
                },
            },
        ]


class _CrowdedTrendStore:
    def search(self, *args, **kwargs):
        raise AssertionError("trend discovery must not use free-text search")

    def recent(self, limit=100, where=None):
        def item(identity, content_id, source, category, score):
            return {
                "text": f"{identity} evidence",
                "match_type": "browse",
                "metadata": {
                    "date": "2026-08-05",
                    "source": source,
                    "title": identity,
                    "citation_id": identity,
                    "occurrence_id": identity,
                    "content_id": content_id,
                    "local_url": f"#2026-08-05/ai-topic-radar/item/{identity}",
                    "url": f"https://example.com/{identity}",
                    "score": score,
                    "category": category,
                    "evidence": f"{identity} evidence",
                },
            }

        return [
            item("same-content-first", "content-1", "OpenAI", "AI Agent", 99),
            item("same-content-duplicate", "content-1", "OpenAI", "AI Agent", 98),
            item("same-source-second", "content-2", "OpenAI", "RAG", 97),
            item("same-source-third", "content-3", "OpenAI", "RAG", 96),
            item("other-source", "content-4", "Anthropic", "RAG", 95),
        ]


class _ImportantNewsStore:
    def search(self, *args, **kwargs):
        return []

    def recent(self, limit=100, where=None):
        def item(identity, title, date, score, summary):
            return {
                "text": summary,
                "match_type": "browse",
                "metadata": {
                    "date": date,
                    "effective_date": date,
                    "source": "OpenAI",
                    "title": title,
                    "citation_id": identity,
                    "occurrence_id": identity,
                    "content_id": f"content-{identity}",
                    "entity_ids": ["openai"],
                    "local_url": f"#{date}/ai-topic-radar/item/{identity}",
                    "url": f"https://example.com/{identity}",
                    "score": score,
                    "category": "OpenAI 动态",
                    "summary": summary,
                    "evidence": summary,
                },
            }

        return [
            item(
                "price-detail",
                "Premium Seats Chatgpt Business",
                "2026-08-11",
                99,
                "ChatGPT Business premium seats pricing and seat configuration details.",
            ),
            item(
                "older-major-dispute",
                "OpenAI responds to Apple dispute",
                "2026-07-20",
                98,
                "A major dispute between OpenAI and Apple.",
            ),
            item(
                "responsible-ai-partnership",
                "OpenAI And APA Partner To Advance Responsible AI",
                "2026-08-07",
                96,
                "OpenAI and APA announce a responsible AI partnership.",
            ),
            item(
                "math-advance",
                "Ten Advances In Mathematics",
                "2026-08-02",
                95,
                "OpenAI reports ten advances in mathematical research.",
            ),
            item(
                "leadership-change",
                "OpenAI head of ethics leaves",
                "2026-08-12",
                90,
                "OpenAI's head of ethics leaves less than a year after joining.",
            ),
        ]


class _ImportantNewsCounterexampleStore(_ImportantNewsStore):
    def recent(self, limit=100, where=None):
        items = super().recent(limit=limit, where=where)

        def item(identity, title, summary):
            return {
                "text": summary,
                "match_type": "browse",
                "metadata": {
                    "date": "2026-08-12",
                    "effective_date": "2026-08-12",
                    "source": "OpenAI",
                    "title": title,
                    "citation_id": identity,
                    "occurrence_id": identity,
                    "content_id": f"content-{identity}",
                    "entity_ids": ["openai"],
                    "local_url": f"#2026-08-12/ai-topic-radar/item/{identity}",
                    "url": f"https://example.com/{identity}",
                    "score": 99,
                    "category": "OpenAI 动态",
                    "summary": summary,
                    "evidence": summary,
                },
            }

        return [
            *items,
            item(
                "ordinary-release-notes",
                "Business pricing strategy release notes",
                "Documentation for ordinary seat configuration changes.",
            ),
            item(
                "tutorial",
                "How to configure ChatGPT Business",
                "A tutorial explaining account configuration.",
            ),
            item(
                "major-pricing-restructure",
                "OpenAI restructures enterprise pricing architecture",
                "A company-wide strategic decision affects all enterprise customers and triggers broad industry debate.",
            ),
        ]


class EvidenceRetrievalGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_title_navigates_to_the_canonical_item(self):
        gateway = EvidenceRetrievalGateway(
            retriever=_FailingRetriever(),
            structured_store=_NavigatorStore(),
        )

        bundle = await gateway.retrieve(
            ResearchRequest(
                question="Apple Is Getting This Wrong 讲了什么？",
                latest_corpus_date="2026-08-05",
                limit=5,
            )
        )

        self.assertEqual(bundle.status, "ready")
        self.assertEqual(bundle.task_family, "item_navigation")
        self.assertEqual(bundle.records[0]["occurrence_id"], "occ-apple")
        self.assertEqual(
            bundle.records[0]["local_url"],
            "#2026-08-05/ai-topic-radar/item/occ-apple",
        )
        self.assertEqual(bundle.trace["path"], "navigator")

    async def test_exact_title_navigation_wins_over_an_overbroad_discovery_intent(self):
        """A title containing a named entity must not be demoted to discovery."""
        gateway = EvidenceRetrievalGateway(
            retriever=_FailingRetriever(),
            structured_store=_NavigatorStore(),
        )

        bundle = await gateway.retrieve(
            ResearchRequest(
                question="Introducing The Openai Economic Research Exchange",
                latest_corpus_date="2026-08-05",
                limit=5,
            )
        )

        self.assertEqual(bundle.task_family, "item_navigation")
        self.assertEqual(bundle.records[0]["occurrence_id"], "occ-apple")

    async def test_non_exact_title_falls_back_without_claiming_navigation(self):
        retriever = _EvidenceRetriever()
        gateway = EvidenceRetrievalGateway(
            retriever=retriever,
            structured_store=_NonExactStore(),
        )

        bundle = await gateway.retrieve(ResearchRequest(question="RAG 是什么？"))

        self.assertEqual(bundle.status, "ready")
        self.assertEqual(bundle.task_family, "evidence_research")
        self.assertEqual(bundle.trace["path"], "evidence_search")
        self.assertEqual(retriever.calls, 1)

    async def test_generic_recent_trends_use_structured_candidates(self):
        gateway = EvidenceRetrievalGateway(
            retriever=_FailingRetriever(),
            structured_store=_TrendStore(),
        )

        bundle = await gateway.retrieve(
            ResearchRequest(
                question="最近有什么热门趋势？",
                latest_corpus_date="2026-08-05",
                limit=5,
            )
        )

        self.assertEqual(bundle.status, "ready")
        self.assertEqual(bundle.task_family, "trend_discovery")
        self.assertEqual(bundle.trace["path"], "trend_discovery")
        self.assertEqual(
            [record["citation_id"] for record in bundle.records],
            ["occ-openai-agent", "occ-multilingual"],
        )

    async def test_trend_discovery_deduplicates_and_limits_a_single_source(self):
        gateway = EvidenceRetrievalGateway(
            retriever=_FailingRetriever(),
            structured_store=_CrowdedTrendStore(),
        )

        bundle = await gateway.retrieve(
            ResearchRequest(
                question="最近有什么热门趋势？",
                latest_corpus_date="2026-08-05",
                limit=5,
            )
        )

        citation_ids = [record["citation_id"] for record in bundle.records]
        self.assertIn("same-content-first", citation_ids)
        self.assertNotIn("same-content-duplicate", citation_ids)
        self.assertNotIn("same-source-third", citation_ids)
        self.assertEqual(
            sum(record["source"] == "OpenAI" for record in bundle.records),
            2,
        )

    async def test_company_recent_important_news_uses_news_gate_and_background_tier(self):
        gateway = EvidenceRetrievalGateway(
            retriever=_FailingRetriever(),
            structured_store=_ImportantNewsStore(),
        )

        bundle = await gateway.retrieve(
            ResearchRequest(
                question="OpenAI 最近有哪些重要动态？",
                latest_corpus_date="2026-08-12",
                limit=5,
            )
        )

        self.assertEqual(bundle.task_family, "trend_discovery")
        self.assertEqual(bundle.trace["path"], "trend_discovery")
        self.assertEqual(
            {record["citation_id"] for record in bundle.records},
            {"leadership-change", "responsible-ai-partnership", "math-advance"},
        )
        self.assertEqual(
            [record["citation_id"] for record in bundle.background_records],
            ["older-major-dispute"],
        )
        self.assertIn("price-detail", bundle.trace["excluded_candidate_ids"])

    async def test_news_gate_rejects_routine_content_but_keeps_major_adjustment(self):
        gateway = EvidenceRetrievalGateway(
            retriever=_FailingRetriever(),
            structured_store=_ImportantNewsCounterexampleStore(),
        )

        bundle = await gateway.retrieve(
            ResearchRequest(
                question="OpenAI 最近有什么大事？",
                latest_corpus_date="2026-08-12",
                limit=10,
            )
        )

        main_ids = {record["citation_id"] for record in bundle.records}
        self.assertIn("major-pricing-restructure", main_ids)
        self.assertNotIn("ordinary-release-notes", main_ids)
        self.assertNotIn("tutorial", main_ids)
        self.assertIn("ordinary-release-notes", bundle.trace["excluded_candidate_ids"])
        self.assertIn("tutorial", bundle.trace["excluded_candidate_ids"])

    async def test_important_news_uses_event_subject_not_incidental_mentions(self):
        gateway = EvidenceRetrievalGateway(
            retriever=_FailingRetriever(),
            structured_store=_EventStructuredImportantNewsStore(),
        )

        bundle = await gateway.retrieve(
            ResearchRequest(
                question="OpenAI 最近有哪些重要动态？",
                latest_corpus_date="2026-08-05",
                limit=10,
            )
        )

        self.assertEqual(
            [record["citation_id"] for record in bundle.records],
            ["ATR-20260805-MAIN01", "ATR-20260805-MAIN02"],
        )
        self.assertEqual(
            set(bundle.trace["excluded_candidate_ids"]),
            {"ATR-20260805-NOISE1", "ATR-20260805-NOISE2"},
        )
        self.assertEqual(bundle.trace["entity_filter_mode"], "event_subject")

    async def test_important_news_collapses_event_sources_and_quarantines_unverified_time(self):
        gateway = EvidenceRetrievalGateway(
            retriever=_FailingRetriever(),
            structured_store=_EventGroupedImportantNewsStore(),
        )

        bundle = await gateway.retrieve(ResearchRequest(
            question="OpenAI 最近有哪些重要动态？",
            latest_corpus_date="2026-08-05",
            limit=10,
        ))

        self.assertEqual([row["citation_id"] for row in bundle.records], ["OFFICIAL"])
        self.assertEqual(
            [row["citation_id"] for row in bundle.unverified_records],
            ["UNKNOWN-TIME"],
        )
        self.assertEqual(bundle.trace["merged_event_sources"], {
            "apple-dispute": ["OFFICIAL", "MEDIA"],
        })

    async def test_timeline_question_requires_observation_graph_and_owns_timeline_contract(self):
        retriever = _TaskAwareRetriever()
        gateway = EvidenceRetrievalGateway(retriever=retriever, graph_driver=_GraphDriver())

        bundle = await gateway.retrieve(
            ResearchRequest(question="OpenAI 的发展历程和变化是什么？")
        )

        self.assertEqual(bundle.task_family, "timeline")
        self.assertEqual(retriever.graph_requirement, "required")
        self.assertEqual(bundle.records[0]["citation_id"], "ATR-20260805-ABC123")
        self.assertEqual(len(bundle.records), 2)
        self.assertEqual(bundle.records[1]["citation_id"], "graph-reasoning/openai")
        self.assertIn("7 条每日观察", bundle.records[1]["excerpt"])
        self.assertEqual(bundle.trace["graph_evidence"]["status"], "ready")

    async def test_relation_question_requires_observation_graph(self):
        retriever = _TaskAwareRetriever()
        gateway = EvidenceRetrievalGateway(retriever=retriever, graph_driver=_GraphDriver())

        bundle = await gateway.retrieve(
            ResearchRequest(question="请分析 OpenAI 与 Apple 的跨日关联")
        )

        self.assertEqual(bundle.task_family, "relation_exploration")
        self.assertEqual(retriever.graph_requirement, "required")
        self.assertEqual([item["citation_id"] for item in bundle.records], [
            "ATR-20260805-ABC123", "graph-reasoning/openai", "graph-reasoning/apple",
            "graph-relation/openai/apple",
        ])
        self.assertEqual(bundle.trace["graph_evidence"]["entity_count"], 2)
        self.assertEqual(bundle.trace["graph_evidence"]["relation_count"], 1)

    async def test_relation_question_fails_closed_when_graph_evidence_provider_breaks(self):
        gateway = EvidenceRetrievalGateway(
            retriever=_TaskAwareRetriever(), graph_driver=_BrokenGraphDriver()
        )

        bundle = await gateway.retrieve(
            ResearchRequest(question="OpenAI 是否跨多个日期和来源反复出现？")
        )

        self.assertEqual(bundle.status, "partial_error")
        self.assertEqual(bundle.error_code, "required_graph_evidence_unavailable")
        self.assertEqual(bundle.trace["graph_evidence"]["status"], "error")

    async def test_graph_aggregate_recovers_required_graph_channel_failure(self):
        gateway = EvidenceRetrievalGateway(
            retriever=_RequiredGraphChannelFailureRetriever(),
            graph_driver=_GraphDriver(),
        )

        bundle = await gateway.retrieve(
            ResearchRequest(question="OpenAI 是否跨多个日期反复出现？")
        )

        self.assertEqual(bundle.status, "degraded")
        self.assertEqual(bundle.error_code, "")
        self.assertEqual(bundle.trace["channel_status"]["graph"], "error")
        self.assertEqual(bundle.trace["graph_evidence"]["status"], "ready")

    async def test_claim_verification_does_not_treat_graph_cooccurrence_as_proof(self):
        retriever = _TaskAwareRetriever()
        gateway = EvidenceRetrievalGateway(retriever=retriever)

        bundle = await gateway.retrieve(
            ResearchRequest(question="请验证 OpenAI 已经取得商业成功的真实性和来源")
        )

        self.assertEqual(bundle.task_family, "claim_verification")
        self.assertNotEqual(retriever.graph_requirement, "required")
        self.assertEqual(len(bundle.records), 1)

    async def test_structured_entity_ids_win_over_incidental_text_matches(self):
        retriever = _StructuredEntityRetriever()
        gateway = EvidenceRetrievalGateway(retriever=retriever)

        bundle = await gateway.retrieve(
            ResearchRequest(
                question="OpenAI 最近有哪些重要动态？",
                latest_corpus_date="2026-08-12",
                limit=5,
            )
        )

        self.assertEqual(
            [record["citation_id"] for record in bundle.records],
            ["ATR-20260805-MATCH1"],
        )
        self.assertEqual(bundle.trace["entity_filter_mode"], "structured")
        self.assertIsNotNone(retriever.where)
        self.assertIn(
            {"effective_date": {"$in": [
                "2026-07-30", "2026-07-31", "2026-08-01", "2026-08-02",
                "2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06",
                "2026-08-07", "2026-08-08", "2026-08-09", "2026-08-10",
                "2026-08-11", "2026-08-12",
            ]}},
            retriever.where["$and"],
        )


if __name__ == "__main__":
    unittest.main()
