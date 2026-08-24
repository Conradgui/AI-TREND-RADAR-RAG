"""Generate immutable-style predictions without reading sealed Gold labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from rag.query_understanding_v2 import understand_query_v2


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUERIES = ROOT / "docs/rag-transformation/evals/route-contract-v2-challenge-queries-2026-08-13.json"
DEFAULT_OUTPUT = ROOT / "docs/rag-transformation/evals/route-contract-v2-challenge-baseline-2026-08-13.json"
UNDERSTANDER = Path(__file__).with_name("query_understanding_v2.py")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(queries_path: Path, prediction_id: str = "route-contract-v2-predictions") -> dict:
    if "sealed" in queries_path.parts:
        raise ValueError("blind baseline generator cannot read from a sealed path")

    dataset = json.loads(queries_path.read_text(encoding="utf-8"))
    predictions = []
    for case in dataset["cases"]:
        context = case.get("conversation_context")
        contract = understand_query_v2(case["query"], context).to_dict()
        prediction = {
            "case_id": case["case_id"],
            "query": case["query"],
            "prediction": contract,
        }
        if context is not None:
            prediction["conversation_context"] = context
        predictions.append(prediction)

    return {
        "prediction_id": prediction_id,
        "baseline_id": prediction_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "blind_protocol": "Generated from query-only file before the main implementer read sealed Gold.",
        "query_dataset_id": dataset["dataset_id"],
        "query_file_sha256": sha256(queries_path),
        "understander_file_sha256": sha256(UNDERSTANDER),
        "total_cases": len(predictions),
        "predictions": predictions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--prediction-id", default="route-contract-v2-predictions")
    args = parser.parse_args()

    if args.output.exists():
        raise FileExistsError(f"baseline already exists and will not be overwritten: {args.output}")

    report = generate(args.queries, prediction_id=args.prediction_id)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "prediction_id": report["prediction_id"],
                "total_cases": report["total_cases"],
                "query_file_sha256": report["query_file_sha256"],
                "understander_file_sha256": report["understander_file_sha256"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
