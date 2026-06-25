"""Tests for selecting citations from batched external evidence."""

import json
import tempfile
import unittest
from pathlib import Path

from rag.batch_evidence import load_batch_evidence_trace, select_batch_evidence_citations


class BatchEvidenceTests(unittest.TestCase):
    def test_selects_primary_quality_topic_relevant_citations(self):
        citations = [
            _citation("https://example.com/rag", "generic", "Generic RAG guide"),
            _citation("https://arxiv.org/html/1", "academic", "RAG benchmark"),
            _citation("https://pinecone.io/learn/rag", "developer", "RAG developer guide"),
            _citation("https://github.com/example/rag-bench", "official", "RAG benchmark repo"),
            _citation("https://nasa.gov/ar", "official", "Augmented reality report", excerpt="Virtual reality tools."),
            _citation("https://arxiv.org/html/1", "academic", "Duplicate RAG benchmark"),
        ]

        selected = select_batch_evidence_citations(citations, topic="RAG", max_citations=3)

        self.assertEqual([item["url"] for item in selected], [
            "https://arxiv.org/html/1",
            "https://github.com/example/rag-bench",
            "https://pinecone.io/learn/rag",
        ])

    def test_load_batch_evidence_trace_counts_candidates_and_selected(self):
        artifact = {
            "result": {
                "citations": [
                    _citation("https://arxiv.org/html/1", "academic", "RAG benchmark"),
                    _citation("https://example.com/rag", "generic", "Generic RAG guide"),
                ]
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "batch.json"
            path.write_text(json.dumps(artifact), encoding="utf-8")

            trace = load_batch_evidence_trace(path, topic="RAG", max_citations=4)

        self.assertTrue(trace["attempted"])
        self.assertEqual(trace["candidate_count"], 2)
        self.assertEqual(trace["selected_count"], 1)
        self.assertEqual(trace["source_quality_counts"], {"academic": 1, "generic": 1})
        self.assertEqual(trace["background_candidate_count"], 1)


def _citation(url: str, quality: str, title: str, excerpt: str = "Retrieval augmented generation benchmark.") -> dict:
    return {
        "evidence_type": "external",
        "provider": "test",
        "source": url.split("/")[2],
        "source_type": "web",
        "title": title,
        "url": url,
        "retrieved_at": "2026-06-25",
        "excerpt": excerpt,
        "source_quality": quality,
    }


if __name__ == "__main__":
    unittest.main()
