"""Tests for URL-labelled retrieval quality metrics."""

import json
import tempfile
import unittest
from pathlib import Path

from rag.eval_retrieval_quality import (
    assess_snapshot,
    apply_query_contract,
    evaluation_contract,
    load_dataset,
    metric_ceiling,
    normalize_url,
    score_query,
    summarize,
)
from rag.query_understanding import analyze_query


class RetrievalQualityEvalTests(unittest.TestCase):
    def test_normalize_url_removes_tracking_and_trailing_slash(self):
        self.assertEqual(
            normalize_url("https://Example.com/path/?utm_source=x&keep=1#part"),
            "https://example.com/path?keep=1",
        )

    def test_scores_precision_recall_f1_mrr_and_ndcg(self):
        query = {
            "id": "Q1",
            "answerable": True,
            "relevant": [
                {"url": "https://example.com/a", "grade": 3},
                {"url": "https://example.com/b", "grade": 1},
            ],
        }
        retrieved = [
            {"url": "https://example.com/noise", "title": "noise"},
            {"url": "https://example.com/a/", "title": "A"},
        ]

        score = score_query(query, retrieved, k=2)

        self.assertEqual(score["true_positive"], 1)
        self.assertEqual(score["precision_at_k"], 0.5)
        self.assertEqual(score["recall_at_k"], 0.5)
        self.assertEqual(score["f1_at_k"], 0.5)
        self.assertEqual(score["mrr"], 0.5)
        self.assertGreater(score["ndcg_at_k"], 0)
        self.assertLess(score["ndcg_at_k"], 1)

    def test_deduplicates_repeated_retrieval_identity(self):
        query = {"id": "Q1", "answerable": True, "relevant": [{"url": "https://example.com/a", "grade": 1}]}
        retrieved = [{"url": "https://example.com/a"}, {"url": "https://example.com/a/"}]

        score = score_query(query, retrieved, k=2)

        self.assertEqual(score["returned"], 1)
        self.assertEqual(score["true_positive"], 1)

    def test_unanswerable_query_requires_empty_retrieval(self):
        query = {"id": "Q0", "answerable": False, "relevant": []}

        rejected = score_query(query, [], k=10)
        hallucinated = score_query(query, [{"url": "https://example.com/noise"}], k=10)

        self.assertTrue(rejected["correct_rejection"])
        self.assertFalse(hallucinated["correct_rejection"])

    def test_claim_refutation_is_diagnostic_until_claim_labels_exist(self):
        query = {
            "id": "HN16",
            "answerable": False,
            "task_family": "claim_verification",
            "evaluation_contract": "future_claim_classification",
            "negative_type": "claim_refutation",
            "relevant": [],
        }

        score = score_query(query, [{"url": "https://example.com/oerx"}], k=10)

        self.assertFalse(score["scored"])
        self.assertIsNone(score["query_success"])
        self.assertNotIn("correct_rejection", score)
        self.assertEqual(score["unscored_reason"], "claim_labels_missing")

    def test_entity_absent_is_diagnostic_until_sufficiency_gate_exists(self):
        query = {
            "id": "HN01",
            "answerable": False,
            "task_family": "claim_verification",
            "evaluation_contract": "diagnostic_only",
            "negative_type": "entity_absent",
            "relevant": [],
        }

        score = score_query(query, [{"url": "https://example.com/nearest-neighbour"}], k=10)

        self.assertFalse(score["scored"])
        self.assertEqual(score["returned"], 1)
        self.assertEqual(score["unscored_reason"], "evidence_sufficiency_gate_missing")

    def test_explicit_task_contract_is_exposed_to_the_scorer(self):
        query = {
            "id": "RQ07",
            "answerable": True,
            "task_family": "item_navigation",
            "evaluation_contract": "ranked_retrieval",
            "relevance_set_status": "complete",
            "relevant": [{"url": "https://example.com/a", "grade": 1}],
        }

        score = score_query(query, [{"url": "https://example.com/a"}], k=1)

        self.assertTrue(score["scored"])
        self.assertEqual(score["task_family"], "item_navigation")
        self.assertEqual(score["evaluation_contract"], "ranked_retrieval")
        self.assertEqual(score["relevance_set_status"], "complete")

    def test_summary_reports_macro_micro_and_query_success_accuracy(self):
        rows = [
            {
                "answerable": True,
                "query_success": True,
                "true_positive": 1,
                "relevant_total": 2,
                "precision_at_k": 0.1,
                "recall_at_k": 0.5,
                "f1_at_k": 0.1667,
                "mrr": 1.0,
                "ndcg_at_k": 0.8,
            },
            {"answerable": False, "query_success": True, "correct_rejection": True},
        ]

        summary = summarize(rows, k=10)

        self.assertEqual(summary["query_success_accuracy"], 1.0)
        self.assertEqual(summary["correct_rejection_rate"], 1.0)
        self.assertEqual(summary["micro"]["precision_at_k"], 0.1)
        self.assertEqual(summary["micro"]["recall_at_k"], 0.5)

    def test_summary_groups_tasks_and_excludes_diagnostics(self):
        rows = [
            {
                "task_family": "item_navigation",
                "evaluation_contract": "ranked_retrieval",
                "scored": True,
                "answerable": True,
                "query_success": True,
                "true_positive": 1,
                "relevant_total": 1,
                "metric_cutoff": 1,
                "precision_at_k": 1.0,
                "recall_at_k": 1.0,
                "f1_at_k": 1.0,
                "mrr": 1.0,
                "ndcg_at_k": 1.0,
            },
            {
                "task_family": "claim_verification",
                "evaluation_contract": "diagnostic_only",
                "scored": False,
                "answerable": False,
                "query_success": None,
                "unscored_reason": "evidence_sufficiency_gate_missing",
            },
        ]

        summary = summarize(rows)

        self.assertEqual(summary["scoreable_query_count"], 1)
        self.assertEqual(summary["diagnostic_query_count"], 1)
        self.assertEqual(summary["by_task_family"]["item_navigation"]["query_count"], 1)
        self.assertEqual(summary["by_task_family"]["claim_verification"]["diagnostic_count"], 1)
        self.assertEqual(summary["unscored_reason_counts"]["evidence_sufficiency_gate_missing"], 1)
        self.assertTrue(summary["not_a_release_gate"])

    def test_metric_ceiling_uses_query_specific_cutoff(self):
        exact = {
            "id": "Q1",
            "answerable": True,
            "metric_cutoff": 1,
            "relevant": [{"url": "https://example.com/a", "grade": 1}],
        }
        broad = {
            "id": "Q2",
            "answerable": True,
            "metric_cutoff": 10,
            "relevant": [{"url": f"https://example.com/{i}", "grade": 1} for i in range(3)],
        }

        self.assertEqual(metric_ceiling(exact)["precision_at_k"], 1.0)
        self.assertEqual(metric_ceiling(exact)["f1_at_k"], 1.0)
        self.assertEqual(metric_ceiling(broad)["precision_at_k"], 0.3)
        self.assertEqual(metric_ceiling(broad)["recall_at_k"], 1.0)

    def test_dataset_overlay_preserves_base_and_applies_reviewable_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.json"
            overlay = root / "overlay.json"
            base.write_text(
                json.dumps({
                    "dataset_id": "v1",
                    "queries": [
                        {"id": "Q1", "query": "old", "answerable": True, "relevant": []},
                    ],
                }),
                encoding="utf-8",
            )
            overlay.write_text(
                json.dumps({
                    "dataset_id": "v2",
                    "base_dataset": "base.json",
                    "query_overrides": {
                        "Q1": {"query": "new", "metric_cutoff": 1, "review_status": "ai_proposed"},
                    },
                    "additional_queries": [
                        {"id": "Q2", "query": "negative", "answerable": False, "relevant": []},
                    ],
                }),
                encoding="utf-8",
            )

            resolved = load_dataset(overlay)

        self.assertEqual(resolved["dataset_id"], "v2")
        self.assertEqual([query["id"] for query in resolved["queries"]], ["Q1", "Q2"])
        self.assertEqual(resolved["queries"][0]["query"], "new")
        self.assertEqual(resolved["queries"][0]["metric_cutoff"], 1)
        self.assertEqual(resolved["queries"][0]["review_status"], "ai_proposed")

    def test_dataset_contract_defaults_apply_to_base_and_negative_overlay_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.json"
            overlay = root / "overlay.json"
            base.write_text(
                json.dumps({
                    "dataset_id": "v1",
                    "queries": [
                        {"id": "Q1", "query": "title", "kind": "exact_title", "answerable": True, "relevant": []},
                    ],
                }),
                encoding="utf-8",
            )
            overlay.write_text(
                json.dumps({
                    "dataset_id": "v2",
                    "base_dataset": "base.json",
                    "contract_defaults": {
                        "by_kind": {
                            "exact_title": {
                                "task_family": "item_navigation",
                                "evaluation_contract": "ranked_retrieval",
                                "relevance_set_status": "complete",
                            },
                        },
                        "by_negative_type": {
                            "entity_absent": {
                                "task_family": "claim_verification",
                                "evaluation_contract": "diagnostic_only",
                                "relevance_set_status": "missing",
                            },
                        },
                    },
                    "additional_queries": [
                        {"id": "HN1", "query": "missing", "kind": "unanswerable_control", "negative_type": "entity_absent", "answerable": False, "relevant": []},
                    ],
                }),
                encoding="utf-8",
            )

            resolved = load_dataset(overlay)

        item, negative = resolved["queries"]
        self.assertEqual(item["task_family"], "item_navigation")
        self.assertEqual(item["evaluation_contract"], "ranked_retrieval")
        self.assertEqual(negative["evaluation_contract"], "diagnostic_only")
        self.assertEqual(negative["task_family"], "claim_verification")

    def test_evaluation_contract_maps_legacy_queries_without_hiding_the_legacy_status(self):
        contract = evaluation_contract({"id": "Q1", "answerable": True, "kind": "exact_title"})

        self.assertEqual(contract["task_family"], "item_navigation")
        self.assertEqual(contract["evaluation_contract"], "ranked_retrieval")
        self.assertEqual(contract["relevance_set_status"], "sampled")
        self.assertTrue(contract["legacy_inferred"])

    def test_snapshot_mismatch_is_blocked_unless_directional(self):
        target = {"latest_corpus_date": "2026-08-10", "corpus_revision": "target"}
        observed = {"latest_corpus_date": "2026-08-05", "document_count": 100}

        blocked = assess_snapshot(target, observed, directional=False)
        directional = assess_snapshot(target, observed, directional=True)

        self.assertEqual(blocked["status"], "mismatch_blocked")
        self.assertFalse(blocked["can_run"])
        self.assertEqual(directional["status"], "mismatched_directional")
        self.assertTrue(directional["can_run"])
        self.assertFalse(directional["release_gate_eligible"])

    def test_snapshot_with_unobserved_revision_cannot_enter_release_gate(self):
        assessment = assess_snapshot(
            {"latest_corpus_date": "2026-08-10", "corpus_revision": "target"},
            {"latest_corpus_date": "2026-08-10", "document_count": 100},
        )

        self.assertEqual(assessment["status"], "matched_revision_unobserved")
        self.assertTrue(assessment["can_run"])
        self.assertFalse(assessment["release_gate_eligible"])

    def test_metric_ceiling_does_not_promise_rejection_for_diagnostic_contracts(self):
        ceiling = metric_ceiling({
            "id": "HN01",
            "answerable": False,
            "task_family": "claim_verification",
            "evaluation_contract": "diagnostic_only",
            "negative_type": "entity_absent",
            "relevant": [],
        })

        self.assertFalse(ceiling["scored"])
        self.assertEqual(ceiling["unscored_reason"], "evidence_sufficiency_gate_missing")
        self.assertNotIn("correct_rejection_rate", ceiling)

    def test_summary_uses_each_rows_cutoff_for_micro_precision(self):
        rows = [
            {
                "answerable": True,
                "query_success": True,
                "true_positive": 1,
                "relevant_total": 1,
                "metric_cutoff": 1,
                "precision_at_k": 1.0,
                "recall_at_k": 1.0,
                "f1_at_k": 1.0,
                "mrr": 1.0,
                "ndcg_at_k": 1.0,
            },
            {
                "answerable": True,
                "query_success": True,
                "true_positive": 2,
                "relevant_total": 3,
                "metric_cutoff": 10,
                "precision_at_k": 0.2,
                "recall_at_k": 0.6667,
                "f1_at_k": 0.3077,
                "mrr": 1.0,
                "ndcg_at_k": 0.8,
            },
        ]

        summary = summarize(rows)

        self.assertEqual(summary["micro"]["precision_at_k"], round(3 / 11, 4))
        self.assertEqual(summary["metric_cutoff_total"], 11)

    def test_query_contract_applies_strict_recent_window(self):
        plan = analyze_query("OpenAI 最近有哪些重要动态？")

        contracted = apply_query_contract(
            plan,
            {"time_policy": "strict_recent", "time_window_days": 7},
        )

        self.assertEqual(contracted.time_window["label"], "recent_corpus_first")
        self.assertEqual(contracted.time_window["days"], 7)
        self.assertTrue(contracted.time_window["requires_date_filter"])

    def test_query_contract_can_remove_implicit_recent_filter(self):
        plan = analyze_query("最近 RAG 和向量数据库有哪些值得关注的开源项目？")

        contracted = apply_query_contract(plan, {"time_policy": "not_limited"})

        self.assertEqual(contracted.time_window["label"], "not_limited")
        self.assertIsNone(contracted.time_window["days"])


if __name__ == "__main__":
    unittest.main()
