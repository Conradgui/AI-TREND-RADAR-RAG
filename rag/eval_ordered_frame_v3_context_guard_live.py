"""One-call live canary for deterministic Query-only protected-span sanitation."""

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
QUERY = "查找标题包含“端侧推理框架”的记录；如果有多个匹配项，列出候选"
CONTEXT = "用户上一条消息：左侧列表中上周新增的是融资新闻，右侧是评论摘录。"


def run_context_guard_canary(extractor) -> dict:
    started = time.monotonic()
    frame = envelope = None
    metadata = {"attempts": 1, "model": _model_name(extractor)}
    try:
        frame, metadata = extractor.extract(QUERY, CONTEXT)
        envelope = build_ordered_route_envelope_v3(QUERY, frame, CONTEXT)
        contract = envelope.get("contract")
        if contract:
            Draft202012Validator(ROUTE_SCHEMA).validate(contract)
            validate_route_contract_semantics(contract)
        checks = {
            "single_attempt": metadata.get("attempts") == 1,
            "resolved": envelope.get("status") == "resolved",
            "primary": (contract or {}).get("primary_task_family") == "item_navigation",
            "answer_mode": (contract or {}).get("answer_mode") == "item_disambiguation",
            "protected_query_only": all(
                term in QUERY for term in (contract or {}).get("protected_terms", [])
            ),
            "target_protected": "端侧推理框架" in (contract or {}).get("protected_terms", []),
        }
        error = None
    except Exception as exc:
        checks = {"single_attempt": True, "complete_contract": False}
        error = f"{type(exc).__name__}: {exc}"
    latency = round(time.monotonic() - started, 3)
    passed = not error and all(checks.values()) and latency <= 12
    return {
        "experiment_id": "ordered-query-frame-v3-context-guard-canary-2026-08-16",
        "evidence_boundary": "One new structural canary after an aborted visible calibration; not blind or production evidence.",
        "prompt_sha256": prompt_sha256_v3(),
        "model": _model_name(extractor),
        "gate": {"passed": passed, "requirements": "one attempt; valid A route; Query-only protected terms; <=12s"},
        "case": {
            "query": QUERY,
            "conversation_context": CONTEXT,
            "frame": frame,
            "envelope": envelope,
            "metadata": metadata,
            "latency_seconds": latency,
            "checks": checks,
            "error": error,
        },
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
    report = run_context_guard_canary(OrderedFrameClientV3(
        DeepSeekOrderedFrameModelV3(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            model=config.DEEPSEEK_MODEL,
        )
    ))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"gate": report["gate"], "latency_seconds": report["case"]["latency_seconds"], "error": report["case"]["error"]}, ensure_ascii=False, indent=2))
    if not report["gate"]["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
