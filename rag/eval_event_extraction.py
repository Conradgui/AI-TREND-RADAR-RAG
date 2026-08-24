"""Field-level evaluation for the offline event extraction prototype."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rag.event_extraction import extract_event_batch
from rag.event_contract import CONTRACT_VERSION, canonicalize_expected


FIELDS = (
    "content_kind", "source_role", "event_type", "subject_entity_ids",
    "mentioned_entity_ids", "publication_date", "temporal_confidence",
)


def evaluate_predictions(documents: list[dict], annotations: list[dict]) -> dict:
    selected = {row["daily_item_id"]: row for row in documents}
    source = [selected[row["daily_item_id"]] for row in annotations]
    annotations = [canonicalize_expected(row, selected[row["daily_item_id"]]) for row in annotations]
    predicted = {row["daily_item_id"]: row for row in extract_event_batch(source)}
    field_rows = {}
    for field in FIELDS:
        correct = 0
        details = []
        for expected in annotations:
            identity = expected["daily_item_id"]
            observed = predicted[identity].get(field)
            wanted = expected.get(field)
            if wanted is None and field == "source_role":
                continue
            if field.endswith("_entity_ids"):
                observed = sorted(observed or [])
                wanted = sorted(wanted or [])
            passed = observed == wanted
            correct += int(passed)
            details.append({
                "daily_item_id": identity,
                "expected": wanted,
                "observed": observed,
                "passed": passed,
            })
        total = len(details)
        field_rows[field] = {
            "correct": correct,
            "total": total,
            "accuracy": round(correct / total, 4) if total else None,
            "errors": [row for row in details if not row["passed"]],
        }
    exact = 0
    for expected in annotations:
        observed = predicted[expected["daily_item_id"]]
        record_matches = True
        for field in FIELDS:
            actual_value = observed.get(field)
            expected_value = expected.get(field)
            if expected_value is None and field == "source_role":
                continue
            if field.endswith("_entity_ids"):
                actual_value = sorted(actual_value or [])
                expected_value = sorted(expected_value or [])
            record_matches = record_matches and actual_value == expected_value
        exact += int(record_matches)
    non_news = [row for row in annotations if row.get("content_kind") != "news"]
    false_news = sum(
        1 for row in non_news
        if predicted[row["daily_item_id"]].get("content_kind") == "news"
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "semantic_extraction_fields": [
            "content_kind", "source_role", "event_type",
            "subject_entity_ids", "mentioned_entity_ids",
        ],
        "source_fact_checks": ["publication_date", "temporal_confidence"],
        "quality_metrics": {
            "non_news_false_admission_count": false_news,
            "non_news_record_count": len(non_news),
            "non_news_false_admission_rate": round(false_news / len(non_news), 4) if non_news else None,
        },
        "record_count": len(annotations),
        "exact_record_count": exact,
        "exact_record_rate": round(exact / len(annotations), 4) if annotations else 0.0,
        "fields": field_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.source.read_text(encoding="utf-8"))
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    documents = payload.get("documents", payload)
    result = evaluate_predictions(documents, dataset["annotations"])
    result["extractor_sha256"] = hashlib.sha256(
        Path(__file__).with_name("event_extraction.py").read_bytes()
    ).hexdigest()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "exact_record_rate": result["exact_record_rate"],
        "fields": {key: value["accuracy"] for key, value in result["fields"].items()},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
