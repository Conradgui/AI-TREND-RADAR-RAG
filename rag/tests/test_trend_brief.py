"""Tests for deterministic trend brief assembly."""

import json
import re
import unittest

from rag.trend_brief import (
    build_trend_brief_markdown,
    inspect_trend_brief_artifact,
    select_brief_citations,
    slugify_topic,
    summarize_brief_inputs,
)


SAMPLE_CITATIONS = [
    {
        "evidence_type": "internal",
        "date": "2026-06-21",
        "source": "Product Hunt",
        "title": "Graph RAG workflow",
        "citation_id": "2026-06-21/graph-topic/graph-rag-workflow",
        "excerpt": "Graph RAG workflow evidence.",
        "category": "AI 产品与用户入口",
    },
    {
        "evidence_type": "internal",
        "date": "2026-06-20",
        "source": "GitHub",
        "title": "Agentic RAG eval",
        "citation_id": "2026-06-20/vector/agentic-rag-eval",
        "excerpt": "Agentic RAG evaluation evidence.",
        "category": "AI Agent",
    },
]


SAMPLE_GRAPH_EVIDENCE = {
    "entity_id": "rag",
    "entity_label": "RAG",
    "content_count": 5,
    "observation_count": 8,
    "repeated_content_count": 2,
    "previous_link_count": 3,
    "date_count": 2,
    "source_count": 3,
    "sample_paths": [
        {"entity": "RAG", "title": "Graph RAG workflow", "date": "2026-06-21", "source": "Product Hunt"},
        {"entity": "RAG", "title": "Agentic RAG eval", "date": "2026-06-20", "source": "GitHub"},
    ],
}


