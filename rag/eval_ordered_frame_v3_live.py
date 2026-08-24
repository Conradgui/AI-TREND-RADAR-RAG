"""Run the fixed three-case, already-unsealed regression canary for v3."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from jsonschema import Draft202012Validator

from rag import config
from rag.ordered_frame_client_v3 import (
    DeepSeekOrderedFrameModelV3,
    OrderedFrameClientV3,
    prompt_sha256_v3,
)
from rag.ordered_semantic_frame_v3 import build_ordered_route_envelope_v3
from rag.route_contract_validation import validate_route_contract_semantics


ROOT = Path(__file__).resolve().parents[1]
ROUTE_SCHEMA = json.loads(
    (ROOT / "docs/rag-transformation/specs/route-contract-v2.schema.json").read_text()
)

CANARY_CASES = (
    {
        "case_id": "blind-014-regression",
        "query": "先比较 Atlas 3 与 Atlas 3.2 的能力差异，再定位两条对应记录并给出原始链接",
        "scripted_frame": {
            "schema_version": "atr.ordered-semantic-frame/3.0",
            "deliveries": [
                {
                    "task_family": "evidence_research",
                    "evidence_spans": ["先比较 Atlas 3 与 Atlas 3.2 的能力差异"],
                    "requested_output_form": "comparison",
                    "locator_kind": "none",
                },
                {
                    "task_family": "item_navigation",
                    "evidence_spans": ["再定位两条对应记录并给出原始链接"],
                    "requested_output_form": "item_disambiguation",
                    "locator_kind": "descriptive",
                },
            ],
            "protected_spans": ["Atlas 3", "Atlas 3.2"],
            "web_permission": "on_demand",
            "web_evidence_spans": [],
            "unresolved_reference_spans": [],
        },
        "expected": {
            "primary": "evidence_research",
            "supporting": ["item_navigation"],
            "answer_mode": "comparison",
            "web_permission": "on_demand",
            "required_protected": ["Atlas 3", "Atlas 3.2"],
            "supporting_locator": "descriptive",
        },
    },
    {
        "case_id": "blind-008-regression",
        "query": "把过去三个月的浏览器端 AI 助手演变整理成时间线；必要时可以联网核对日期",
        "scripted_frame": {
            "schema_version": "atr.ordered-semantic-frame/3.0",
            "deliveries": [
                {
                    "task_family": "temporal_relation_exploration",
                    "evidence_spans": ["把过去三个月的浏览器端 AI 助手演变整理成时间线"],
                    "requested_output_form": "timeline",
                    "locator_kind": "none",
                }
            ],
            "protected_spans": ["过去三个月", "浏览器端 AI 助手"],
            "web_permission": "on_demand",
            "web_evidence_spans": ["必要时可以联网核对日期"],
            "unresolved_reference_spans": [],
        },
        "expected": {
            "primary": "temporal_relation_exploration",
            "supporting": [],
            "answer_mode": "timeline",
            "web_permission": "on_demand",
            "required_protected": ["过去三个月", "浏览器端 AI 助手"],
            "supporting_locator": None,
        },
    },
    {
        "case_id": "blind-010-regression",
        "query": "截至 2026 年 8 月 1 日，这个说法有证据支持吗：‘Nova R2 已经开源且允许商用’？禁止联网",
        "scripted_frame": {
            "schema_version": "atr.ordered-semantic-frame/3.0",
            "deliveries": [
                {
                    "task_family": "claim_verification",
                    "evidence_spans": ["这个说法有证据支持吗"],
                    "requested_output_form": "verification_verdict",
                    "locator_kind": "none",
                }
            ],
            "protected_spans": ["2026 年 8 月 1 日", "Nova R2 已经开源且允许商用", "禁止联网"],
            "web_permission": "forbidden",
            "web_evidence_spans": ["禁止联网"],
            "unresolved_reference_spans": [],
        },
        "expected": {
            "primary": "claim_verification",
            "supporting": [],
            "answer_mode": "verification_verdict",
            "web_permission": "forbidden",
            "required_protected": ["2026 年 8 月 1 日", "Nova R2 已经开源且允许商用", "禁止联网"],
            "supporting_locator": None,
        },
    },
)


def run_canary(extractor) -> dict:
    rows = []
    for case in CANARY_CASES:
        started = time.monotonic()
        try:
            frame, metadata = extractor.extract(case["query"])
            envelope = build_ordered_route_envelope_v3(case["query"], frame)
            contract = envelope.get("contract")
            if contract:
                Draft202012Validator(ROUTE_SCHEMA).validate(contract)
                validate_route_contract_semantics(contract)
            checks = _checks(case, envelope, metadata)
            error = None
        except Exception as exc:
            frame, envelope = None, None
            metadata = {"attempts": 1, "model": _model_name(extractor)}
            checks = {"single_attempt": True, "complete_contract": False}
            error = f"{type(exc).__name__}: {exc}"
        rows.append({
            "case_id": case["case_id"],
            "query": case["query"],
            "frame": frame,
            "envelope": envelope,
            "metadata": metadata,
            "latency_seconds": round(time.monotonic() - started, 3),
            "checks": checks,
            "error": error,
        })
        if error or not all(checks.values()):
            break

    latencies = [row["latency_seconds"] for row in rows]
    correct = sum(all(row["checks"].values()) for row in rows)
    mean_latency = round(sum(latencies) / len(latencies), 3) if latencies else 0
    max_latency = max(latencies, default=0)
    passed = (
        len(rows) == len(CANARY_CASES)
        and correct == len(CANARY_CASES)
        and mean_latency <= 8
        and max_latency <= 12
    )
    return {
        "experiment_id": "ordered-query-frame-v3-three-case-regression-canary-2026-08-16",
        "evidence_boundary": "Already-unsealed regression canary; not blind, production, or generalization evidence.",
        "model": _model_name(extractor),
        "prompt_sha256": prompt_sha256_v3(),
        "total": len(CANARY_CASES),
        "executed": len(rows),
        "complete_projection_correct": correct,
        "mean_latency_seconds": mean_latency,
        "max_latency_seconds": max_latency,
        "gate": {
            "passed": passed,
            "requirements": "3/3 complete projection; one attempt each; mean<=8s; max<=12s",
        },
        "cases": rows,
    }


def _checks(case: dict, envelope: dict, metadata: dict) -> dict:
    contract = envelope.get("contract") or {}
    expected = case["expected"]
    supporting_contracts = contract.get("supporting_contracts", [])
    locator = supporting_contracts[0].get("locator_kind") if supporting_contracts else None
    return {
        "single_attempt": metadata.get("attempts") == 1,
        "resolved": envelope.get("status") == "resolved",
        "primary": contract.get("primary_task_family") == expected["primary"],
        "supporting": contract.get("supporting_task_families") == expected["supporting"],
        "answer_mode": contract.get("answer_mode") == expected["answer_mode"],
        "web_permission": contract.get("web_permission") == expected["web_permission"],
        "protected_terms": set(expected["required_protected"]).issubset(
            contract.get("protected_terms", [])
        ),
        "supporting_locator": locator == expected["supporting_locator"],
        "complete_contract": bool(contract),
    }


def _model_name(extractor) -> str:
    model = getattr(extractor, "model", "unknown")
    nested = getattr(model, "model", None)
    return nested if isinstance(nested, str) else str(model)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if not config.DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    extractor = OrderedFrameClientV3(
        DeepSeekOrderedFrameModelV3(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            model=config.DEEPSEEK_MODEL,
        )
    )
    report = run_canary(extractor)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "executed": report["executed"],
        "complete_projection_correct": report["complete_projection_correct"],
        "mean_latency_seconds": report["mean_latency_seconds"],
        "max_latency_seconds": report["max_latency_seconds"],
        "gate": report["gate"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
