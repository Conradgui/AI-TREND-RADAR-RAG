"""Tests for citation extraction from retrieval metadata."""

import unittest
from dataclasses import dataclass, field

from rag.citations import build_citations, evidence_insufficient_answer, retrieve_citations


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

    def test_evidence_insufficient_answer_names_current_boundary(self):
        answer = evidence_insufficient_answer("最近 RAG 有什么新动向？")

        self.assertIn("当前 AI Trend Radar RAG 知识库", answer)
        self.assertIn("最近 RAG 有什么新动向？", answer)


class RetrieveCitationTests(unittest.IsolatedAsyncioTestCase):
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


if __name__ == "__main__":
    unittest.main()
