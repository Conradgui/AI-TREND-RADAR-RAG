"""Readiness check for future external evidence ingestion."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from rag.external_evidence import build_web_search_unavailable_result, validate_external_citation


DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/external-evidence-readiness-2026-06-22.json")


def build_external_evidence_readiness() -> dict:
    """Build a deterministic readiness snapshot for external evidence contracts."""
    valid_external_citation = {
        "evidence_type": "external",
        "source": "Google Research",
        "title": "Example external source",
        "url": "https://research.google/example",
        "retrieved_at": "2026-06-22",
        "excerpt": "Example excerpt for schema validation.",
    }
    valid_errors = validate_external_citation(valid_external_citation)
    unavailable = build_web_search_unavailable_result("Google OKF ALM Wiki")

    failed_checks = []
    if valid_errors:
        failed_checks.append("valid_external_citation_failed_schema")
    if unavailable.get("available") is not False:
        failed_checks.append("web_search_unavailable_flag_missing")
    if unavailable.get("citations") != []:
        failed_checks.append("disabled_web_search_should_not_return_citations")
    if "外部证据" not in unavailable.get("user_message", ""):
        failed_checks.append("disabled_web_search_message_missing_external_label")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": not failed_checks,
        "failed_checks": failed_checks,
        "valid_external_citation_errors": valid_errors,
        "web_search": unavailable,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check external evidence schema readiness.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = build_external_evidence_readiness()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "passed": result["passed"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
