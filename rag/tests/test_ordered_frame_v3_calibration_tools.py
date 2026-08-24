"""Offline tests for the separated v3 calibration runner and scorer."""

from __future__ import annotations

import hashlib
import json

import pytest

from rag.run_ordered_frame_v3_calibration import (
    FreezeViolation,
    assert_public_query_path,
    report_failed,
    run_queries,
    verify_frozen_queries,
    verify_freeze_manifest,
)
from rag.score_ordered_frame_v3_calibration import score_predictions, validate_assets


QUERIES = {
    "dataset_id": "fixture-queries",
    "cases": [
        {"case_id": "A", "query": "定位 ATR-20260814-A1B2C3"},
        {"case_id": "B", "query": "解释这个"},
    ],
}
GOLD = {
    "cases": [
        {
            "case_id": "A",
            "expected_status": "resolved",
            "expected_deliveries": [["item_navigation", "exact_item", "atr_id"]],
            "expected_protected_terms": ["ATR-20260814-A1B2C3"],
            "expected_web_permission": "on_demand",
        },
        {
            "case_id": "B",
            "expected_status": "clarification_required",
            "expected_deliveries": [],
            "expected_protected_terms": [],
            "expected_web_permission": "on_demand",
        },
    ]
}


class FixtureExtractor:
    model = "fixture"

    def extract(self, query: str, context=None):
        if query.startswith("定位"):
            frame = {
                "schema_version": "atr.ordered-semantic-frame/3.0",
                "deliveries": [{
                    "task_family": "item_navigation",
                    "evidence_spans": [query],
                    "requested_output_form": "exact_item",
                    "locator_kind": "atr_id",
                }],
                "protected_spans": ["ATR-20260814-A1B2C3"],
                "web_permission": "on_demand",
                "web_evidence_spans": [],
                "unresolved_reference_spans": [],
            }
        else:
            frame = {
                "schema_version": "atr.ordered-semantic-frame/3.0",
                "deliveries": [],
                "protected_spans": [],
                "web_permission": "on_demand",
                "web_evidence_spans": [],
                "unresolved_reference_spans": ["这个"],
            }
        return frame, {"attempts": 1, "total_tokens": 1}


def test_runner_uses_queries_only_and_scorer_accepts_perfect_projection() -> None:
    predictions = run_queries(QUERIES, FixtureExtractor())

    validate_assets(QUERIES, GOLD)
    report = score_predictions(QUERIES, GOLD, predictions)

    assert predictions["executed"] == 2
    assert report["metrics"]["ordered_deliveries_accuracy"] == 100
    assert report["metrics"]["protected_span_micro_f1"] == 100
    assert report["metrics"]["clarification_recall"] == 100
    assert report["metrics"]["frame_route_legal_rate"] == 100
    assert report["metrics"]["web_permission_accuracy"] == 100
    assert report["gate"]["passed"] is True


def test_freeze_manifest_rejects_artifact_drift(tmp_path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text('{"frozen": true}\n')
    manifest = {
        "runner_artifacts": [{
            "path": "artifact.json",
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        }],
    }
    manifest_path = tmp_path / "freeze.json"
    manifest_path.write_text(json.dumps(manifest))

    verify_freeze_manifest(manifest_path, root=tmp_path, verify_runtime=False)
    artifact.write_text('{"frozen": false}\n')

    with pytest.raises(FreezeViolation, match="hash drift"):
        verify_freeze_manifest(manifest_path, root=tmp_path, verify_runtime=False)


def test_runner_rejects_a_freeze_manifest_inside_sealed_directory(tmp_path) -> None:
    sealed = tmp_path / "sealed"
    sealed.mkdir()
    manifest_path = sealed / "freeze.json"
    manifest_path.write_text(json.dumps({"runner_artifacts": []}))

    with pytest.raises(FreezeViolation, match="sealed"):
        verify_freeze_manifest(manifest_path, root=tmp_path, verify_runtime=False)


def test_runner_rejects_a_query_file_inside_sealed_directory(tmp_path) -> None:
    query_path = tmp_path / "sealed" / "queries.json"
    query_path.parent.mkdir()
    query_path.write_text(json.dumps(QUERIES))

    with pytest.raises(FreezeViolation, match="public and outside sealed"):
        assert_public_query_path(query_path)


def test_frozen_query_order_and_hash_are_enforced_before_calls() -> None:
    manifest = {
        "case_order": ["A", "B"],
        "query_sha256": "wrong",
    }

    with pytest.raises(FreezeViolation, match="query hash drift"):
        verify_frozen_queries(manifest, QUERIES)


def test_scorer_rejects_reordered_or_duplicate_predictions() -> None:
    predictions = run_queries(QUERIES, FixtureExtractor())
    predictions["cases"].reverse()

    with pytest.raises(ValueError, match="prediction case IDs"):
        score_predictions(QUERIES, GOLD, predictions)


def test_runner_report_is_failed_when_execution_stops_early() -> None:
    report = {"planned": 2, "executed": 1, "cases": [{"error": "boom"}]}

    assert report_failed(report) is True


def test_runner_accepts_a_sealed_shard_identifier_before_extraction() -> None:
    shard_queries = {**QUERIES, "shard_id": "sealed-shard", "dataset_id": None}

    predictions = run_queries(shard_queries, FixtureExtractor())

    assert predictions["query_dataset_id"] == "sealed-shard"


def test_runner_rejects_a_query_document_without_an_identifier_before_calls() -> None:
    class MustNotRun:
        def extract(self, query: str, context=None):
            raise AssertionError("extractor must not be called")

    anonymous_queries = {"cases": QUERIES["cases"]}

    with pytest.raises(ValueError, match="dataset_id or shard_id"):
        run_queries(anonymous_queries, MustNotRun())
