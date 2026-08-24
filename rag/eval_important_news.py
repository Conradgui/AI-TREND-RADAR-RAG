"""Offline product-rule calibration for the important-news retrieval path."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from rag.entity_identity import canonical_entity_id
from rag.retrieval_gateway import EvidenceRetrievalGateway, ResearchRequest


class _NoFallbackRetriever:
    async def search(self, *args, **kwargs):
        raise AssertionError("important-news calibration must use structured records")


class _CalibrationStore:
    def __init__(self, cases: list[dict]):
        self.cases = cases

    def search(self, *args, **kwargs):
        return []

    def recent(self, limit: int = 100, where: dict | None = None) -> list[dict]:
        records = []
        for case in self.cases:
            identity = str(case["id"])
            entity_id = canonical_entity_id(case["entity"])
            records.append({
                "text": case["summary"],
                "match_type": "browse",
                "metadata": {
                    "content_type": "topic_candidate",
                    "date": case["date"],
                    "effective_date": case["date"],
                    "source": case["entity"],
                    "title": case["title"],
                    "citation_id": identity,
                    "occurrence_id": identity,
                    "content_id": f"calibration-{identity}",
                    "entity_ids": [entity_id],
                    "local_url": f"#{case['date']}/calibration/item/{identity}",
                    "url": f"https://calibration.invalid/{identity}",
                    "score": case.get("score", 0),
                    "category": "calibration",
                    "summary": case["summary"],
                    "evidence": case["summary"],
                },
            })
        return records[:limit]


async def evaluate_dataset(dataset: dict) -> dict:
    cases = list(dataset.get("cases") or [])
    store = _CalibrationStore(cases)
    gateway = EvidenceRetrievalGateway(_NoFallbackRetriever(), structured_store=store)
    by_entity: dict[str, list[dict]] = defaultdict(list)
    for case in cases:
        by_entity[str(case["entity"])].append(case)

    rows = []
    for entity, entity_cases in by_entity.items():
        bundle = await gateway.retrieve(ResearchRequest(
            question=f"{entity} 最近有哪些重要动态？",
            latest_corpus_date=dataset.get("reference_date"),
            limit=max(10, len(entity_cases)),
        ))
        main_ids = {str(record.get("citation_id")) for record in bundle.records}
        background_ids = {
            str(record.get("citation_id")) for record in bundle.background_records
        }
        excluded_ids = set(bundle.trace.get("excluded_candidate_ids") or [])
        observed_by_id = {
            **{identity: "main" for identity in main_ids},
            **{identity: "background" for identity in background_ids},
            **{identity: "exclude" for identity in excluded_ids},
        }
        for case in entity_cases:
            observed = observed_by_id.get(case["id"], "missing")
            expected = case["expected_tier"]
            rows.append({
                "id": case["id"],
                "entity": entity,
                "title": case["title"],
                "expected_tier": expected,
                "observed_tier": observed,
                "passed": observed == expected,
            })

    passed = sum(row["passed"] for row in rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset.get("dataset_id"),
        "scope_limit": "Synthetic product-rule calibration; not a corpus Recall/F1 benchmark.",
        "summary": {
            "total": len(rows),
            "passed": passed,
            "failed": len(rows) - passed,
            "gate_passed": passed == len(rows),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate important-news product rules.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    result = asyncio.run(evaluate_dataset(dataset))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
