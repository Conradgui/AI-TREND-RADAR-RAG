"""Tests for ingestion pipeline — chunk_text and topic pool normalization."""

import unittest
from unittest.mock import patch

from rag.ingest import (
    build_report_chunk_metadata,
    build_topic_candidate_chunks,
    chunk_text,
    infer_source_family,
    ingest_vector_chunks_for_date,
    ingest_all_vector_chunks,
    select_ingestion_dates,
    normalize_topic_pool,
)


class IngestionDateSelectionTests(unittest.TestCase):
    @patch("rag.ingest._find_digest_dates", return_value=["2026-08-03", "2026-08-04", "2026-08-05"])
    def test_selects_only_requested_existing_dates_without_reordering_the_callers_priority(self, _find_dates):
        self.assertEqual(
            select_ingestion_dates(["2026-08-05", "2026-08-04", "2026-08-05"]),
            ["2026-08-05", "2026-08-04"],
        )

    @patch("rag.ingest._find_digest_dates", return_value=["2026-08-05"])
    def test_rejects_missing_or_malformed_dates(self, _find_dates):
        with self.assertRaisesRegex(ValueError, "Invalid digest date"):
            select_ingestion_dates(["latest"])
        with self.assertRaisesRegex(ValueError, "not found locally"):
            select_ingestion_dates(["2026-08-04"])


class ChunkTextTests(unittest.TestCase):
    def test_chunk_text_empty(self):
        self.assertEqual(chunk_text(""), [])
        self.assertEqual(chunk_text("   "), [])
        self.assertEqual(chunk_text(None), [])

    def test_chunk_text_short(self):
        text = "这是一个足够长的短文本内容，用于验证短报告仍然会被保留为一个分块。"
        result = chunk_text(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)

    def test_chunk_text_sections(self):
        text = (
            "# 标题\n这里是第一段足够长的内容，用于验证标题部分可以形成一个分块。\n\n"
            "## 章节\n这里是第二段足够长的内容，用于验证章节部分可以形成另一个分块。"
        )
        chunks = chunk_text(text)
        self.assertGreaterEqual(len(chunks), 2)

    def test_chunk_text_long_paragraph(self):
        text = "段" * 2000
        chunks = chunk_text(text, chunk_size=500)
        self.assertGreaterEqual(len(chunks), 3)
        self.assertTrue(all(len(c) > 20 for c in chunks))

    def test_chunk_text_overlap(self):
        text = "A" * 1500
        chunks = chunk_text(text, chunk_size=500, overlap=100)
        self.assertGreaterEqual(len(chunks), 2)

    def test_chunk_text_invalid_params(self):
        with self.assertRaisesRegex(ValueError, "chunk_size must be > overlap"):
            chunk_text("test", chunk_size=100, overlap=200)

    def test_chunk_text_filters_short(self):
        text = "好\n\n## 标题\n\n这是一段足够长的内容用于测试分块功能是否会正确保留"
        chunks = chunk_text(text)
        self.assertTrue(all(len(c) > 20 for c in chunks))


class TopicPoolNormalizationTests(unittest.TestCase):
    def test_normalize_topic_pool_uses_candidates_and_adds_date(self):
        pool = {
            "candidates": [
                {"title": "Claude Code Artifacts", "source": "Product Hunt"},
            ],
            "topics": [
                {"title": "Legacy Topic"},
            ],
        }

        normalized = normalize_topic_pool(pool, "2026-06-21")

        self.assertEqual(
            normalized["candidates"],
            [{"title": "Claude Code Artifacts", "source": "Product Hunt", "date": "2026-06-21"}],
        )

    def test_normalize_topic_pool_falls_back_to_legacy_topics(self):
        pool = {
            "topics": [
                {"topic": "Agentic RAG", "source": "Legacy"},
            ],
        }

        normalized = normalize_topic_pool(pool, "2026-06-20")

        self.assertEqual(
            normalized["candidates"],
            [{"topic": "Agentic RAG", "source": "Legacy", "date": "2026-06-20"}],
        )

    def test_normalize_topic_pool_handles_empty_or_malformed_pool(self):
        self.assertEqual(normalize_topic_pool(None, "2026-06-19"), {"candidates": []})
        self.assertEqual(normalize_topic_pool({"candidates": "bad"}, "2026-06-19"), {"candidates": []})


