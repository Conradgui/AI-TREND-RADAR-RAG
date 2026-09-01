import unittest

from rag.graph_readiness import GraphReadiness
from rag.query_understanding_v2 import understand_query_v2
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


class _DescriptorNavigationStore:
    def search(self, query, k=5, where=None):
        return [
            {
                "text": "A uniquely matching project description.",
                "match_type": "descriptor",
                "lexical_score": 0.2,
                "metadata": {
                    "content_type": "topic_candidate",
                    "date": "2026-08-21",
                    "source": "GitHub",
                    "title": "Graphify-Labs/graphify",
                    "citation_id": "occ-graphify",
                    "occurrence_id": "occ-graphify",
                    "content_id": "content-graphify",
                    "local_url": "#2026-08-21/ai-topic-radar/item/occ-graphify",
                    "url": "https://example.com/graphify",
                    "evidence": "A uniquely matching project description.",
                },
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


class _QueryRecordingRetriever(_TaskAwareRetriever):
    async def search_with_status(self, query, **kwargs):
        self.query = query
        self.where = kwargs.get("where")
        return await super().search_with_status(query, **kwargs)


class _TimelineEventStore:
    """Local lexical hit that hybrid fusion must not discard for a direct timeline."""

    def search(self, _query, k=5, where=None):
        self.k = k
        self.where = where
        return [{
            "text": "OpenAI says it will be a public company in 2027 or sooner.",
            "match_type": "entity_event",
            "lexical_score": 0.25,
            "metadata": {
                "content_type": "topic_candidate",
                "date": "2026-08-19",
                "effective_date": "2026-08-19",
                "source": "Hacker News",
                "title": "OpenAI 'will be a public company in 2027' or sooner",
                "citation_id": "ATR-20260820-6EFF79",
                "occurrence_id": "ATR-20260820-6EFF79",
                "content_id": "openai-public-company-2027",
                "local_url": "#2026-08-20/ai-topic-radar/item/ATR-20260820-6EFF79",
                "url": "https://example.com/openai-public-company",
                "evidence": "OpenAI says it will be a public company in 2027 or sooner.",
                "entity_ids": ["openai"],
            },
        }][:k]


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


class _ReadyProbe:
    def __init__(self):
        self.calls = 0

    async def probe(self, level="runtime", **_kwargs):
        self.calls += 1
        return GraphReadiness(
            status="ready", level=level, checked_at=1.0, latency_ms=1.0
        )


class _UnavailableProbe:
    async def probe(self, level="runtime", **_kwargs):
        return GraphReadiness(
            status="unavailable",
            level=level,
            checked_at=1.0,
            latency_ms=1.0,
            error_code="graph_connectivity_failed",
        )


class _CandidateGraphDriver:
    def __init__(self):
        self.content_ids = []

    async def execute_query(self, _cypher, **params):
        self.content_ids = params["content_ids"]
        return [{
            "entities": ["OpenAI"],
            "categories": ["AI Agent", "RAG"],
            "repeated_content_ids": ["content-openai-agent"],
            "previous_link_count": 1,
        }]


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


class _LegacyClaudeImportantNewsStore:
    """Realistic legacy records: entity_ids exist, event-role fields do not."""

    def search(self, *args, **kwargs):
        return []

    def recent(self, limit=100, where=None):
        def item(identity, title, summary, source, score=90):
            return {
                "text": f"{title}\n{summary}",
                "match_type": "browse",
                "metadata": {
                    "content_type": "topic_candidate",
                    "date": "2026-08-20",
                    "effective_date": "2026-08-20",
                    "publication_date": "2026-08-20",
                    "publication_date_source": "upstream_declared",
                    "source": source,
                    "title": title,
                    "summary": summary,
                    "citation_id": identity,
                    "occurrence_id": identity,
                    "content_id": identity,
                    "entity_ids": ["anthropic"],
                    "local_url": f"#2026-08-20/ai-topic-radar/item/{identity}",
                    "url": f"https://example.com/{identity}",
                    "score": score,
                    "evidence": summary,
                },
            }

        return [
            item(
                "ANTHROPIC-OFFICIAL",
                "Anthropic announces a major Claude safety partnership",
                "Anthropic announces a partnership affecting model deployment across enterprises.",
                "Anthropic (Claude)",
                94,
            ),
            item(
                "ANTHROPIC-MEDIA",
                "Anthropic closes a major funding round",
                "The funding changes Anthropic's competitive position.",
                "TechCrunch",
                92,
            ),
            item(
                "ANTHROPIC-REVENUE-A",
                "Anthropic annualized revenue tops $65B before IPO",
                "A report says Anthropic revenue increased before its planned IPO.",
                "Hacker News",
                91,
            ),
            item(
                "ANTHROPIC-REVENUE-B",
                "Anthropic revenue jumps again before IPO",
                "Another source reports Anthropic revenue growth before the IPO.",
                "Tech News",
                89,
            ),
            item(
                "CLAUDE-MEM",
                "thedotmack/claude-mem",
                "A third-party memory project that works with Claude Code, Codex and Gemini.",
                "GitHub Search:rag",
                99,
            ),
            item(
                "CLAUDE-WATERMARK",
                "Claude Watermark Remover",
                "A third-party utility listed on Product Hunt.",
                "Product Hunt",
                98,
            ),
            item(
                "CLAUDE-SETTINGS",
                "How to configure Claude quota settings",
                "A step-by-step guide to ordinary account configuration.",
                "Dev.to",
                97,
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
            item("UNKNOWN-TIME", "OpenAI announces another major event", group="unknown-event", confidence="low", source="Unverified News", score=99),
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


class _RecordingImportantNewsStore(_ImportantNewsStore):
    def recent(self, limit=100, where=None):
        self.where = where
        return super().recent(limit=limit, where=where)


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

    async def test_explicit_navigation_can_accept_one_strong_descriptor_match(self):
        gateway = EvidenceRetrievalGateway(
            retriever=_FailingRetriever(),
            structured_store=_DescriptorNavigationStore(),
        )

        question = "找能把 SQL schema 和配置转成知识图谱的项目"
        bundle = await gateway.retrieve(
            ResearchRequest(
                question=question,
                route_contract=understand_query_v2(question).to_dict(),
            )
        )

        self.assertEqual(bundle.status, "ready")
        self.assertEqual(bundle.records[0]["occurrence_id"], "occ-graphify")

    async def test_named_item_does_not_hijack_an_explicit_comparison_route(self):
        retriever = _EvidenceRetriever()
        gateway = EvidenceRetrievalGateway(
            retriever=retriever,
            structured_store=_NavigatorStore(),
        )
        question = "Graphify 和 claude-mem 在保留和检索上下文上分别做什么？"

        bundle = await gateway.retrieve(
            ResearchRequest(
                question=question,
                route_contract=understand_query_v2(question).to_dict(),
            )
        )

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

        self.assertEqual(bundle.status, "degraded")
        self.assertEqual(bundle.task_family, "trend_discovery")
        self.assertEqual(bundle.trace["path"], "trend_discovery")
        self.assertEqual(bundle.trace["candidate_graph"]["status"], "unavailable")
        self.assertEqual(
            [record["citation_id"] for record in bundle.records],
            ["occ-openai-agent", "occ-multilingual"],
        )

    async def test_trend_clusters_add_graph_evidence_only_for_ranked_candidates(self):
        driver = _CandidateGraphDriver()
        probe = _ReadyProbe()
        gateway = EvidenceRetrievalGateway(
            retriever=_FailingRetriever(),
            structured_store=_TrendStore(),
            graph_driver=driver,
            graph_readiness_probe=probe,
        )

        bundle = await gateway.retrieve(
            ResearchRequest(
                question="最近有什么热门趋势？",
                latest_corpus_date="2026-08-05",
                limit=5,
            )
        )

        self.assertEqual(
            driver.content_ids,
            ["content-openai-agent", "content-multilingual"],
        )
        self.assertEqual(bundle.trace["execution_policy"]["graph_mode"], "candidate_bounded")
        self.assertEqual(bundle.trace["candidate_graph"]["status"], "ready")
        self.assertEqual(bundle.records[-1]["evidence_type"], "graph")
        self.assertEqual(probe.calls, 1)

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
            {"leadership-change"},
        )
        self.assertEqual(
            {record["citation_id"] for record in bundle.supplementary_records},
            {"responsible-ai-partnership", "math-advance"},
        )
        self.assertEqual(
            [record["citation_id"] for record in bundle.background_records],
            ["older-major-dispute"],
        )
        self.assertIn("price-detail", bundle.trace["excluded_candidate_ids"])

    async def test_concept_scoped_important_news_does_not_reject_every_candidate(self):
        gateway = EvidenceRetrievalGateway(
            retriever=_TaskAwareRetriever(),
            structured_store=_ImportantNewsStore(),
        )
        from rag.query_understanding_v2 import understand_query_v2

        question = "最近一周，AI 编程助手有哪些不同的产品做法？"
        contract = understand_query_v2(question).to_dict()
        contract["subjects"] = ["AI 编程助手"]
        contract["protected_terms"] = ["AI 编程助手"]

        bundle = await gateway.retrieve(ResearchRequest(
            question=question,
            latest_corpus_date="2026-08-12",
            limit=5,
            route_contract=contract,
        ))

        self.assertNotEqual(bundle.status, "empty")
        self.assertGreater(len(bundle.records), 0)
        self.assertEqual(bundle.trace["path"], "evidence_search")

    async def test_timeline_retrieval_expands_bilingual_event_aliases(self):
        retriever = _QueryRecordingRetriever()
        gateway = EvidenceRetrievalGateway(retriever=retriever)
        contract = understand_query_v2(
            "按时间线梳理与 OpenAI 潜在上市相关的两条直接报道"
        ).to_dict()
        contract["primary_task_family"] = "temporal_relation_exploration"
        contract["answer_mode"] = "timeline"
        contract["subjects"] = ["OpenAI"]
        contract["protected_terms"] = ["上市"]

        await gateway.retrieve(ResearchRequest(
            question="按时间线梳理与 OpenAI 潜在上市相关的两条直接报道",
            route_contract=contract,
        ))

        self.assertIn("上市", retriever.query)
        self.assertIn("ipo", retriever.query.casefold())

    async def test_direct_report_timeline_does_not_require_graph_before_returning_evidence(self):
        retriever = _TaskAwareRetriever()
        gateway = EvidenceRetrievalGateway(retriever=retriever, graph_driver=_GraphDriver())
        contract = understand_query_v2(
            "按时间线梳理与 OpenAI 潜在上市相关的两条直接报道"
        ).to_dict()

        bundle = await gateway.retrieve(ResearchRequest(
            question="按时间线梳理与 OpenAI 潜在上市相关的两条直接报道",
            route_contract=contract,
        ))

        self.assertEqual(retriever.graph_requirement, "disabled")
        self.assertEqual(bundle.trace["graph_evidence"]["status"], "not_required")

    async def test_important_news_passes_an_explicit_cutoff_to_structured_candidates(self):
        store = _RecordingImportantNewsStore()
        question = "截至 8 月 21 日，过去一周 OpenAI 有哪些值得关注的业务或产品动态？"
        contract = understand_query_v2(question).to_dict()
        gateway = EvidenceRetrievalGateway(
            retriever=_FailingRetriever(), structured_store=store
        )

        await gateway.retrieve(ResearchRequest(
            question=question,
            latest_corpus_date="2026-08-24",
            route_contract=contract,
        ))

        self.assertEqual(store.where, {"$and": [
            {"content_type": "topic_candidate"},
            {"$and": [
                {"effective_date": {"$gte": "2026-08-15"}},
                {"effective_date": {"$lte": "2026-08-21"}},
            ]},
        ]})

    async def test_direct_timeline_preserves_local_event_candidate_lost_by_hybrid_fusion(self):
        store = _TimelineEventStore()
        gateway = EvidenceRetrievalGateway(
            retriever=_TaskAwareRetriever(), structured_store=store
        )
        question = "按时间线梳理与 OpenAI 潜在上市相关的两条直接报道"
        contract = understand_query_v2(question).to_dict()

        bundle = await gateway.retrieve(ResearchRequest(
            question=question,
            route_contract=contract,
            limit=2,
        ))

        self.assertIn(
            "ATR-20260820-6EFF79",
            [record["citation_id"] for record in bundle.records],
        )
        self.assertEqual(bundle.trace["timeline_lexical_candidate_count"], 1)
        self.assertGreaterEqual(store.k, 20)

    async def test_explicit_cutoff_is_applied_before_comparison_retrieval(self):
        adapter = _QueryRecordingRetriever()
        gateway = EvidenceRetrievalGateway(retriever=adapter)
        contract = understand_query_v2(
            "Graphify 和 claude-mem 截至 2026-08-21 分别做什么？"
        ).to_dict()

        await gateway.retrieve(ResearchRequest(
            question="Graphify 和 claude-mem 截至 2026-08-21 分别做什么？",
            route_contract=contract,
            latest_corpus_date="2026-08-24",
        ))

        self.assertEqual(adapter.where, {"$and": [
            {"effective_date": {"$gte": "2000-01-01"}},
            {"effective_date": {"$lte": "2026-08-21"}},
        ]})

    async def test_retrieval_hints_widen_query_without_becoming_entity_filters(self):
        retriever = _QueryRecordingRetriever()
        gateway = EvidenceRetrievalGateway(retriever=retriever)
        contract = understand_query_v2(
            "最近 AI 编程助手在跨会话上下文和代码库知识上有哪些做法？"
        ).to_dict()
        contract["subjects"] = ["AI 编程助手"]
        contract["retrieval_hints"] = [
            "persistent context across sessions",
            "codebase knowledge graph",
        ]

        bundle = await gateway.retrieve(ResearchRequest(
            question="最近 AI 编程助手在跨会话上下文和代码库知识上有哪些做法？",
            route_contract=contract,
        ))

        self.assertEqual(bundle.task_family, "evidence_research")
        self.assertIn("persistent context across sessions", retriever.query)
        self.assertIn("codebase knowledge graph", retriever.query)
        self.assertEqual(bundle.trace["entity_filter_mode"], "not_required")

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
            ["ATR-20260805-MAIN02"],
        )
        self.assertEqual(
            [record["citation_id"] for record in bundle.supplementary_records],
            ["ATR-20260805-MAIN01"],
        )
        self.assertEqual(
            set(bundle.trace["excluded_candidate_ids"]),
            {"ATR-20260805-NOISE1", "ATR-20260805-NOISE2"},
        )
        self.assertEqual(bundle.trace["entity_filter_mode"], "event_subject")

    async def test_legacy_important_news_derives_subject_roles_before_filtering(self):
        gateway = EvidenceRetrievalGateway(
            retriever=_FailingRetriever(),
            structured_store=_LegacyClaudeImportantNewsStore(),
        )

        bundle = await gateway.retrieve(
            ResearchRequest(
                question="Claude 最近有哪些重要动态？",
                latest_corpus_date="2026-08-20",
                limit=10,
            )
        )

        self.assertEqual(bundle.records, [])
        self.assertEqual(
            bundle.supplementary_records[0]["citation_id"],
            "ANTHROPIC-OFFICIAL",
        )
        self.assertIn(
            "ANTHROPIC-MEDIA",
            {record["citation_id"] for record in bundle.supplementary_records},
        )
        self.assertTrue(
            {"CLAUDE-MEM", "CLAUDE-WATERMARK", "CLAUDE-SETTINGS"}
            <= set(bundle.trace["excluded_candidate_ids"])
        )
        returned_ids = {
            record["citation_id"]
            for record in [*bundle.records, *bundle.supplementary_records]
        }
        self.assertEqual(
            len(returned_ids & {"ANTHROPIC-REVENUE-A", "ANTHROPIC-REVENUE-B"}),
            1,
        )
        self.assertTrue(bundle.trace["merged_event_sources"])
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

    async def test_required_graph_route_preflights_readiness_and_skips_graph_channel_when_down(self):
        retriever = _TaskAwareRetriever()
        gateway = EvidenceRetrievalGateway(
            retriever=retriever,
            graph_driver=_GraphDriver(),
            graph_readiness_probe=_UnavailableProbe(),
        )

        bundle = await gateway.retrieve(
            ResearchRequest(question="请分析 OpenAI 与 Apple 的跨日关联")
        )

        self.assertEqual(retriever.graph_requirement, "disabled")
        self.assertEqual(bundle.status, "partial_error")
        self.assertEqual(bundle.error_code, "required_graph_evidence_unavailable")
        self.assertEqual(bundle.trace["graph_readiness"]["status"], "unavailable")

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
