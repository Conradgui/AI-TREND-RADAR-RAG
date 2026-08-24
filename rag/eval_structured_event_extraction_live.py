"""Run the five-record DeepSeek semantic extraction smoke test."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from rag.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from rag.structured_event_extraction import (
    DeepSeekSemanticEventClient,
    SYSTEM_PROMPT,
    extract_semantic_event,
)


SEMANTIC_FIELDS = (
    "content_kind", "event_type", "subject_entity_ids", "mentioned_entity_ids",
)


def score_predictions(predictions: list[dict], annotations: list[dict]) -> dict:
    expected = {row["daily_item_id"]: row for row in annotations}
    fields = {}
    for field in SEMANTIC_FIELDS:
        correct = 0
        errors = []
        for row in predictions:
            wanted = expected[row["daily_item_id"]].get(field)
            observed = row.get(field)
            if field.endswith("_entity_ids"):
                wanted = sorted(wanted or [])
                observed = sorted(observed or [])
            passed = wanted == observed
            correct += int(passed)
            if not passed:
                errors.append({
                    "daily_item_id": row["daily_item_id"],
                    "expected": wanted,
                    "observed": observed,
                })
        fields[field] = {
            "correct": correct,
            "total": len(predictions),
            "accuracy": round(correct / len(predictions), 4) if predictions else 0.0,
            "errors": errors,
        }
    exact = sum(
        all(not fields[field]["errors"] or not any(
            error["daily_item_id"] == row["daily_item_id"]
            for error in fields[field]["errors"]
        ) for field in SEMANTIC_FIELDS)
        for row in predictions
    )
    valid = sum(row.get("extraction_status") == "extracted" for row in predictions)
    return {
        "record_count": len(predictions),
        "valid_contract_count": valid,
        "valid_contract_rate": round(valid / len(predictions), 4) if predictions else 0.0,
        "exact_record_count": exact,
        "exact_record_rate": round(exact / len(predictions), 4) if predictions else 0.0,
        "fields": fields,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not DEEPSEEK_API_KEY:
        raise SystemExit("DEEPSEEK_API_KEY is not configured")
    documents = json.loads(args.source.read_text(encoding="utf-8"))["documents"]
    dataset_bytes = args.dataset.read_bytes()
    dataset = json.loads(dataset_bytes)
    annotations = [
        row for row in dataset["annotations"]
        if row.get("label_confidence") == "high"
    ]
    by_id = {row["daily_item_id"]: row for row in documents}
    client = DeepSeekSemanticEventClient(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        model=DEEPSEEK_MODEL,
    )
    predictions = []
    for annotation in annotations:
        identity = annotation["daily_item_id"]
        started = time.monotonic()
        try:
            result = extract_semantic_event(by_id[identity], client)
            error = None
        except Exception as exc:
            result = {
                "content_kind": "unknown", "event_type": "unknown",
                "subject_entity_ids": [], "mentioned_entity_ids": [],
                "extraction_status": "needs_review", "diagnostics": ["client_error"],
            }
            error = f"{type(exc).__name__}: {str(exc)[:300]}"
        predictions.append({
            "daily_item_id": identity,
            **result,
            "latency_seconds": round(time.monotonic() - started, 3),
            "error": error,
        })
    scored = score_predictions(predictions, annotations)
    payload = {
        "experiment": "structured-llm-event-smoke-v1",
        "provider": "deepseek",
        "model": DEEPSEEK_MODEL,
        "sample_policy": "high_confidence_only",
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "predictions": predictions,
        **scored,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "valid_contract_rate": scored["valid_contract_rate"],
        "exact_record_rate": scored["exact_record_rate"],
        "fields": {key: value["accuracy"] for key, value in scored["fields"].items()},
        "errors": sum(bool(row["error"]) for row in predictions),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