class CitationReadyIngestionTests(unittest.TestCase):
    def test_infer_source_family_normalizes_github_variants(self):
        self.assertEqual(infer_source_family("GitHub Search:rag"), "GitHub")
        self.assertEqual(infer_source_family("GitHub Trending"), "GitHub")
        self.assertEqual(infer_source_family("Product Hunt"), "Product Hunt")
        self.assertEqual(infer_source_family("Anthropic (Claude)"), "Anthropic")
        self.assertEqual(infer_source_family("Hacker News"), "")

    def test_build_report_chunk_metadata_contains_citation_fields(self):
        metadata = build_report_chunk_metadata("2026-06-21", "ai-topic-radar", 3)

        self.assertEqual(metadata["content_type"], "report_chunk")
        self.assertEqual(metadata["date"], "2026-06-21")
        self.assertEqual(metadata["report_type"], "ai-topic-radar")
        self.assertEqual(metadata["source"], "ai-topic-radar")
        self.assertEqual(metadata["title"], "ai-topic-radar")
        self.assertEqual(metadata["chunk_index"], 3)
        self.assertEqual(metadata["citation_id"], "2026-06-21/ai-topic-radar/3")

    def test_build_topic_candidate_chunks_contains_text_and_metadata_for_citation(self):
        topic_pool = {
            "candidates": [
                {
                    "title": "Claude Code Artifacts",
                    "summary": "Preview and share your coding work live as it happens",
                    "recommendedTopic": "Claude Code Artifacts 为什么值得关注？",
                    "url": "https://example.com/claude-code-artifacts",
                    "source": "Product Hunt",
                    "category": "AI 产品与用户入口",
                    "score": 80,
                    "action": "深挖",
                    "reason": "值得优先深挖",
                    "evidence": ["来源：Product Hunt", "发布时间：2026-06-19"],
                    "tags": ["Developer Tools", "Artificial Intelligence"],
                }
            ]
        }

        chunks, metadatas, ids = build_topic_candidate_chunks(topic_pool, "2026-06-21")

        self.assertEqual(ids, ["2026-06-21/topic-pool/0"])
        self.assertIn("Claude Code Artifacts", chunks[0])
        self.assertIn("值得优先深挖", chunks[0])
        self.assertEqual(metadatas[0]["content_type"], "topic_candidate")
        self.assertEqual(metadatas[0]["date"], "2026-06-21")
        self.assertEqual(metadatas[0]["source"], "Product Hunt")
        self.assertEqual(metadatas[0]["source_family"], "Product Hunt")
        self.assertEqual(metadatas[0]["title"], "Claude Code Artifacts")
        self.assertEqual(metadatas[0]["url"], "https://example.com/claude-code-artifacts")
        self.assertEqual(metadatas[0]["score"], 80)
        self.assertEqual(metadatas[0]["evidence"], "来源：Product Hunt\n发布时间：2026-06-19")
        self.assertEqual(metadatas[0]["tags"], "Developer Tools, Artificial Intelligence")

    def test_build_topic_candidate_chunks_skips_candidate_without_title(self):
        chunks, metadatas, ids = build_topic_candidate_chunks({"candidates": [{"summary": "missing title"}]}, "2026-06-21")

        self.assertEqual(chunks, [])
        self.assertEqual(metadatas, [])
        self.assertEqual(ids, [])

    def test_ingest_vector_chunks_for_date_replaces_existing_date_chunks(self):
        class FakeVectorStore:
            def __init__(self):
                self.deleted_dates = []
                self.added = []

            def delete_by_date(self, date):
                self.deleted_dates.append(date)

            def add_chunks(self, chunks, metadatas, ids):
                self.added.append((chunks, metadatas, ids))

        store = FakeVectorStore()
        reports = {
            "ai-topic-radar": "# 今日 Top 深挖选题\n这里是一段足够长的报告内容，用于验证报告 chunk 写入。"
        }
        topic_pool = {
            "candidates": [
                {
                    "title": "Claude Code Artifacts",
                    "summary": "Preview and share coding work",
                    "source": "Product Hunt",
                }
            ]
        }

        chunk_count = ingest_vector_chunks_for_date(store, "2026-06-21", topic_pool, reports)

        self.assertEqual(store.deleted_dates, ["2026-06-21"])
        self.assertEqual(chunk_count, 2)
        self.assertEqual(len(store.added), 2)
        self.assertEqual(store.added[0][2], ["2026-06-21/ai-topic-radar/0"])
        self.assertEqual(store.added[1][2], ["2026-06-21/topic-pool/0"])

    def test_ingest_all_vector_chunks_does_not_require_neo4j(self):
        import json
        import tempfile
        from pathlib import Path

        class FakeVectorStore:
            def __init__(self):
                self.deleted_dates = []
                self.added = []

            def delete_by_date(self, date):
                self.deleted_dates.append(date)

            def add_chunks(self, chunks, metadatas, ids):
                self.added.append((chunks, metadatas, ids))

            def count(self):
                return sum(len(item[0]) for item in self.added)

        with tempfile.TemporaryDirectory() as tmp:
            date_dir = Path(tmp) / "2026-06-21"
            date_dir.mkdir()
            (date_dir / "ai-topic-radar.md").write_text(
                "# 今日 Top 深挖选题\n这里是一段足够长的报告内容，用于验证向量路径可以独立写入。",
                encoding="utf-8",
            )
            (date_dir / "topic-pool.json").write_text(
                json.dumps({"candidates": [{"title": "Claude Code", "source": "Product Hunt"}]}),
                encoding="utf-8",
            )

            store = FakeVectorStore()
            count = ingest_all_vector_chunks(store, digests_dir=tmp)

            self.assertEqual(count, 2)
            self.assertEqual(store.deleted_dates, ["2026-06-21"])


if __name__ == "__main__":
    unittest.main()
