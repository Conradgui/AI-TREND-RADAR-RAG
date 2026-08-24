"""Run the fixed three-case Lean Task Atom API canary."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from rag.lean_task_atom_client import LeanTaskAtomClient, prompt_sha256
from rag.lean_task_atom_v1 import project_lean_task_atoms
from rag.route_contract_scoring import score_protected_terms
from rag.route_contract_validation import validate_route_contract_semantics


CASE_IDS = ("RC2-SG-017", "RC2-SG-020", "RC2-SG-039")


def run(queries_path: Path, gold_path: Path, client) -> dict:
    queries = {x["case_id"]: x for x in json.loads(queries_path.read_text())["cases"]}
    gold = {x["case_id"]: x for x in json.loads(gold_path.read_text())["cases"]}
    rows = []
    for case_id in CASE_IDS:
        case, expected = queries[case_id], gold[case_id]
        started = time.monotonic(); value = contract = usage = None; error = None
        try:
            value, usage = client.extract(case["query"], case.get("conversation_context"))
            contract = project_lean_task_atoms(case["query"], case.get("conversation_context"), value).to_dict()
            validate_route_contract_semantics(contract)
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:500]}"
            usage = getattr(exc, "diagnostics", None)
        latency = round(time.monotonic() - started, 3)
        if contract:
            protected = score_protected_terms(contract["protected_terms"], expected["expected_protected_terms"])
            checks = {
                "schema_semantic": True,
                "route": contract["primary_task_family"] == expected["primary_task_family"],
                "answer_mode": contract["answer_mode"] == expected["answer_mode"],
                "supporting": contract["supporting_task_families"] == expected["supporting_task_families"],
                "references": contract["resolved_references"] == expected["expected_resolved_references"],
                "protected_terms": protected.f1 == 1,
            }
        else:
            checks = {key: False for key in ("schema_semantic", "route", "answer_mode", "supporting", "references", "protected_terms")}
        rows.append({"case_id": case_id, "value": value, "contract": contract, "usage": usage, "latency_seconds": latency, "error": error, "checks": checks})
    latencies = [r["latency_seconds"] for r in rows]
    completion = [(r["usage"] or {}).get("completion_tokens", 0) for r in rows]
    semantic_correct = sum(all(r["checks"].values()) for r in rows)
    result = {
        "experiment_id": "lean-task-atom-v1-strict-three-case-canary-2026-08-13",
        "evidence_boundary": "Three-case calibration canary; not blind or production evidence.",
        "provider": "deepseek", "model": getattr(client, "model", "unknown"),
        "request_mode": getattr(client, "request_mode", "unknown"),
        "thinking": "disabled", "strict_function_call": True,
        "temperature": 0, "max_tokens": 800, "timeout_seconds": 45, "max_retries": 0,
        "prompt_sha256": prompt_sha256(), "total": 3,
        "schema_semantic_valid": sum(r["checks"]["schema_semantic"] for r in rows),
        "semantic_and_projection_correct": semantic_correct,
        "mean_latency_seconds": round(sum(latencies)/3, 3), "max_latency_seconds": max(latencies),
        "mean_completion_tokens": round(sum(completion)/3, 2),
        "total_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in rows),
        "gate": {
            "passed": semantic_correct == 3 and sum(r["checks"]["schema_semantic"] for r in rows) == 3
                and sum(latencies)/3 <= 8 and max(latencies) <= 12 and sum(completion)/3 <= 600,
            "requirements": "3/3 schema+semantic+projection; mean<=8s; max<=12s; mean completion<=600",
        },
        "cases": rows,
    }
    return result


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--queries",type=Path,required=True); parser.add_argument("--gold",type=Path,required=True); parser.add_argument("--output",type=Path,required=True); args=parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    client=LeanTaskAtomClient(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.environ["DEEPSEEK_MODEL"],
    )
    report=run(args.queries,args.gold,client); args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("schema_semantic_valid","semantic_and_projection_correct","mean_latency_seconds","max_latency_seconds","mean_completion_tokens","total_tokens","gate")},ensure_ascii=False,indent=2))


if __name__ == "__main__": main()
