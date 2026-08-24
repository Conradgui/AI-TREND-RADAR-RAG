"""Tests for citation extraction from retrieval metadata."""

import asyncio
import unittest
from dataclasses import dataclass, field

from rag.citations import (
    build_citations,
    evidence_insufficient_answer,
    retrieve_citations,
    retrieve_citations_with_status,
)


@dataclass
class FakeChunk:
    text: str
    metadata: dict = field(default_factory=dict)


class CitationTests(unittest.TestCase):
    def test_build_citations_uses_retrieval_metadata(self):
        chunks = [
            FakeChunk(
                text="Claude Code Artifacts\nPreview and share your coding work live as it happens.",
                metadata={
                    "date": "2026-06-21",
                    "source": "Product Hunt",
                    "title": "Claude Code Artifacts",
                    "citation_id": "2026-06-21/topic-pool/0",
                    "url": "https://example.com/claude-code-artifacts",
                    "score": 80,
                    "category": "AI 产品与用户入口",
                    "evidence": "来源：Product Hunt\n发布时间：2026-06-19",
                    "report_date": "2026-06-21",
                    "publication_date": "2026-06-19",
                    "publication_date_source": "legacy_evidence",
                    "effective_date": "2026-06-19",
                    "effective_date_basis": "publication_date",
                },
            )
        ]

        citations = build_citations(chunks)

        self.assertEqual(
            citations,
            [
                {
                    "evidence_type": "internal",
                    "date": "2026-06-21",
                    "source": "Product Hunt",
                    "title": "Claude Code Artifacts",
                    "citation_id": "2026-06-21/topic-pool/0",
                    "excerpt": "来源：Product Hunt\n发布时间：2026-06-19",
                    "url": "https://example.com/claude-code-artifacts",
                    "score": 80,
                    "category": "AI 产品与用户入口",
                    "report_date": "2026-06-21",
                    "publication_date": "2026-06-19",
                    "publication_date_source": "legacy_evidence",
                    "effective_date": "2026-06-19",
                    "effective_date_basis": "publication_date",
                }
            ],
        )

    def test_build_citations_uses_text_excerpt_when_evidence_missing(self):
        chunks = [
            FakeChunk(
                text="A" * 280,
                metadata={
                    "date": "2026-06-21",
                    "source": "ai-topic-radar",
                    "title": "ai-topic-radar",
                    "citation_id": "2026-06-21/ai-topic-radar/0",
                },
            )
        ]

        citations = build_citations(chunks, excerpt_chars=120)

        self.assertEqual(citations[0]["excerpt"], "A" * 120)

    def test_build_citations_skips_chunks_without_required_fields(self):
        chunks = [
            FakeChunk(text="Missing date", metadata={"source": "Product Hunt", "title": "Topic", "citation_id": "x"}),
            FakeChunk(text="Missing source", metadata={"date": "2026-06-21", "title": "Topic", "citation_id": "x"}),
        ]

        self.assertEqual(build_citations(chunks), [])

    def test_build_citations_deduplicates_by_citation_id(self):
        chunks = [
            FakeChunk(
                text="First",
                metadata={"date": "2026-06-21", "source": "S", "title": "T", "citation_id": "same"},
            ),
            FakeChunk(
                text="Second",
                metadata={"date": "2026-06-21", "source": "S", "title": "T", "citation_id": "same"},
            ),
        ]

        self.assertEqual(len(build_citations(chunks)), 1)

    def test_build_citations_deduplicates_repeated_topic_title_source_and_url(self):
        chunks = [
            FakeChunk(
                text="First graphify evidence",
                metadata={
                    "date": "2026-06-19",
                    "source": "GitHub Search:rag",
                    "title": "safishamsi/graphify",
                    "citation_id": "2026-06-19/topic-pool/19",
                    "url": "https://github.com/safishamsi/graphify",
                },
            ),
            FakeChunk(
                text="Repeated graphify evidence",
                metadata={
                    "date": "2026-06-20",
                    "source": "GitHub Search:rag",
                    "title": "safishamsi/graphify",
                    "citation_id": "2026-06-20/topic-pool/13",
                    "url": "https://github.com/safishamsi/graphify",
                },
            ),
        ]

        citations = build_citations(chunks, max_citations=5)

        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["citation_id"], "2026-06-19/topic-pool/19")

    def test_source_cap_is_explicit_not_global(self):
        chunks = [
            FakeChunk(
                text=f"Evidence {index}",
                metadata={
                    "date": "2026-08-05",
                    "source": "OpenAI",
                    "title": f"Release {index}",
                    "citation_id": f"release-{index}",
                },
            )
            for index in range(3)
        ]

        self.assertEqual(len(build_citations(chunks)), 3)
        self.assertEqual(len(build_citations(chunks, source_cap=2)), 2)

    def test_evidence_insufficient_answer_names_current_boundary(self):
        answer = evidence_insufficient_answer("最近 RAG 有什么新动向？")

        self.assertIn("当前 AI Trend Radar RAG 知识库", answer)
        self.assertIn("最近 RAG 有什么新动向？", answer)


