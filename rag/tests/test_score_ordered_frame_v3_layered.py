"""Discrimination tests for the layered v3.1 evaluator."""

from __future__ import annotations

import json
import hashlib
import sys
from copy import deepcopy
from pathlib import Path

from rag.ordered_semantic_frame_v3 import build_ordered_route_envelope_v3
from rag.run_ordered_frame_v3_calibration import _canonical_sha256
from rag.score_ordered_frame_v3_layered import (
    L2_REPLAY_ARTIFACTS,
    LAYERED_SCORING_ARTIFACTS,
    _span_case,
    _span_positions,
    evaluate_gate,
    main,
    score_layered,
)


ROOT = Path(__file__).resolve().parents[2]
FREEZE_HASH = "fixture-freeze"
FREEZE = {
    "runner_artifacts": [
        {"path": path, "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
        for path in sorted(L2_REPLAY_ARTIFACTS)
    ],
    "scoring_artifacts": [
        {"path": path, "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
        for path in sorted(LAYERED_SCORING_ARTIFACTS)
    ],
}


def _delivery(family: str, evidence: str, output: str, locator: str = "none") -> dict:
    return {"task_family": family, "evidence_spans": [evidence], "requested_output_form": output, "locator_kind": locator}


CASES = [
    ("A", "定位 ATR-20260816-A1B2C3", _delivery("item_navigation", "ATR-20260816-A1B2C3", "exact_item", "atr_id"), ["ATR-20260816-A1B2C3"], "on_demand", [], "resolved"),
    ("B", "最近一周有哪些 OpenAI 重要动态？不要联网", _delivery("trend_discovery", "重要动态", "important_news"), ["最近一周", "OpenAI"], "forbidden", [], "resolved"),
    ("C", "梳理 Nova 从发布到更新的时间线", _delivery("temporal_relation_exploration", "从发布到更新的时间线", "timeline"), ["Nova"], "on_demand", [], "resolved"),
    ("D", "判断“Nova 已经开源”是否为真", _delivery("claim_verification", "是否为真", "verification_verdict"), ["Nova 已经开源"], "on_demand", [], "resolved"),
    ("E", "比较 Graph RAG 和向量 RAG", _delivery("evidence_research", "比较", "comparison"), ["Graph RAG", "向量 RAG"], "on_demand", [], "resolved"),
    ("F", "解释这个为什么重要", _delivery("evidence_research", "解释这个为什么重要", "explanation"), [], "on_demand", ["这个"], "clarification_required"),
]


def _assets() -> tuple[dict, dict, dict]:
    queries = {"dataset_id": "layered-fixture", "cases": []}
    gold = {"cases": []}
    predictions = {"query_dataset_id": "layered-fixture", "freeze_manifest_sha256": FREEZE_HASH, "planned": len(CASES), "executed": len(CASES), "cases": []}
    for case_id, query, delivery, protected, web, unresolved, status in CASES:
        frame = {
            "schema_version": "atr.ordered-semantic-frame/3.0",
            "deliveries": [delivery],
            "protected_spans": protected,
            "web_permission": web,
            "web_evidence_spans": ["不要联网"] if web == "forbidden" else [],
            "unresolved_reference_spans": unresolved,
        }
        queries["cases"].append({"case_id": case_id, "query": query})
        gold["cases"].append({
            "case_id": case_id,
            "expected_status": status,
            "expected_deliveries": [[delivery["task_family"], delivery["requested_output_form"], delivery["locator_kind"]]],
            "expected_delivery_evidence_spans": [delivery["evidence_spans"]],
            "expected_protected_terms": protected,
            "expected_critical_terms": {"other": protected},
            "expected_unresolved_reference_spans": unresolved,
            "expected_web_permission": web,
            "expected_web_evidence_spans": ["不要联网"] if web == "forbidden" else [],
        })
        predictions["cases"].append({
            "case_id": case_id,
            "query": query,
            "frame": frame,
            "envelope": build_ordered_route_envelope_v3(query, frame),
            "metadata": {"attempts": 1, "total_tokens": 1},
            "latency_seconds": 1.0,
            "error": None,
        })
    predictions["query_sha256"] = _canonical_sha256(queries)
    return queries, gold, predictions


def _score(queries: dict, gold: dict, predictions: dict) -> dict:
    frozen = deepcopy(FREEZE)
    frozen["query_sha256"] = _canonical_sha256(queries)
    frozen["gold_sha256"] = _canonical_sha256(gold)
    return score_layered(queries, gold, predictions, frozen, FREEZE_HASH)


def test_perfect_fixture_passes_every_layer() -> None:
    queries, gold, predictions = _assets()

    report = _score(queries, gold, predictions)

    assert report["gate"]["passed"] is True
    assert report["metrics"]["delivery_sequence_exact"] == 100
    assert report["metrics"]["l3_projection_consistency"] == 100
    assert report["metrics"]["product_complete"] == 100


def test_wider_protected_span_gets_partial_credit_not_total_failure() -> None:
    queries, gold, predictions = _assets()
    predictions["cases"][2]["frame"]["protected_spans"] = ["梳理 Nova"]
    predictions["cases"][2]["envelope"] = build_ordered_route_envelope_v3(
        predictions["cases"][2]["query"], predictions["cases"][2]["frame"]
    )

    perfect = _score(*_assets())
    report = _score(queries, gold, predictions)
    f1 = report["metrics"]["protected_span_char_micro_f1"]

    assert perfect["metrics"]["protected_span_char_micro_f1"] > f1 > 0
    assert report["cases"][2]["checks"]["product_complete"] is True
    assert report["gate"]["passed"] is True


def test_span_rules_cover_all_repeated_literals_and_define_empty_sets() -> None:
    assert len(_span_positions("Nova 与 Nova", ["Nova"])) == 8
    assert _span_case("解释", [], [])["f1"] == 100
    assert _span_case("解释", [], ["解释"]) == {
        "precision": 0.0,
        "recall": 100.0,
        "f1": 0.0,
        "counts": [0, 2, 0],
    }


def test_missing_delivery_counts_against_output_and_locator_denominators() -> None:
    queries, gold, predictions = _assets()
    case = predictions["cases"][-1]
    case["frame"]["deliveries"] = []
    case["envelope"] = build_ordered_route_envelope_v3(case["query"], case["frame"])

    report = _score(queries, gold, predictions)

    assert report["metrics"]["output_form_accuracy"] == 83.3
    assert report["metrics"]["locator_accuracy"] == 83.3


def test_wrong_l1_primary_route_fails_gate_even_with_consistent_projection() -> None:
    queries, gold, predictions = _assets()
    case = predictions["cases"][1]
    case["frame"]["deliveries"] = [_delivery("evidence_research", "重要动态", "explanation")]
    case["envelope"] = build_ordered_route_envelope_v3(case["query"], case["frame"])

    report = _score(queries, gold, predictions)

    assert report["gate"]["passed"] is False
    assert report["metrics"]["primary_task_family_accuracy"] < 85
    assert report["metrics"]["l3_projection_consistency"] == 100


def test_wrong_l2_status_and_wrong_l3_saved_projection_are_distinguished() -> None:
    queries, gold, predictions = _assets()
    wrong_l2 = deepcopy(predictions)
    wrong_l2["cases"][-1]["envelope"] = deepcopy(predictions["cases"][0]["envelope"])
    wrong_l3 = deepcopy(predictions)
    wrong_l3["cases"][0]["envelope"]["contract"]["request_id"] = "tampered"

    l2_report = _score(queries, gold, wrong_l2)
    l3_report = _score(queries, gold, wrong_l3)

    assert l2_report["metrics"]["clarification_recall"] == 0
    assert l2_report["gate"]["passed"] is False
    assert l3_report["metrics"]["l3_projection_consistency"] < 100
    assert l3_report["gate"]["passed"] is False


def test_wrong_l4_product_completion_cannot_be_hidden_by_passing_micro_span_gate() -> None:
    queries, gold, predictions = _assets()
    for index in range(14):
        case_id = f"X{index:02d}"
        fragment = f"ExtremelyLongStableTitleFragmentAlpha{index:02d}"
        query = f"请在今天的内部日报中查找标题片段 {fragment} 并返回候选"
        delivery = _delivery("item_navigation", fragment, "item_disambiguation", "title_fragment")
        frame = {
            "schema_version": "atr.ordered-semantic-frame/3.0",
            "deliveries": [delivery],
            "protected_spans": [fragment],
            "web_permission": "on_demand",
            "web_evidence_spans": [],
            "unresolved_reference_spans": [],
        }
        queries["cases"].append({"case_id": case_id, "query": query})
        gold["cases"].append({
            "case_id": case_id,
            "expected_status": "resolved",
            "expected_deliveries": [["item_navigation", "item_disambiguation", "title_fragment"]],
            "expected_delivery_evidence_spans": [[fragment]],
            "expected_protected_terms": [fragment],
            "expected_critical_terms": {"other": [fragment]},
            "expected_unresolved_reference_spans": [],
            "expected_web_permission": "on_demand",
            "expected_web_evidence_spans": [],
        })
        predictions["cases"].append({
            "case_id": case_id,
            "query": query,
            "frame": frame,
            "envelope": build_ordered_route_envelope_v3(query, frame),
            "metadata": {"attempts": 1, "total_tokens": 1},
            "latency_seconds": 1.0,
            "error": None,
        })
    for case in predictions["cases"][6:11]:
        case["frame"]["protected_spans"] = [case["query"]]
        case["envelope"] = build_ordered_route_envelope_v3(case["query"], case["frame"])
    predictions["planned"] = predictions["executed"] = len(queries["cases"])
    predictions["query_sha256"] = _canonical_sha256(queries)

    report = _score(queries, gold, predictions)

    assert report["metrics"]["protected_span_char_micro_f1"] >= 85
    assert report["metrics"]["product_complete"] == 75
    assert report["gate"]["checks"]["product_complete_at_least_80"] is False
    assert report["gate"]["passed"] is False


def test_l2_replay_refuses_hash_drift() -> None:
    queries, gold, predictions = _assets()
    drifted = deepcopy(FREEZE)
    drifted["runner_artifacts"][0]["sha256"] = "0" * 64

    import pytest

    with pytest.raises(ValueError, match="frozen L2 artifact drift"):
        score_layered(queries, gold, predictions, drifted, FREEZE_HASH)


def test_cli_writes_a_traceable_report_and_refuses_overwrite(tmp_path, monkeypatch) -> None:
    import pytest

    queries, gold, predictions = _assets()
    manifest = deepcopy(FREEZE)
    manifest.update({
        "experiment_id": "layered-cli-fixture",
        "query_sha256": _canonical_sha256(queries),
        "gold_sha256": _canonical_sha256(gold),
    })
    query_path = tmp_path / "queries.json"
    gold_path = tmp_path / "gold.json"
    prediction_path = tmp_path / "predictions.json"
    manifest_path = tmp_path / "freeze.json"
    output_path = tmp_path / "score.json"
    query_path.write_text(json.dumps(queries, ensure_ascii=False))
    gold_path.write_text(json.dumps(gold, ensure_ascii=False))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False))
    predictions["freeze_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    prediction_path.write_text(json.dumps(predictions, ensure_ascii=False))
    monkeypatch.setattr(sys, "argv", [
        "score_ordered_frame_v3_layered",
        "--queries", str(query_path),
        "--gold", str(gold_path),
        "--predictions", str(prediction_path),
        "--freeze-manifest", str(manifest_path),
        "--output", str(output_path),
    ])

    main()

    report = json.loads(output_path.read_text())
    assert report["experiment_id"] == "layered-cli-fixture"
    assert report["freeze_manifest_sha256"] == predictions["freeze_manifest_sha256"]
    assert report["gate"]["passed"] is True
    with pytest.raises(FileExistsError):
        main()


def test_scorer_aligns_a_sealed_shard_identifier() -> None:
    queries, gold, predictions = _assets()
    queries["shard_id"] = "sealed-shard"
    queries.pop("dataset_id")
    predictions["query_dataset_id"] = "sealed-shard"
    predictions["query_sha256"] = _canonical_sha256(queries)

    report = _score(queries, gold, predictions)

    assert report["gate"]["passed"] is True


def test_scoring_amendment_preserves_the_original_prediction_freeze() -> None:
    queries, gold, predictions = _assets()
    manifest = deepcopy(FREEZE)
    manifest.update({
        "query_sha256": _canonical_sha256(queries),
        "gold_sha256": _canonical_sha256(gold),
        "prediction_freeze_manifest_sha256": FREEZE_HASH,
    })

    report = score_layered(queries, gold, predictions, manifest, "scoring-amendment")

    assert report["gate"]["passed"] is True
