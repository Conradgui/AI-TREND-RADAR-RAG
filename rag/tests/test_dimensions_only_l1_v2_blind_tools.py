"""Offline guards for sealed prediction and scoring utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag.run_dimensions_only_l1_v2_blind import run
from rag.score_dimensions_only_l1_v2_blind import score


class FixtureExtractor:
    model = "fixture"

    def extract(self, query: str, conversation_context: str | None = None):
        decisions = {
            "schema_version": "atr.semantic-decisions/1.0",
            "dimensions": {
                "item_lookup": {"state": "absent", "evidence_spans": []},
                "recent_update_set": {"state": "present", "evidence_spans": [query.rstrip("？")]},
                "cross_time_or_entity_structure": {"state": "absent", "evidence_spans": []},
                "truth_assessable_claim": {"state": "absent", "evidence_spans": []},
                "explanation_or_comparison": {"state": "absent", "evidence_spans": []},
            },
            "protected_spans": ["近期"],
            "item_locator_precision": "none",
            "unresolved_reference_spans": [],
            "resolved_references": [],
        }
        return decisions, {"model": self.model, "attempts": 1}


def test_prediction_runner_needs_only_unlabelled_queries(tmp_path: Path) -> None:
    queries = tmp_path / "queries.json"
    queries.write_text(json.dumps({
        "dataset_id": "sealed",
        "cases": [{"case_id": "BLIND-001", "query": "近期有什么趋势？"}],
    }, ensure_ascii=False))

    report = run(queries, FixtureExtractor(), {"freeze_id": "frozen-v2"})

    assert report["freeze_id"] == "frozen-v2"
    assert [row["case_id"] for row in report["cases"]] == ["BLIND-001"]
    assert "expected" not in json.dumps(report, ensure_ascii=False)


def test_scorer_opens_labels_only_after_predictions_exist(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.json"
    labels = tmp_path / "labels.json"
    predictions.write_text(json.dumps({
        "experiment_id": "blind",
        "freeze_id": "frozen-v2",
        "cases": [{
            "case_id": "BLIND-001",
            "latency_seconds": 1.0,
            "envelope": {
                "status": "resolved",
                "contract": {
                    "primary_task_family": "trend_discovery",
                    "supporting_task_families": [],
                    "answer_mode": "important_news",
                    "protected_terms": ["近期"],
                    "resolved_references": [],
                    "web_permission": "on_demand",
                },
            },
        }],
    }))
    labels.write_text(json.dumps({"cases": [{
        "case_id": "BLIND-001",
        "expected_status": "resolved",
        "expected_primary": "trend_discovery",
        "expected_supporting": [],
        "expected_answer_mode": "important_news",
        "expected_protected_terms": ["近期"],
        "expected_references": [],
        "expected_web_permission": "on_demand",
    }]}))

    report = score(predictions, labels)

    assert report["complete_contract_accuracy"] == 1.0
    assert report["gate"]["passed"] is True
    assert report["protected_terms"]["micro_f1"] == 1.0


def test_scorer_rejects_a_gold_status_outside_the_public_envelope(tmp_path: Path) -> None:
    predictions = tmp_path / "predictions.json"
    labels = tmp_path / "labels.json"
    predictions.write_text(json.dumps({
        "experiment_id": "blind", "freeze_id": "frozen-v2", "cases": []
    }))
    labels.write_text(json.dumps({"cases": [{
        "case_id": "BLIND-001",
        "expected_status": "ambiguous",
        "expected_primary": "item_navigation",
        "expected_supporting": [],
        "expected_answer_mode": "item_disambiguation",
        "expected_protected_terms": [],
        "expected_references": [],
        "expected_web_permission": "on_demand",
    }]}))

    with pytest.raises(ValueError, match="invalid expected_status"):
        score(predictions, labels)
