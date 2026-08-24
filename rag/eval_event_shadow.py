"""Compare legacy, subject-aware, and event-aware views on one frozen day."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from rag.event_shadow import apply_event_annotations
from rag.retrieval_gateway import EvidenceRetrievalGateway, ResearchRequest
from rag.retriever.lexical_store import LexicalStore


class _NoFallbackRetriever:
    async def search(self, *args, **kwargs):
        raise AssertionError("event shadow evaluation must use the structured store")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _view_documents(documents: list[dict], annotations: list[dict], version: str) -> list[dict]:
    if version == "v0_legacy_entity":
        return [dict(row) for row in documents]
    reviewed = apply_event_annotations(documents, annotations)
    if version == "v1_subject_roles":
        for row in reviewed:
            row["content_kind"] = ""
            row["event_type"] = ""
        return reviewed
    if version == "v2_event_contract":
        return reviewed
    raise ValueError(f"unknown view: {version}")


async def _evaluate_view(
    documents: list[dict], dataset: dict, version: str, index_path: Path
) -> dict:
    store = LexicalStore(index_path)
    try:
        store.rebuild(_view_documents(documents, dataset["annotations"], version))
        gateway = EvidenceRetrievalGateway(_NoFallbackRetriever(), structured_store=store)
        rows = []
        annotation_by_id = {
            row["daily_item_id"]: row for row in dataset["annotations"]
        }
        for query in dataset["evaluation_queries"]:
            bundle = await gateway.retrieve(ResearchRequest(
                question=query["query"],
                latest_corpus_date=dataset["report_date"],
                limit=20,
            ))
            observed_main = [str(row["citation_id"]) for row in bundle.records]
            expected_main = set(query["expected_main"])
            expected_exclude = set(query["expected_exclude"])
            observed_set = set(observed_main)
            observed_event_groups = [
                annotation_by_id.get(identity, {}).get("event_group_id")
                for identity in observed_main
            ]
            observed_event_groups = [group for group in observed_event_groups if group]
            duplicate_event_slots = len(observed_event_groups) - len(set(observed_event_groups))
            low_time_confidence_main = [
                identity for identity in observed_main
                if annotation_by_id.get(identity, {}).get("temporal_confidence") in {"low", "unknown"}
            ]
            true_positive = len(observed_set & expected_main)
            false_positive = len(observed_set - expected_main)
            false_negative = len(expected_main - observed_set)
            precision = true_positive / len(observed_set) if observed_set else 0.0
            recall = true_positive / len(expected_main) if expected_main else 1.0
            f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
            rows.append({
                "query": query["query"],
                "entity": query["entity"],
                "observed_main": observed_main,
                "expected_main": sorted(expected_main),
                "expected_exclude_in_main": sorted(observed_set & expected_exclude),
                "unexpected_main": sorted(observed_set - expected_main - expected_exclude),
                "duplicate_event_slots": duplicate_event_slots,
                "low_time_confidence_main": low_time_confidence_main,
                "metrics": {
                    "true_positive": true_positive,
                    "false_positive": false_positive,
                    "false_negative": false_negative,
                    "precision": round(precision, 4),
                    "recall": round(recall, 4),
                    "f1": round(f1, 4),
                    "duplicate_event_slots": duplicate_event_slots,
                    "low_time_confidence_main_count": len(low_time_confidence_main),
                },
                "entity_filter_mode": bundle.trace.get("entity_filter_mode"),
            })
        return {"version": version, "rows": rows}
    finally:
        store.close()


async def evaluate(source_path: Path, dataset_path: Path) -> dict:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    all_documents = payload.get("documents", []) if isinstance(payload, dict) else payload
    selected_ids = {row["daily_item_id"] for row in dataset["annotations"]}
    documents = [row for row in all_documents if row.get("daily_item_id") in selected_ids]
    if len(documents) != len(selected_ids):
        found = {row.get("daily_item_id") for row in documents}
        raise ValueError(f"source is missing frozen IDs: {sorted(selected_ids - found)}")

    with tempfile.TemporaryDirectory(prefix="atr-event-shadow-") as directory:
        root = Path(directory)
        versions = []
        for version in ("v0_legacy_entity", "v1_subject_roles", "v2_event_contract"):
            versions.append(await _evaluate_view(
                documents, dataset, version, root / f"{version}.sqlite3"
            ))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset["dataset_id"],
        "scope_limit": dataset["scope_limit"],
        "frozen_inputs": {
            "source_sha256": _sha256(source_path),
            "dataset_sha256": _sha256(dataset_path),
            "record_count": len(documents),
        },
        "versions": versions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a one-day event shadow view.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(evaluate(args.source, args.dataset))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        version["version"]: [row["metrics"] for row in version["rows"]]
        for version in result["versions"]
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
