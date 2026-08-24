"""Generate sealed predictions without reading blind gold labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

from rag.narrow_decision_client import (
    DeepSeekNarrowDecisionModel,
    NarrowDecisionClient,
    prompt_sha256,
)
from rag.narrow_query_understanding_v1 import understand_narrow_query_v1


ROOT = Path(__file__).resolve().parents[1]


def verify_freeze(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    for relative_path, expected in manifest["artifacts"].items():
        actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"frozen artifact changed: {relative_path}")
    if prompt_sha256() != manifest["prompt_sha256"]:
        raise RuntimeError("frozen prompt changed")
    return manifest


def run(query_path: Path, extractor, freeze_manifest: dict) -> dict:
    dataset = json.loads(query_path.read_text())
    rows = []
    for case in dataset["cases"]:
        started = time.monotonic()
        envelope = understand_narrow_query_v1(
            case["query"], extractor, case.get("conversation_context")
        )
        rows.append({
            "case_id": case["case_id"],
            "envelope": envelope,
            "latency_seconds": round(time.monotonic() - started, 3),
        })
    return {
        "experiment_id": "dimensions-only-l1-v2-unseen-blind-2026-08-15",
        "evidence_boundary": "Predictions produced without loading blind labels.",
        "freeze_id": freeze_manifest["freeze_id"],
        "prompt_sha256": prompt_sha256(),
        "query_set_sha256": hashlib.sha256(query_path.read_bytes()).hexdigest(),
        "model": _model_name(extractor),
        "cases": rows,
    }


def _model_name(extractor) -> str:
    model = getattr(extractor, "model", "unknown")
    nested = getattr(model, "model", None)
    return nested if isinstance(nested, str) else str(model)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    freeze = verify_freeze(args.freeze)
    model = DeepSeekNarrowDecisionModel(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
    )
    report = run(args.queries, NarrowDecisionClient(model), freeze)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "cases": len(report["cases"]),
        "model": report["model"],
        "freeze_id": report["freeze_id"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
