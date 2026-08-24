"""Query-only runner for the once-only, already-unsealed v3 calibration."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from jsonschema import Draft202012Validator

from rag import config
from rag.ordered_frame_client_v3 import (
    DeepSeekOrderedFrameModelV3,
    OrderedFrameClientV3,
    build_strict_tool_v3,
    prompt_sha256_v3,
)
from rag.ordered_semantic_frame_v3 import build_ordered_route_envelope_v3
from rag.route_contract_validation import validate_route_contract_semantics


ROOT = Path(__file__).resolve().parents[1]
ROUTE_SCHEMA = json.loads(
    (ROOT / "docs/rag-transformation/specs/route-contract-v2.schema.json").read_text()
)


class FreezeViolation(RuntimeError):
    """Raised before any API call when the frozen experiment has drifted."""


def assert_public_query_path(query_path: Path) -> None:
    """Prevent the Query-only Runner from reading any sealed filesystem path."""
    if "sealed" in {part.lower() for part in query_path.resolve().parts}:
        raise FreezeViolation("query file must be public and outside sealed storage")


def verify_freeze_manifest(
    manifest_path: Path,
    *,
    root: Path = ROOT,
    verify_runtime: bool = True,
) -> dict:
    if "sealed" in {part.lower() for part in manifest_path.resolve().parts}:
        raise FreezeViolation("runner must not read a freeze manifest from sealed storage")
    manifest = json.loads(manifest_path.read_text())
    for artifact in manifest.get("runner_artifacts", []):
        path = root / artifact["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != artifact["sha256"]:
            raise FreezeViolation(f"artifact hash drift: {artifact['path']}")

    if verify_runtime:
        runtime = manifest["runtime"]
        actual_runtime = {
            "model": config.DEEPSEEK_MODEL,
            "base_url": config.DEEPSEEK_BASE_URL.rstrip("/"),
            "temperature": 0,
            "max_tokens": 900,
            "timeout_seconds": 20,
            "thinking": "disabled",
            "max_retries": 0,
            "attempts_per_case": 1,
        }
        if runtime != actual_runtime:
            raise FreezeViolation("runtime configuration drift")
        if manifest["prompt_sha256"] != prompt_sha256_v3():
            raise FreezeViolation("prompt hash drift")
        provider_schema = build_strict_tool_v3()["function"]["parameters"]
        if manifest["provider_schema_sha256"] != _canonical_sha256(provider_schema):
            raise FreezeViolation("provider schema hash drift")
    return manifest


def verify_frozen_queries(manifest: dict, query_document: dict) -> None:
    cases = query_document.get("cases", [])
    case_ids = [case.get("case_id") for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise FreezeViolation("query case IDs must be unique")
    if case_ids != manifest.get("case_order"):
        raise FreezeViolation("query case order drift")
    if _canonical_sha256(query_document) != manifest.get("query_sha256"):
        raise FreezeViolation("query hash drift")


def run_queries(
    query_document: dict,
    extractor,
    *,
    experiment_id: str = "ordered-query-frame-v3-visible-calibration-2026-08-16",
    evidence_boundary: str = "Query-only execution; the runner did not read Gold.",
) -> dict:
    query_dataset_id = _query_dataset_id(query_document)
    rows = []
    for case in query_document["cases"]:
        started = time.monotonic()
        try:
            frame, metadata = extractor.extract(
                case["query"], case.get("conversation_context")
            )
            envelope = build_ordered_route_envelope_v3(
                case["query"], frame, case.get("conversation_context")
            )
            contract = envelope.get("contract")
            if contract:
                Draft202012Validator(ROUTE_SCHEMA).validate(contract)
                validate_route_contract_semantics(contract)
            error = None
        except Exception as exc:
            frame, envelope = None, None
            metadata = {"attempts": 1, "model": _model_name(extractor)}
            error = f"{type(exc).__name__}: {exc}"
        rows.append({
            "case_id": case["case_id"],
            "query": case["query"],
            "frame": frame,
            "envelope": envelope,
            "metadata": metadata,
            "latency_seconds": round(time.monotonic() - started, 3),
            "error": error,
        })
        if error:
            break

    return {
        "experiment_id": experiment_id,
        "evidence_boundary": evidence_boundary,
        "query_dataset_id": query_dataset_id,
        "query_sha256": _canonical_sha256(query_document),
        "model": _model_name(extractor),
        "planned": len(query_document["cases"]),
        "executed": len(rows),
        "cases": rows,
    }


def _query_dataset_id(query_document: dict) -> str:
    identifier = query_document.get("dataset_id") or query_document.get("shard_id")
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("query document requires a non-empty dataset_id or shard_id")
    return identifier


def _model_name(extractor) -> str:
    model = getattr(extractor, "model", "unknown")
    nested = getattr(model, "model", None)
    return nested if isinstance(nested, str) else str(model)


def _canonical_sha256(value: dict) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def report_failed(report: dict) -> bool:
    return (
        report.get("executed") != report.get("planned")
        or any(case.get("error") for case in report.get("cases", []))
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if not config.DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    manifest = verify_freeze_manifest(args.freeze_manifest)
    assert_public_query_path(args.queries)
    query_document = json.loads(args.queries.read_text())
    verify_frozen_queries(manifest, query_document)
    extractor = OrderedFrameClientV3(
        DeepSeekOrderedFrameModelV3(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            model=config.DEEPSEEK_MODEL,
        )
    )
    report = run_queries(
        query_document,
        extractor,
        experiment_id=manifest["experiment_id"],
        evidence_boundary=manifest["evidence_boundary"],
    )
    report["freeze_manifest_sha256"] = hashlib.sha256(
        args.freeze_manifest.read_bytes()
    ).hexdigest()
    report["frozen_runtime"] = manifest["runtime"]
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "planned": report["planned"],
        "executed": report["executed"],
        "errors": sum(bool(row["error"]) for row in report["cases"]),
    }, ensure_ascii=False, indent=2))
    if report_failed(report):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
