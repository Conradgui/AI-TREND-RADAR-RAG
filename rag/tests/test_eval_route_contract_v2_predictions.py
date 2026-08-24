"""Contract tests for sealed Route Contract v2 scoring."""

from __future__ import annotations

import json
from pathlib import Path

from rag.eval_route_contract_v2_predictions import evaluate_predictions
from rag.query_understanding_v2 import understand_query_v2


def test_sealed_scorer_rewards_exact_contract_and_detects_route_regression(tmp_path: Path) -> None:
    query = "最近 Nova 有哪些重要动态？"
    contract = understand_query_v2(query).to_dict()
    predictions = {
        "prediction_id": "frozen-run",
        "query_dataset_id": "sealed-demo",
        "predictions": [{"case_id": "B-01", "query": query, "prediction": contract}],
    }
    gold = {
        "dataset_id": "sealed-demo",
        "cases": [
            {
                "case_id": "B-01",
                "original_query": query,
                "intent_signals": ["recency", "importance"],
                "primary_task_family": "trend_discovery",
                "supporting_task_families": [],
                "answer_mode": "important_news",
                "web_permission": "on_demand",
                "expected_protected_terms": ["Nova", "最近"],
                "ambiguity_expected": False,
                "expected_resolved_references": [],
                "minimal_pair_id": "BC-01",
            }
        ],
    }
    prediction_path = tmp_path / "predictions.json"
    gold_path = tmp_path / "sealed-gold.json"
    schema_path = Path("docs/rag-transformation/specs/route-contract-v2.schema.json")
    prediction_path.write_text(json.dumps(predictions), encoding="utf-8")
    gold_path.write_text(json.dumps(gold), encoding="utf-8")

    report = evaluate_predictions(prediction_path, gold_path, schema_path)
    assert report["route_accuracy"]["overall"]["accuracy"] == 1
    assert report["full_projection_exact"]["accuracy"] == 1
    assert report["minimal_pairs"]["all_cases_route_correct"] == 1

    predictions["predictions"][0]["prediction"]["primary_task_family"] = "evidence_research"
    prediction_path.write_text(json.dumps(predictions), encoding="utf-8")
    regressed = evaluate_predictions(prediction_path, gold_path, schema_path)
    assert regressed["route_accuracy"]["overall"]["accuracy"] == 0
    assert regressed["full_projection_exact"]["accuracy"] == 0
    assert regressed["minimal_pairs"]["all_cases_route_correct"] == 0
