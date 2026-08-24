"""Safety tests for the query-only blind baseline generator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag.generate_route_contract_v2_blind_baseline import generate


def test_blind_generator_rejects_sealed_input(tmp_path: Path) -> None:
    sealed = tmp_path / "sealed" / "gold.json"
    sealed.parent.mkdir()
    sealed.write_text(json.dumps({"dataset_id": "secret", "cases": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="sealed"):
        generate(sealed)


def test_prediction_generator_uses_public_context_and_custom_run_id(tmp_path: Path) -> None:
    queries = tmp_path / "queries.json"
    queries.write_text(
        json.dumps(
            {
                "dataset_id": "fresh-blind",
                "cases": [
                    {
                        "case_id": "CTX-001",
                        "query": "解释它为什么重要",
                        "conversation_context": "current_item_id=ATR-20260812-AB12CD",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = generate(queries, prediction_id="fresh-run")

    assert report["prediction_id"] == "fresh-run"
    assert report["predictions"][0]["conversation_context"].endswith("AB12CD")
    assert report["predictions"][0]["prediction"]["resolved_references"][0]["value"].endswith("AB12CD")
