"""Offline test for the fixed three-case v3 canary evaluator."""

from __future__ import annotations

import json

from rag.eval_ordered_frame_v3_live import CANARY_CASES, run_canary


class ScriptedExtractor:
    model = "fixture"

    def __init__(self):
        self.calls = 0

    def extract(self, query: str, conversation_context: str | None = None):
        self.calls += 1
        case = next(case for case in CANARY_CASES if case["query"] == query)
        return case["scripted_frame"], {"attempts": 1, "total_tokens": 0}


def test_canary_evaluator_accepts_three_complete_scripted_projections() -> None:
    extractor = ScriptedExtractor()

    report = run_canary(extractor)

    assert extractor.calls == 3
    assert report["total"] == 3
    assert report["complete_projection_correct"] == 3
    assert report["gate"]["passed"] is True
    assert all(row["metadata"]["attempts"] == 1 for row in report["cases"])


class FailingExtractor:
    model = object()

    def __init__(self):
        self.calls = 0

    def extract(self, query: str, conversation_context: str | None = None):
        self.calls += 1
        raise ValueError("provider rejected schema")


def test_canary_stops_once_and_serializes_the_first_failure() -> None:
    extractor = FailingExtractor()

    report = run_canary(extractor)

    assert extractor.calls == 1
    assert report["executed"] == 1
    assert report["gate"]["passed"] is False
    assert "provider rejected schema" in report["cases"][0]["error"]
    json.dumps(report)
