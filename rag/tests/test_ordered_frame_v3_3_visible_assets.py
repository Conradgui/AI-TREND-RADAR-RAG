"""Freeze-contract tests for the six-case v3.3 visible calibration."""

from __future__ import annotations

import json

import pytest

from rag.build_ordered_frame_v3_3_visible_assets import (
    build_visible_freeze_manifest,
    validate_visible_gold,
    validate_visible_queries,
)


def _queries() -> dict:
    return {
        "dataset_id": "visible",
        "cases": [
            {"case_id": f"case-{index}", "query": f"问题 {index}", "conversation_context": None}
            for index in range(6)
        ],
    }


def _gold() -> dict:
    return {
        "dataset_id": "visible",
        "cases": [
            {
                "case_id": f"case-{index}",
                "expected_status": "resolved",
                "expected_deliveries": [["evidence_research", "explanation", "none"]],
                "expected_contract_literals": [],
                "expected_web_permission": "on_demand",
            }
            for index in range(6)
        ],
    }


def test_visible_validator_requires_exactly_six_public_cases() -> None:
    document = _queries()
    validate_visible_queries(document)
    document["cases"].pop()

    with pytest.raises(ValueError, match="exactly six"):
        validate_visible_queries(document)


def test_visible_gold_must_match_query_order() -> None:
    gold = _gold()
    gold["cases"].reverse()

    with pytest.raises(ValueError, match="order"):
        validate_visible_gold(_queries(), gold)


def test_freeze_manifest_hashes_query_gold_runner_and_scorer(tmp_path) -> None:
    query_path = tmp_path / "queries.json"
    gold_path = tmp_path / "gold.json"
    runner_path = tmp_path / "runner.py"
    scorer_path = tmp_path / "scorer.py"
    query_path.write_text(json.dumps(_queries(), ensure_ascii=False))
    gold_path.write_text(json.dumps(_gold(), ensure_ascii=False))
    runner_path.write_text("runner = True\n")
    scorer_path.write_text("scorer = True\n")

    manifest = build_visible_freeze_manifest(
        experiment_id="visible",
        query_path=query_path,
        gold_path=gold_path,
        runtime={"model": "fixture"},
        runner_artifacts=[runner_path],
        scoring_artifacts=[scorer_path],
        root=tmp_path,
        require_project_artifacts=False,
    )

    assert manifest["runtime_budget"]["planned_cases"] == 6
    assert manifest["case_order"] == [f"case-{index}" for index in range(6)]
    assert manifest["query_sha256"] != manifest["gold_sha256"]
    assert manifest["runner_artifacts"][0]["path"] == "runner.py"
    assert manifest["scoring_artifacts"][0]["path"] == "scorer.py"