class TrendBriefTests(unittest.TestCase):
    def test_slugify_topic_is_filename_safe(self):
        self.assertEqual(slugify_topic("Graph RAG / Agentic RAG"), "graph-rag-agentic-rag")
        self.assertEqual(slugify_topic("  RAG  "), "rag")

    def test_summary_counts_internal_and_graph_inputs(self):
        summary = summarize_brief_inputs(
            topic="RAG",
            citations=SAMPLE_CITATIONS,
            graph_evidence=SAMPLE_GRAPH_EVIDENCE,
            answer_policy={"mode": "internal_grounded"},
            source_review={"status": "internal_only"},
            batch_evidence_trace={"attempted": True, "candidate_count": 75, "selected_count": 4, "background_candidate_count": 71, "source_quality_counts": {"academic": 19}},
        )

        self.assertEqual(summary["topic"], "RAG")
        self.assertEqual(summary["citation_count"], 2)
        self.assertEqual(summary["graph_counts"], {
            "content_count": 5,
            "observation_count": 8,
            "repeated_content_count": 2,
            "previous_link_count": 3,
            "date_count": 2,
            "source_count": 3,
        })
        self.assertEqual(summary["policy_mode"], "internal_grounded")
        self.assertEqual(summary["artifact_quality_status"], "internal_only")
        self.assertEqual(summary["source_relevance"]["relevance_status"], "internal_only")
        self.assertEqual(summary["batch_evidence"]["candidate_count"], 75)
        self.assertEqual(summary["batch_evidence"]["selected_count"], 4)

    def test_markdown_contains_required_sections_and_parseable_appendix(self):
        markdown = build_trend_brief_markdown(
            topic="RAG",
            citations=SAMPLE_CITATIONS,
            graph_evidence=SAMPLE_GRAPH_EVIDENCE,
            source_review={"status": "internal_only", "instruction": "Use internal corpus only."},
            answer_policy={"mode": "internal_grounded", "external_search_required": False},
            latest_corpus_date="2026-06-21",
            generated_at="2026-06-24T00:00:00+00:00",
            mode="local-only",
        )

        for section in [
            "# Trend Brief: RAG",
            "## Executive Summary",
            "## Key Trend Themes",
            "## Evidence Table",
            "## Graph Relationship Summary",
            "## Source Quality Review",
            "## Uncertainty And Missing Evidence",
            "## Recommended Follow-Up Actions",
            "## Machine-Readable Appendix",
        ]:
            self.assertIn(section, markdown)

        self.assertIn("2026-06-21/graph-topic/graph-rag-workflow", markdown)
        self.assertIn("图谱证据只能证明语料中的覆盖和关联", markdown)

        match = re.search(r"```json\n(.*?)\n```", markdown, flags=re.S)
        self.assertIsNotNone(match)
        appendix = json.loads(match.group(1))
        self.assertEqual(appendix["topic"], "RAG")
        self.assertEqual(appendix["citation_count"], 2)
        self.assertEqual(appendix["graph_counts"]["content_count"], 5)
        self.assertNotIn("topic_count", appendix["graph_counts"])
        self.assertEqual(appendix["batch_evidence"]["attempted"], False)

        inspection = inspect_trend_brief_artifact(markdown)
        self.assertTrue(inspection["consistent"])
        self.assertEqual(inspection["evidence_table_count"], 2)
        self.assertEqual(inspection["appendix_citation_count"], 2)

    def test_markdown_marks_weak_evidence_when_citations_are_sparse(self):
        markdown = build_trend_brief_markdown(
            topic="RAG",
            citations=SAMPLE_CITATIONS[:1],
            graph_evidence=None,
            source_review={"status": "internal_only", "instruction": "Use internal corpus only."},
            answer_policy={"mode": "internal_grounded", "external_search_required": False},
            latest_corpus_date="2026-06-21",
            generated_at="2026-06-24T00:00:00+00:00",
            mode="local-only",
        )

        self.assertIn("当前证据更适合描述为单点信号", markdown)
        self.assertIn("缺少图谱关系证据", markdown)
        self.assertIn("缺少外部一手来源", markdown)

    def test_markdown_cleans_noisy_excerpts_for_readability(self):
        markdown = build_trend_brief_markdown(
            topic="RAG",
            citations=[
                {
                    "evidence_type": "internal",
                    "date": "2026-06-21",
                    "source": "GitHub Search:rag",
                    "title": "Noisy RAG item",
                    "citation_id": "c-noisy",
                    "excerpt": "First line<br>Second line &quot;quoted&quot;\n| table noise | with pipe | and a very long tail",
                    "category": "AI 产品与用户入口",
                }
            ],
            graph_evidence=None,
            source_review={"status": "internal_only", "instruction": "Use internal corpus only."},
            answer_policy={"mode": "internal_grounded", "external_search_required": False},
            latest_corpus_date="2026-06-21",
            generated_at="2026-06-24T00:00:00+00:00",
            mode="local-only",
        )

        self.assertNotIn("<br>", markdown)
        self.assertIn('First line Second line "quoted"', markdown)

    def test_graph_citation_is_grouped_as_graph_coverage_theme(self):
        markdown = build_trend_brief_markdown(
            topic="RAG",
            citations=[
                {
                    "evidence_type": "graph",
                    "content_type": "graph_reasoning",
                    "date": "2026-06-21",
                    "source": "Neo4j graph",
                    "title": "RAG graph relationship evidence",
                    "citation_id": "graph-reasoning/rag",
                    "excerpt": "RAG graph relationship summary.",
                }
            ],
            graph_evidence=SAMPLE_GRAPH_EVIDENCE,
            source_review={"status": "internal_only", "instruction": "Use internal corpus only."},
            answer_policy={"mode": "internal_grounded", "external_search_required": False},
            latest_corpus_date="2026-06-21",
            generated_at="2026-06-24T00:00:00+00:00",
            mode="local-only",
        )

        self.assertIn("**Graph coverage**", markdown)
        self.assertNotIn("**Neo4j graph**", markdown)

    def test_select_brief_citations_prunes_generic_report_chunks_when_specific_evidence_exists(self):
        selected = select_brief_citations([
            {
                "evidence_type": "internal",
                "date": "2026-06-19",
                "source": "ai-topic-radar",
                "title": "ai-topic-radar",
                "citation_id": "report-row",
                "excerpt": "table-like report fragment",
            },
            SAMPLE_CITATIONS[0],
            {
                "evidence_type": "graph",
                "content_type": "graph_reasoning",
                "date": "2026-06-21",
                "source": "Neo4j graph",
                "title": "RAG graph relationship evidence",
                "citation_id": "graph-reasoning/rag",
                "excerpt": "RAG graph relationship summary.",
            },
        ])

        self.assertEqual([citation["citation_id"] for citation in selected], [
            "2026-06-21/graph-topic/graph-rag-workflow",
            "graph-reasoning/rag",
        ])

    def test_select_brief_citations_filters_irrelevant_external_results_for_rag_topic(self):
        selected = select_brief_citations([
            {
                "evidence_type": "external",
                "source": "aws.amazon.com",
                "title": "What is RAG?",
                "url": "https://aws.amazon.com/what-is/retrieval-augmented-generation/",
                "retrieved_at": "2026-06-24",
                "excerpt": "Retrieval-Augmented Generation overview.",
            },
            {
                "evidence_type": "external",
                "source": "www.nasa.gov",
                "title": "Advanced Health Research on Station Using Augmented Reality",
                "url": "https://www.nasa.gov/example",
                "retrieved_at": "2026-06-24",
                "excerpt": "Biomedical tests using augmented and virtual reality tools.",
            },
        ], topic="RAG")

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["source"], "aws.amazon.com")

    def test_external_citations_use_url_as_evidence_identifier(self):
        markdown = build_trend_brief_markdown(
            topic="RAG",
            citations=[
                {
                    "evidence_type": "external",
                    "source": "aws.amazon.com",
                    "title": "What is RAG?",
                    "url": "https://aws.amazon.com/what-is/retrieval-augmented-generation/",
                    "retrieved_at": "2026-06-24",
                    "excerpt": "Retrieval-Augmented Generation overview.",
                }
            ],
            graph_evidence=None,
            source_review={"status": "weak_only", "instruction": "External evidence is weak."},
            answer_policy={"mode": "internal_and_external_grounded", "external_search_required": False},
            latest_corpus_date="2026-06-21",
            generated_at="2026-06-24T00:00:00+00:00",
            mode="live-external",
        )

        self.assertIn("https://aws.amazon.com/what-is/retrieval-augmented-generation/", markdown)
        self.assertIn("| 2026-06-24 | aws.amazon.com | What is RAG? | external | https://aws.amazon.com", markdown)

    def test_summary_exposes_source_quality_counts_and_artifact_quality_status(self):
        summary = summarize_brief_inputs(
            topic="RAG",
            citations=[
                {
                    "evidence_type": "external",
                    "source": "aws.amazon.com",
                    "title": "What is RAG?",
                    "url": "https://aws.amazon.com/what-is/retrieval-augmented-generation/",
                    "source_quality": "developer",
                    "excerpt": "RAG evaluation benchmark and graph RAG workflow guidance.",
                },
                {
                    "evidence_type": "external",
                    "source": "example.blog",
                    "title": "RAG blog",
                    "url": "https://example.blog/rag",
                    "source_quality": "generic",
                },
            ],
            graph_evidence=None,
            answer_policy={"mode": "internal_and_external_grounded"},
            source_review={"status": "mixed_quality", "external_count": 2, "primary_count": 1, "supporting_count": 0},
        )

        self.assertEqual(summary["source_quality_counts"], {"developer": 1, "generic": 1})
        self.assertEqual(summary["artifact_quality_status"], "research_quality_verified")
        self.assertEqual(summary["source_relevance"]["relevance_counts"]["direct_support"], 1)
        self.assertEqual(summary["source_relevance"]["relevance_counts"]["weak_context"], 1)


if __name__ == "__main__":
    unittest.main()
