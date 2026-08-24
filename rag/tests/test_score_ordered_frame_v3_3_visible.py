"""Contract-level TDD tests for the v3.3 visible calibration scorer."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from rag.ordered_semantic_frame_v3 import build_ordered_route_envelope_v3
from rag.score_ordered_frame_v3_3_visible import (
    score_visible_contract_calibration,
    verify_visible_scoring_freeze,
)
from rag.run_ordered_frame_v3_calibration import _canonical_sha256


QUERY = {
    "schema_version": "atr.visible-query/3.3",
    "dataset_id": "v33-visible-fixture",
    "cases": [
        {
            "case_id": "supporting-navigation",
            "query": "按顺序梳理苍穹编排器的里程碑，并定位《苍穹编排器发布说明》。",
            "conversation_context": None,
        }
    ],
}

FRAME = {
    "schema_version": "atr.ordered-semantic-frame/3.0",
    "deliveries": [
        {
            "task_family": "temporal_relation_exploration",
            "evidence_spans": ["按顺序梳理苍穹编排器的里程碑"],
            "requested_output_form": "timeline",
            "locator_kind": "none",
        },
        {
            "task_family": "item_navigation",
            "evidence_spans": ["定位《苍穹编排器发布说明》"],
            "requested_output_form": "exact_item",
            "locator_kind": "full_title",
        },
    ],
    "protected_spans": ["苍穹编排器", "《苍穹编排器发布说明》"],
    "web_permission": "on_demand",
    "web_evidence_spans": [],
    "unresolved_reference_spans": [],
}

GOLD = {
    "schema_version": "atr.visible-gold/3.3",
    "dataset_id": "v33-visible-fixture",
    "cases": [
        {
            "case_id": "supporting-navigation",
            "expected_status": "resolved",
            "expected_deliveries": [
                ["temporal_relation_exploration", "timeline", "none"],
                ["item_navigation", "exact_item", "full_title"],
            ],
            "expected_contract_literals": [
                {"path": "protected_terms", "literal": "苍穹编排器", "match": "exact"}
            ],
            "expected_web_permission": "on_demand",
        }
    ],
}


def _predictions(frame: dict | None = None) -> dict:
    actual_frame = deepcopy(frame or FRAME)
    query = QUERY["cases"][0]["query"]
    return {
        "experiment_id": "fixture",
        "planned": 1,
        "executed": 1,
        "cases": [
            {
                "case_id": "supporting-navigation",
                "query": query,
                "frame": actual_frame,
                "envelope": build_ordered_route_envelope_v3(query, actual_frame),
                "metadata": {"attempts": 1},
                "latency_seconds": 1.0,
                "error": None,
            }
        ],
    }


def test_perfect_supporting_navigation_is_product_complete() -> None:
    report = score_visible_contract_calibration(QUERY, GOLD, _predictions())

    assert report["cases"][0]["checks"]["supporting_navigation_contract"] is True
    assert report["cases"][0]["checks"]["product_complete"] is True
    assert report["gate"]["passed"] is True


def test_degraded_supporting_locator_fails_the_case() -> None:
    predictions = _predictions()
    supporting = predictions["cases"][0]["envelope"]["contract"]["supporting_contracts"][0]
    supporting["locator_kind"] = "title_fragment"
    supporting["requested_output_form"] = "item_disambiguation"

    report = score_visible_contract_calibration(QUERY, GOLD, predictions)

    assert report["cases"][0]["checks"]["supporting_navigation_contract"] is False
    assert report["cases"][0]["checks"]["product_complete"] is False
    assert report["gate"]["passed"] is False


def test_scorer_orders_correct_above_degraded_above_wrong() -> None:
    perfect = score_visible_contract_calibration(QUERY, GOLD, _predictions())
    degraded_predictions = _predictions()
    supporting = degraded_predictions["cases"][0]["envelope"]["contract"]["supporting_contracts"][0]
    supporting["locator_kind"] = "title_fragment"
    supporting["requested_output_form"] = "item_disambiguation"
    degraded = score_visible_contract_calibration(QUERY, GOLD, degraded_predictions)
    wrong_predictions = _predictions()
    wrong_predictions["cases"][0].update(
        frame=None,
        envelope=None,
        error="provider failure",
    )
    wrong = score_visible_contract_calibration(QUERY, GOLD, wrong_predictions)

    assert (
        perfect["cases"][0]["contract_completion_pct"]
        > degraded["cases"][0]["contract_completion_pct"]
        > wrong["cases"][0]["contract_completion_pct"]
    )


def test_literal_in_wrong_contract_field_does_not_receive_credit() -> None:
    predictions = _predictions()
    contract = predictions["cases"][0]["envelope"]["contract"]
    contract["protected_terms"].remove("苍穹编排器")
    contract["claims"].append("苍穹编排器")

    report = score_visible_contract_calibration(QUERY, GOLD, predictions)

    assert report["cases"][0]["contract_literal_checks"][0]["matched"] is False
    assert report["cases"][0]["checks"]["contract_critical_terms"] is False


def test_amount_literal_can_be_preserved_inside_a_larger_protected_phrase() -> None:
    gold = deepcopy(GOLD)
    gold["cases"][0]["expected_contract_literals"] = [
        {"path": "protected_terms", "literal": "40%", "match": "substring"}
    ]
    predictions = _predictions()
    contract = predictions["cases"][0]["envelope"]["contract"]
    contract["protected_terms"].append("推理成本降低 40%")
    predictions["cases"][0]["frame"]["protected_spans"].append("推理成本降低 40%")

    report = score_visible_contract_calibration(QUERY, gold, predictions)

    assert report["cases"][0]["contract_literal_checks"][0]["matched"] is True


def test_clarification_requires_a_null_contract() -> None:
    query = {
        "dataset_id": "clarification",
        "cases": [{"case_id": "clarify", "query": "这个说法是否成立？", "conversation_context": None}],
    }
    gold = {
        "dataset_id": "clarification",
        "cases": [{
            "case_id": "clarify",
            "expected_status": "clarification_required",
            "expected_deliveries": [["claim_verification", "verification_verdict", "none"]],
            "expected_contract_literals": [],
            "expected_web_permission": "on_demand",
        }],
    }
    frame = {
        "schema_version": "atr.ordered-semantic-frame/3.0",
        "deliveries": [{
            "task_family": "claim_verification",
            "evidence_spans": ["这个说法是否成立"],
            "requested_output_form": "verification_verdict",
            "locator_kind": "none",
        }],
        "protected_spans": [],
        "web_permission": "on_demand",
        "web_evidence_spans": [],
        "unresolved_reference_spans": ["这个说法"],
    }
    envelope = build_ordered_route_envelope_v3(query["cases"][0]["query"], frame)
    assert envelope["contract"] is None
    bad_envelope = deepcopy(envelope)
    bad_envelope["contract"] = {"primary_task_family": "claim_verification"}
    predictions = {
        "planned": 1,
        "executed": 1,
        "cases": [{
            "case_id": "clarify",
            "query": query["cases"][0]["query"],
            "frame": frame,
            "envelope": bad_envelope,
            "metadata": {"attempts": 1},
            "latency_seconds": 1.0,
            "error": None,
        }],
    }

    report = score_visible_contract_calibration(query, gold, predictions)

    assert report["cases"][0]["checks"]["status_and_contract_shape"] is False
    assert report["cases"][0]["checks"]["product_complete"] is False


def test_scoring_freeze_rejects_gold_drift_before_scoring(tmp_path) -> None:
    scorer = tmp_path / "scorer.py"
    scorer.write_text("frozen = True\n")
    manifest = {
        "query_sha256": _canonical_sha256(QUERY),
        "gold_sha256": _canonical_sha256(GOLD),
        "scoring_artifacts": [{
            "path": "scorer.py",
            "sha256": hashlib.sha256(scorer.read_bytes()).hexdigest(),
        }],
    }
    manifest_path = tmp_path / "freeze.json"
    manifest_path.write_text(json.dumps(manifest))
    predictions = _predictions()
    predictions["freeze_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    drifted_gold = deepcopy(GOLD)
    drifted_gold["cases"][0]["expected_web_permission"] = "forbidden"

    with pytest.raises(ValueError, match="Gold hash mismatch"):
        verify_visible_scoring_freeze(
            manifest_path, QUERY, drifted_gold, predictions, root=tmp_path
        )