class RetrieveCitationTests(unittest.IsolatedAsyncioTestCase):
    async def test_structured_retrieval_distinguishes_ready_empty_error_and_timeout(self):
        class ReadyRetriever:
            async def search(self, query, k=5, where=None):
                return [FakeChunk(
                    text="Evidence",
                    metadata={
                        "date": "2026-08-06",
                        "source": "OpenAI",
                        "title": "Release",
                        "citation_id": "release-1",
                    },
                )]

        class EmptyRetriever:
            async def search(self, query, k=5, where=None):
                return []

        class FailingRetriever:
            async def search(self, query, k=5, where=None):
                raise RuntimeError("retriever down")

        class TimeoutRetriever:
            async def search(self, query, k=5, where=None):
                raise asyncio.TimeoutError

        ready = await retrieve_citations_with_status(ReadyRetriever(), "OpenAI")
        empty = await retrieve_citations_with_status(EmptyRetriever(), "OpenAI")
        error = await retrieve_citations_with_status(FailingRetriever(), "OpenAI")
        timeout = await retrieve_citations_with_status(TimeoutRetriever(), "OpenAI")

        self.assertEqual(ready.status, "ready")
        self.assertEqual(len(ready.citations), 1)
        self.assertEqual(empty.status, "empty")
        self.assertEqual(error.status, "error")
        self.assertEqual(error.error_code, "RuntimeError")
        self.assertEqual(timeout.status, "timeout")

    async def test_retrieve_citations_uses_retriever_results(self):
        class FakeRetriever:
            async def search(self, query, k=5, where=None):
                self.query = query
                self.k = k
                self.where = where
                return [
                    FakeChunk(
                        text="Evidence text",
                        metadata={
                            "date": "2026-06-21",
                            "source": "Product Hunt",
                            "title": "Claude Code Artifacts",
                            "citation_id": "2026-06-21/topic-pool/0",
                        },
                    )
                ]

        retriever = FakeRetriever()

        where = {"source": "Product Hunt"}
        citations = await retrieve_citations(retriever, "Claude 最近有什么动态？", k=3, where=where)

        self.assertEqual(retriever.query, "Claude 最近有什么动态？")
        self.assertEqual(retriever.k, 3)
        self.assertEqual(retriever.where, where)
        self.assertEqual(citations[0]["citation_id"], "2026-06-21/topic-pool/0")

    async def test_retrieve_citations_returns_empty_when_retriever_fails(self):
        class FailingRetriever:
            async def search(self, query, k=5):
                raise RuntimeError("retriever down")

        self.assertEqual(await retrieve_citations(FailingRetriever(), "RAG"), [])

    async def test_recent_retrieval_expands_candidates_and_prioritizes_fresh_evidence(self):
        class FakeRetriever:
            async def search(self, query, k=5, where=None):
                self.k = k
                return [
                    FakeChunk(
                        text="Older but top-ranked evidence",
                        metadata={
                            "date": "2026-08-05",
                            "effective_date": "2023-07-23",
                            "source": "Source A",
                            "title": "Older trend",
                            "citation_id": "2026-07-23/topic-pool/0",
                        },
                    ),
                    FakeChunk(
                        text="Fresh evidence from the latest corpus date",
                        metadata={
                            "date": "2026-08-04",
                            "effective_date": "2026-08-04",
                            "source": "Source B",
                            "title": "Fresh trend",
                            "citation_id": "2026-08-05/topic-pool/0",
                        },
                    ),
                ]

        retriever = FakeRetriever()
        citations = await retrieve_citations(
            retriever,
            "最近有什么热门趋势？",
            k=10,
            prefer_recent=True,
            latest_date="2026-08-05",
        )

        self.assertEqual(retriever.k, 30)
        self.assertEqual(citations[0]["date"], "2026-08-04")
        self.assertEqual(citations[0]["effective_date"], "2026-08-04")
        self.assertEqual(citations[0]["title"], "Fresh trend")


if __name__ == "__main__":
    unittest.main()
