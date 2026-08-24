"""Tests for ingestion pipeline — chunk_text and topic pool normalization."""

import unittest
from unittest.mock import patch

from rag.ingest import (
    build_runtime_search_documents,
    build_report_chunk_metadata,
    build_topic_candidate_chunks,
    build_search_document_lookup,
    chunk_text,
    infer_source_family,
    ingest_vector_chunks_for_date,
    ingest_all_vector_chunks,
    migrate_atomic_vector_chunks,
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

    def test_runtime_projection_decodes_html_entities_at_the_input_boundary(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            date_dir = Path(temp_dir) / "2026-08-11"
            date_dir.mkdir()
            (date_dir / "topic-pool.json").write_text(
                json.dumps({"candidates": [{
                    "title": "Claude&#x27;s roadmap",
                    "summary": "Research &amp; product",
                    "source": "Anthropic",
                }]}),
                encoding="utf-8",
            )

            document = build_runtime_search_documents(temp_dir)[0]

        self.assertEqual(document["title"], "Claude's roadmap")
        self.assertEqual(document["summary"], "Research & product")

    def test_runtime_projection_preserves_distinct_time_semantics(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            date_dir = Path(temp_dir) / "2026-08-11"
            date_dir.mkdir()
            (date_dir / "topic-pool.json").write_text(
                json.dumps({"candidates": [{
                    "title": "Old article discovered today",
                    "source": "Official",
                    "publishedAt": "2022-02-11T09:30:00Z",
                }]}),
                encoding="utf-8",
            )

            document = build_runtime_search_documents(temp_dir)[0]

        self.assertEqual(document["report_date"], "2026-08-11")
        self.assertEqual(document["publication_date"], "2022-02-11")
        self.assertEqual(document["publication_date_source"], "upstream_declared")
        self.assertEqual(document["observed_at"], "2026-08-11")
        self.assertIsNone(document["ingested_at"])
        self.assertEqual(document["effective_date"], "2022-02-11")
        self.assertEqual(document["effective_date_basis"], "publication_date")


class CitationReadyIngestionTests(unittest.TestCase):
    def test_temporal_activation_gate_rejects_unproven_legacy_publication(self):
        from rag.temporal_semantics import audit_temporal_documents

        report = audit_temporal_documents([{
            "source": "GitHub Search:rag",
            "publication_date": "2026-08-11",
            "publication_date_source": "legacy_evidence",
            "effective_date_basis": "publication_date",
        }])

        self.assertFalse(report["passed"])
        self.assertEqual(report["legacy_promoted_to_publication"], 1)
        self.assertEqual(report["update_only_promoted_to_publication"], 1)

    def test_temporal_activation_gate_accepts_separated_update_and_report_dates(self):
        from rag.temporal_semantics import audit_temporal_documents

        report = audit_temporal_documents([{
            "source": "GitHub Search:rag",
            "report_date": "2026-08-12",
            "publication_date": None,
            "publication_date_source": "unknown",
            "source_updated_at": "2026-08-11",
            "effective_date": "2026-08-12",
            "effective_date_basis": "report_date_fallback",
        }])

        self.assertTrue(report["passed"])

    def test_temporal_activation_gate_rejects_unauthorized_legacy_contract_source(self):
        from rag.temporal_semantics import audit_temporal_documents

        report = audit_temporal_documents([{
            "source": "OpenAI",
            "publication_date": "2026-08-11",
            "publication_date_source": "legacy_adapter_contract",
            "source_updated_at": None,
            "effective_date": "2026-08-11",
            "effective_date_basis": "publication_date",
        }])

        self.assertFalse(report["passed"])
        self.assertEqual(report["unauthorized_legacy_publication_source"], 1)

    def test_temporal_activation_gate_rejects_invalid_dates_and_inconsistent_roles(self):
        from rag.temporal_semantics import audit_temporal_documents

        report = audit_temporal_documents([{
            "source": "Hacker News",
            "publication_date": "+058568-10",
            "publication_date_source": "legacy_adapter_contract",
            "source_updated_at": "not-a-date",
            "effective_date": "2026-08-12",
            "effective_date_basis": "report_date_fallback",
        }])

        self.assertFalse(report["passed"])
        self.assertEqual(report["invalid_publication_date"], 1)
        self.assertEqual(report["invalid_source_updated_at"], 1)
        self.assertEqual(report["inconsistent_temporal_roles"], 1)

    def test_temporal_activation_gate_rejects_publication_without_provenance(self):
        from rag.temporal_semantics import audit_temporal_documents

        report = audit_temporal_documents([{
            "source": "Hacker News",
            "publication_date": "2026-08-11",
            "publication_date_source": "unknown",
            "source_updated_at": None,
            "effective_date": "2026-08-11",
            "effective_date_basis": "publication_date",
        }])

        self.assertFalse(report["passed"])
        self.assertEqual(report["inconsistent_temporal_roles"], 1)

    def test_temporal_activation_gate_rejects_invalid_report_date(self):
        from rag.temporal_semantics import audit_temporal_documents

        report = audit_temporal_documents([{
            "source": "OpenAI",
            "report_date": "+058568-10",
            "publication_date": None,
            "publication_date_source": "unknown",
            "source_updated_at": None,
            "effective_date": "+058568-10",
            "effective_date_basis": "report_date_fallback",
        }])

        self.assertFalse(report["passed"])
        self.assertEqual(report["invalid_report_date"], 1)

    def test_temporal_activation_gate_rejects_fallback_effective_date_mismatch(self):
        from rag.temporal_semantics import audit_temporal_documents

        report = audit_temporal_documents([{
            "source": "OpenAI",
            "report_date": "2026-08-12",
            "publication_date": None,
            "publication_date_source": "unknown",
            "source_updated_at": None,
            "effective_date": "2020-01-01",
            "effective_date_basis": "report_date_fallback",
        }])

        self.assertFalse(report["passed"])
        self.assertEqual(report["inconsistent_temporal_roles"], 1)

    def test_runtime_projection_recovers_legacy_publication_event_semantics(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            date_dir = Path(temp_dir) / "2026-08-12"
            date_dir.mkdir()
            (date_dir / "topic-pool.json").write_text(
                json.dumps({"candidates": [{
                    "title": "A published Hacker News item",
                    "source": "Hacker News",
                    "evidence": ["发布时间：2026-08-11"],
                }]}),
                encoding="utf-8",
            )

            document = build_runtime_search_documents(temp_dir)[0]

        self.assertEqual(document["publication_date"], "2026-08-11")
        self.assertEqual(document["publication_date_source"], "legacy_adapter_contract")
        self.assertIsNone(document["source_updated_at"])
        self.assertEqual(document["effective_date_basis"], "publication_date")

    def test_runtime_projection_keeps_legacy_official_sitemap_date_unverified(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            date_dir = Path(temp_dir) / "2026-08-12"
            date_dir.mkdir()
            (date_dir / "topic-pool.json").write_text(
                json.dumps({"candidates": [{
                    "title": "An official site item",
                    "source": "OpenAI",
                    "evidence": ["发布时间：2026-08-11"],
                }]}),
                encoding="utf-8",
            )

            document = build_runtime_search_documents(temp_dir)[0]

        self.assertIsNone(document["publication_date"])
        self.assertEqual(document["publication_date_source"], "unknown")
        self.assertIsNone(document["source_updated_at"])

    def test_fast_migration_reuses_candidate_embedding_and_drops_report_chunk(self):
        import numpy as np

        class Source:
            def export_records(self):
                return {
                    "documents": ["candidate", "report"],
                    "metadatas": [
                        {"content_type": "topic_candidate", "date": "2026-08-05", "title": "OpenAI Research", "source": "OpenAI"},
                        {"content_type": "report_chunk", "date": "2026-08-05", "title": "ai-topic-radar"},
                    ],
                    "embeddings": np.array([[0.1, 0.2], [0.3, 0.4]]),
                }

        class Target:
            def __init__(self):
                self.added = []

            def add_preembedded(self, chunks, metadatas, ids, embeddings):
                self.added.append((chunks, metadatas, ids, embeddings))

        target = Target()
        count = migrate_atomic_vector_chunks(
            Source(),
            target,
            [{
                "date": "2026-08-05",
                "title": "OpenAI Research",
                "source": "OpenAI",
                "occurrence_id": "ATR-20260805-A1B2C3",
                "daily_item_id": "ATR-20260805-A1B2C3",
                "content_id": "content-openai",
                "local_url": "#2026-08-05/ai-topic-radar/item/ATR-20260805-A1B2C3",
                "report_date": "2026-08-05",
                "publication_date": "2022-02-11",
                "publication_date_source": "upstream_declared",
                "observed_at": "2026-08-05",
                "effective_date": "2022-02-11",
                "effective_date_basis": "publication_date",
            }],
        )

        self.assertEqual(count, 1)
        self.assertEqual(target.added[0][2], ["ATR-20260805-A1B2C3"])
        self.assertEqual(target.added[0][3], [[0.1, 0.2]])
        migrated_metadata = target.added[0][1][0]
        self.assertEqual(migrated_metadata["report_date"], "2026-08-05")
        self.assertEqual(migrated_metadata["publication_date"], "2022-02-11")
        self.assertEqual(migrated_metadata["effective_date"], "2022-02-11")

    def test_fast_migration_reports_coverage_before_publication(self):
        import numpy as np

        class Source:
            def export_records(self):
                return {
                    "documents": ["mapped", "unmapped", "report"],
                    "metadatas": [
                        {"content_type": "topic_candidate", "date": "2026-08-05", "title": "OpenAI Research", "source": "OpenAI"},
                        {"content_type": "topic_candidate", "date": "2026-08-04", "title": "Legacy only", "source": "Legacy"},
                        {"content_type": "report_chunk", "date": "2026-08-05", "title": "daily"},
                    ],
                    "embeddings": np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]),
                }

        class Target:
            def add_preembedded(self, *args): pass
            def add_chunks(self, *args): pass

        report = {}
        count = migrate_atomic_vector_chunks(
            Source(),
            Target(),
            [{
                "date": "2026-08-05",
                "title": "OpenAI Research",
                "source": "OpenAI",
                "occurrence_id": "ATR-20260805-A1B2C3",
                "daily_item_id": "ATR-20260805-A1B2C3",
                "content_id": "content-openai",
                "entities": ["OpenAI"],
            }],
            report_sink=report,
        )

        self.assertEqual(count, 1)
        self.assertEqual(report["source_record_count"], 3)
        self.assertEqual(report["source_atomic_count"], 2)
        self.assertEqual(report["reused_embedding_count"], 1)
        self.assertEqual(report["unmapped_source_atomic_count"], 1)
        self.assertEqual(report["target_document_count"], 1)
        self.assertEqual(report["output_record_count"], 1)
        self.assertEqual(report["atr_id_coverage"], 1.0)
        self.assertEqual(report["entity_id_coverage"], 1.0)
        self.assertEqual(report["per_date_output_counts"], {"2026-08-05": 1})
        self.assertEqual(report["unmapped_source_records"][0]["title"], "Legacy only")

    def test_fast_migration_does_not_count_empty_target_as_written(self):
        import numpy as np

        class Source:
            def export_records(self):
                return {"documents": [], "metadatas": [], "embeddings": np.array([])}

        class Target:
            def add_preembedded(self, *args): pass
            def add_chunks(self, *args): raise AssertionError("empty document must not be embedded")

        report = {}
        count = migrate_atomic_vector_chunks(
            Source(),
            Target(),
            [{"date": "2026-08-05", "occurrence_id": "ATR-20260805-EMPTY1"}],
            report_sink=report,
        )

        self.assertEqual(count, 0)
        self.assertEqual(report["target_document_count"], 1)
        self.assertEqual(report["output_record_count"], 0)

    def test_fast_migration_stops_before_full_reembedding_when_nothing_can_be_reused(self):
        import numpy as np

        class Source:
            def export_records(self):
                return {
                    "documents": ["unmappable candidate"],
                    "metadatas": [{
                        "content_type": "topic_candidate",
                        "date": "2026-08-05",
                        "title": "Legacy title",
                        "source": "Legacy source",
                    }],
                    "embeddings": np.array([[0.1, 0.2]]),
                }

        class Target:
            def add_preembedded(self, *args, **kwargs):
                raise AssertionError("no reused embedding should be written")

            def add_chunks(self, *args, **kwargs):
                raise AssertionError("full re-embedding must not start silently")

        with self.assertRaisesRegex(RuntimeError, "could not be mapped"):
            migrate_atomic_vector_chunks(
                Source(),
                Target(),
                [{
                    "date": "2026-08-05",
                    "title": "New title",
                    "source": "New source",
                    "occurrence_id": "ATR-20260805-A1B2C3",
                    "daily_item_id": "ATR-20260805-A1B2C3",
                }],
            )

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
        self.assertEqual(metadatas[0]["report_date"], "2026-06-21")
        self.assertEqual(metadatas[0]["publication_date"], "2026-06-19")
        self.assertEqual(metadatas[0]["publication_date_source"], "legacy_adapter_contract")
        self.assertEqual(metadatas[0]["effective_date"], "2026-06-19")
        self.assertEqual(metadatas[0]["effective_date_basis"], "publication_date")
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

    def test_build_topic_candidate_chunks_carries_canonical_entity_ids(self):
        topic_pool = {
            "candidates": [{
                "title": "Economic Research Exchange",
                "summary": "A new research collaboration.",
                "source": "OpenAI",
                "entities": ["Open AI"],
            }]
        }

        _chunks, metadatas, _ids = build_topic_candidate_chunks(topic_pool, "2026-08-05")

        assert metadatas[0]["entity_ids"] == "openai"

    def test_search_document_identity_replaces_array_index_citation(self):
        topic_pool = {
            "candidates": [
                {
                    "title": "Open AI Economic Research Exchange",
                    "summary": "Official research exchange",
                    "url": "https://openai.com/index/economic-research-exchange/",
                    "source": "OpenAI",
                }
            ]
        }
        lookup = build_search_document_lookup(
            [
                {
                    "date": "2026-08-05",
                    "title": "Open AI Economic Research Exchange",
                    "source": "OpenAI",
                    "external_url": "https://openai.com/index/economic-research-exchange/",
                    "content_id": "content-stable",
                    "occurrence_id": "occurrence-stable",
                    "local_url": "#2026-08-05/ai-topic-radar/item/occurrence-stable",
                }
            ]
        )

        _chunks, metadatas, ids = build_topic_candidate_chunks(
            topic_pool,
            "2026-08-05",
            search_document_lookup=lookup,
        )

        self.assertEqual(ids, ["occurrence-stable"])
        self.assertEqual(metadatas[0]["citation_id"], "occurrence-stable")
        self.assertEqual(metadatas[0]["content_id"], "content-stable")
        self.assertEqual(metadatas[0]["occurrence_id"], "occurrence-stable")
        self.assertEqual(
            metadatas[0]["local_url"],
            "#2026-08-05/ai-topic-radar/item/occurrence-stable",
        )

    def test_ingest_vector_chunks_for_date_indexes_atomic_items_without_markdown_duplicates(self):
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
        self.assertEqual(chunk_count, 1)
        self.assertEqual(len(store.added), 1)
        self.assertEqual(store.added[0][2], ["2026-06-21/topic-pool/0"])

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

            self.assertEqual(count, 1)
            self.assertEqual(store.deleted_dates, ["2026-06-21"])
            self.assertTrue((Path(tmp) / "search-index.json").exists())


if __name__ == "__main__":
    unittest.main()
