"""Materialize the frozen 12-case SemanticParseV1 diagnostic slice."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_QUERIES = ROOT / "docs/rag-transformation/evals/route-contract-v2-sealed-generalization-queries-2026-08-13.json"
SOURCE_GOLD = ROOT / "docs/rag-transformation/evals/sealed/route-contract-v2-sealed-generalization-gold-2026-08-13.json"
OUTPUT_QUERIES = ROOT / "docs/rag-transformation/evals/semantic-parse-v1-diagnostic-queries-2026-08-13.json"
OUTPUT_GOLD = ROOT / "docs/rag-transformation/evals/semantic-parse-v1-diagnostic-gold-2026-08-13.json"

CASE_IDS = (
    "RC2-SG-001", "RC2-SG-004", "RC2-SG-006", "RC2-SG-009",
    "RC2-SG-014", "RC2-SG-017", "RC2-SG-020", "RC2-SG-026",
    "RC2-SG-031", "RC2-SG-034", "RC2-SG-039", "RC2-SG-050",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _select(path: Path) -> list[dict]:
    cases = {item["case_id"]: item for item in json.loads(path.read_text(encoding="utf-8"))["cases"]}
    if not all(case_id in cases for case_id in CASE_IDS):
        raise ValueError("diagnostic source is missing a frozen case")
    return [cases[case_id] for case_id in CASE_IDS]


def materialize() -> dict:
    query_cases = _select(SOURCE_QUERIES)
    gold_cases = _select(SOURCE_GOLD)
    query_asset = {
        "dataset_id": "semantic-parse-v1-diagnostic-calibration-2026-08-13",
        "purpose": "Frozen query-only 12-case diagnostic calibration; not a blind test.",
        "source_query_sha256": _sha256(SOURCE_QUERIES),
        "cases": query_cases,
    }
    gold_asset = {
        "dataset_id": query_asset["dataset_id"],
        "purpose": "Frozen calibration Gold selected before SemanticParseV1 implementation.",
        "source_gold_sha256": _sha256(SOURCE_GOLD),
        "cases": gold_cases,
    }
    OUTPUT_QUERIES.write_text(json.dumps(query_asset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT_GOLD.write_text(json.dumps(gold_asset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "query_path": str(OUTPUT_QUERIES.relative_to(ROOT)),
        "query_sha256": _sha256(OUTPUT_QUERIES),
        "gold_path": str(OUTPUT_GOLD.relative_to(ROOT)),
        "gold_sha256": _sha256(OUTPUT_GOLD),
        "cases": len(query_cases),
    }


if __name__ == "__main__":
    print(json.dumps(materialize(), ensure_ascii=False, indent=2))
