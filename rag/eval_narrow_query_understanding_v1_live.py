"""Run the fixed three-case live dimensions-only L1 v2 canary."""

from __future__ import annotations

import argparse
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
from rag.narrow_route_contract_v2 import build_narrow_route_envelope


CASE_IDS = ("NSD-003", "NSD-007", "NSD-009")


def run(dataset_path: Path, extractor, case_ids: tuple[str, ...] | None = CASE_IDS) -> dict:
    cases = {
        case["case_id"]: case
        for case in json.loads(dataset_path.read_text())["cases"]
    }
    rows = []
    selected_case_ids = case_ids or tuple(cases)
    for case_id in selected_case_ids:
        case = cases[case_id]
        expected_envelope = build_narrow_route_envelope(
            case["query"], _gold_l1(case), case.get("conversation_context")
        )
        started = time.monotonic()
        envelope = _json_safe(understand_narrow_query_v1(
            case["query"], extractor, case.get("conversation_context")
        ))
        latency = round(time.monotonic() - started, 3)
        expected_status = expected_envelope["status"]
        contract = envelope.get("contract")
        expected_contract = expected_envelope.get("contract")
        checks = {
            "status": envelope["status"] == expected_status,
            "route": (
                (contract or {}).get("primary_task_family")
                == (expected_contract or {}).get("primary_task_family")
                if expected_status == "resolved"
                else contract is None
            ),
            "supporting": (
                (contract or {}).get("supporting_task_families")
                == (expected_contract or {}).get("supporting_task_families")
                if expected_status == "resolved"
                else contract is None
            ),
            "answer_mode": (
                (contract or {}).get("answer_mode")
                == (expected_contract or {}).get("answer_mode")
                if expected_status == "resolved"
                else contract is None
            ),
            "protected_terms": (
                (contract or {}).get("protected_terms")
                == (expected_contract or {}).get("protected_terms")
                if expected_status == "resolved"
                else True
            ),
            "references": (
                (contract or {}).get("resolved_references")
                == (expected_contract or {}).get("resolved_references")
                if expected_status == "resolved"
                else True
            ),
            "web_permission": (
                (contract or {}).get("web_permission")
                == (expected_contract or {}).get("web_permission")
                if expected_status == "resolved"
                else True
            ),
        }
        rows.append({
            "case_id": case_id,
            "query": case["query"],
            "expected_status": expected_status,
            "envelope": envelope,
            "latency_seconds": latency,
            "checks": checks,
        })
    latencies = [row["latency_seconds"] for row in rows]
    correct = sum(all(row["checks"].values()) for row in rows)
    mean_latency = round(sum(latencies) / len(latencies), 3)
    model_name = _model_name(extractor)
    experiment_kind = (
        "visible-calibration" if len(rows) == len(cases)
        else "three-case-canary" if tuple(selected_case_ids) == CASE_IDS
        else "targeted-diagnostic"
    )
    return {
        "experiment_id": f"dimensions-only-l1-v2-{experiment_kind}-2026-08-15",
        "evidence_boundary": "Visible three-case calibration canary; not blind or production evidence.",
        "provider": "deepseek" if model_name != "fixture" else "fixture",
        "model": model_name,
        "prompt_sha256": prompt_sha256(),
        "total": len(rows),
        "complete_projection_correct": correct,
        "mean_latency_seconds": mean_latency,
        "max_latency_seconds": max(latencies),
        "gate": {
            "passed": correct == len(rows) and mean_latency <= 8 and max(latencies) <= 12,
            "requirements": f"{len(rows)}/{len(rows)} complete projection; mean<=8s; max<=12s",
        },
        "cases": rows,
    }


def _model_name(extractor) -> str:
    model = getattr(extractor, "model", "unknown")
    nested = getattr(model, "model", None)
    if isinstance(nested, str):
        return nested
    return model if isinstance(model, str) else type(model).__name__


def _gold_l1(case: dict) -> dict:
    dimension_names = (
        "item_lookup",
        "recent_update_set",
        "cross_time_or_entity_structure",
        "truth_assessable_claim",
        "explanation_or_comparison",
    )
    dimensions = {}
    for name in dimension_names:
        if name in case["present"]:
            state, spans = "present", case["present"][name]
        elif name in case["uncertain"]:
            state, spans = "uncertain", case["uncertain"][name]
        else:
            state, spans = "absent", []
        dimensions[name] = {"state": state, "evidence_spans": spans}
    return {
        "schema_version": "atr.semantic-decisions/1.0",
        "dimensions": dimensions,
        "protected_spans": case.get("protected_spans", []),
        "item_locator_precision": case.get("item_locator_precision", "none"),
        "unresolved_reference_spans": case["unresolved_reference_spans"],
        "resolved_references": case.get("resolved_references", []),
    }


def _json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    nested = getattr(value, "model", None)
    return nested if isinstance(nested, str) else type(value).__name__


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--all-visible", action="store_true")
    parser.add_argument("--case-id", action="append", default=[])
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    model = DeepSeekNarrowDecisionModel(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
    )
    extractor = NarrowDecisionClient(model)
    selected = tuple(args.case_id) if args.case_id else (
        None if args.all_visible else CASE_IDS
    )
    report = run(args.dataset, extractor, case_ids=selected)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        key: report[key]
        for key in (
            "complete_projection_correct",
            "mean_latency_seconds",
            "max_latency_seconds",
            "gate",
        )
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
