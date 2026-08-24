"""Tests for deterministic graph reasoning evaluation."""

import unittest

from rag.eval_graph_reasoning import (
    score_graph_reasoning_rows,
    summarize_graph_reasoning_rows,
)


class GraphReasoningEvalTests(unittest.TestCase):
    def test_score_passes_when_entity_has_topic_date_and_source_paths(self):
        observations = [
            {
                "id": "G1",
                "entity_id": "rag",
                "content_count": 6,
                "repeated_content_count": 2,
                "date_count": 5,
                "source_count": 2,
                "sample_paths": [
                    {"entity": "rag", "topic": "LightRAG", "date": "2026-05-30", "source": "GitHub Search:rag"}
                ],
            }
        ]
        seeds = [
            {
                "id": "G1",
                "entity_id": "rag",
                "min_contents": 5,
                "min_repeated_contents": 1,
                "min_dates": 3,
                "min_sources": 1,
                "required_paths": ["entity_observation_date", "entity_observation_source"],
            }
        ]

        scored = score_graph_reasoning_rows(observations, seeds)

        self.assertTrue(scored[0]["passed"])
        self.assertEqual(scored[0]["failed_checks"], [])

    def test_score_fails_when_source_path_is_missing(self):
        observations = [
            {
                "id": "G2",
                "entity_id": "openai",
                "content_count": 8,
                "repeated_content_count": 2,
                "date_count": 4,
                "source_count": 0,
                "sample_paths": [],
            }
        ]
        seeds = [
            {
                "id": "G2",
                "entity_id": "openai",
                "min_contents": 5,
                "min_repeated_contents": 1,
                "min_dates": 3,
                "min_sources": 1,
                "required_paths": ["entity_observation_source"],
            }
        ]

        scored = score_graph_reasoning_rows(observations, seeds)

        self.assertFalse(scored[0]["passed"])
        self.assertIn("missing_entity_observation_source_path", scored[0]["failed_checks"])

    def test_summary_counts_failures(self):
        scored = [
            {"passed": True, "failed_checks": []},
            {"passed": False, "failed_checks": ["insufficient_dates"]},
        ]

        self.assertEqual(
            summarize_graph_reasoning_rows(scored),
            {
                "total": 2,
                "passed": 1,
                "failed": 1,
                "failure_counts": {"insufficient_dates": 1},
            },
        )


if __name__ == "__main__":
    unittest.main()
