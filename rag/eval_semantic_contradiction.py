"""Deterministic semantic contradiction risk checks for chat snapshots."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from rag.eval_claim_level import UNCERTAINTY_MARKERS, load_snapshot_rows


DEFAULT_INPUT = Path("docs/rag-transformation/evals/hybrid-live-chat-snapshot-2026-06-23-after-filter.json")
DEFAULT_SEED = Path("docs/rag-transformation/evals/semantic-contradiction-seed-2026-06-24.json")
DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/semantic-contradiction-matrix-2026-06-24.json")

OVERCLAIM_MARKERS = (
    "已经证明",
    "证明了",
    "显著提升",
    "明确提升",
    "完全解决",
    "必然",
    "确定",
    "proven",
    "definitively",
    "significantly improves",
)


def load_semantic_contradiction_seed(path: Path) -> list[dict]:
    """Load semantic contradiction seed checks."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("checks"), list):
        return data["checks"]
    if isinstance(data, list):
        return data
    return []


def score_semantic_contradiction_rows(rows: list[dict], checks: list[dict]) -> list[dict]:
    """Score snapshot rows against deterministic contradiction-risk checks."""
    rows_by_id = {row.get("id"): row for row in rows}
    scored = []
    for check in checks:
        row = rows_by_id.get(check.get("question_id"))
        failed_checks = _failed_checks(row, check)
        scored.append({
            "id": check.get("id"),
            "question_id": check.get("question_id"),
            "label": check.get("label"),
            "passed": not failed_checks,
            "failed_checks": failed_checks,
            "answer_policy_mode": _answer_policy(row).get("mode", "") if row else "",
            "source_review_status": _source_review(row).get("status", "") if row else "",
            "external_citation_count": len(_external_citations(row or {})),
            "needs_conrad_review": bool(check.get("needs_conrad_review", True)),
        })
    return scored


def summarize_semantic_contradiction_rows(rows: list[dict]) -> dict:
    """Summarize semantic contradiction score rows."""
    failures = Counter()
    for row in rows:
        failures.update(row.get("failed_checks", []))
    total = len(rows)
    passed = sum(1 for row in rows if row.get("passed"))
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "failure_counts": dict(failures),
    }


def _failed_checks(row: dict | None, check: dict) -> list[str]:
    if not row:
        return ["question_row_missing"]

    label = check.get("label")
    if label == "source_status_requires_uncertainty":
        return _source_status_uncertainty_failures(row, check)
    if label == "forbid_overclaim_terms":
        return _overclaim_failures(row, check)
    if label == "external_claim_requires_external_citation":
        return _external_claim_failures(row, check)
    return ["unknown_semantic_contradiction_label"]


def _source_status_uncertainty_failures(row: dict, check: dict) -> list[str]:
    required_statuses = set(check.get("when_source_status_in") or [])
    source_status = _source_review(row).get("status", "")
    if required_statuses and source_status not in required_statuses:
        return []

    answer = row.get("answer") or ""
    markers = check.get("uncertainty_markers") or UNCERTAINTY_MARKERS
    failed = []
    if not _contains_any(answer, markers):
        failed.append("missing_uncertainty_for_source_status")
    if _contains_any(answer, check.get("overclaim_markers") or OVERCLAIM_MARKERS):
        failed.append("source_status_overclaim")
    return failed


def _overclaim_failures(row: dict, check: dict) -> list[str]:
    answer = row.get("answer") or ""
    if _contains_any(answer, check.get("answer_must_not_contain_any") or OVERCLAIM_MARKERS):
        return ["forbidden_overclaim_terms_present"]
    return []


def _external_claim_failures(row: dict, check: dict) -> list[str]:
    answer = row.get("answer") or ""
    trigger_terms = check.get("external_claim_terms_any") or []
    if trigger_terms and not _contains_any(answer, trigger_terms):
        return []

    min_external = check.get("min_external_citations", 1)
    if len(_external_citations(row)) >= min_external:
        return []

    if _contains_any(answer, check.get("uncertainty_markers") or UNCERTAINTY_MARKERS):
        return []

    return ["external_claim_without_external_citation_or_uncertainty"]


def _answer_policy(row: dict) -> dict:
    return row.get("query_understanding", {}).get("answer_policy", {}) or {}


def _source_review(row: dict) -> dict:
    return row.get("query_understanding", {}).get("source_review", {}) or {}


def _external_citations(row: dict) -> list[dict]:
    return [
        citation for citation in row.get("citations", [])
        if citation.get("evidence_type") == "external"
    ]


def _contains_any(text: str, needles: list[str] | tuple[str, ...]) -> bool:
    normalized = text.casefold()
    return any(str(needle).casefold() in normalized for needle in needles)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score deterministic semantic contradiction checks.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = load_snapshot_rows(args.input)
    checks = load_semantic_contradiction_seed(args.seed)
    scored = score_semantic_contradiction_rows(rows, checks)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "seed": str(args.seed),
        "summary": summarize_semantic_contradiction_rows(scored),
        "rows": scored,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
