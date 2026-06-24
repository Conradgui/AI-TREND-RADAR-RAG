"""Deterministic claim-level evaluation for chat answer snapshots."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_INPUT = Path("docs/rag-transformation/evals/hybrid-live-chat-snapshot-2026-06-23.json")
DEFAULT_SEED = Path("docs/rag-transformation/evals/claim-level-seed-2026-06-23.json")
DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/claim-level-matrix-2026-06-23.json")
UNCERTAINTY_MARKERS = (
    "证据不足",
    "无法确认",
    "缺乏",
    "尚无",
    "未提供",
    "不能确定",
    "无法就此给出明确结论",
    "无法判断",
    "无法确定",
    "没有直接提及",
    "not enough evidence",
    "insufficient evidence",
    "cannot confirm",
)


def load_snapshot_rows(path: Path) -> list[dict]:
    """Load rows from a chat snapshot file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        return data["rows"]
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def load_claim_seed(path: Path) -> list[dict]:
    """Load claim-level seed rows."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("claims"), list):
        return data["claims"]
    if isinstance(data, list):
        return data
    return []


def score_claim_level_rows(rows: list[dict], claims: list[dict]) -> list[dict]:
    """Score answer rows against claim-level seed rules."""
    rows_by_id = {row.get("id"): row for row in rows}
    scored = []
    for claim in claims:
        row = rows_by_id.get(claim.get("question_id"))
        failed_checks = _failed_checks(row, claim)
        scored.append({
            "id": claim.get("id"),
            "question_id": claim.get("question_id"),
            "label": claim.get("label"),
            "claim": claim.get("claim", ""),
            "passed": not failed_checks,
            "failed_checks": failed_checks,
            "citation_count": len((row or {}).get("citations", [])),
            "internal_citation_count": len(_internal_citations(row or {})),
            "external_citation_count": len(_external_citations(row or {})),
            "graph_citation_count": len(_graph_citations(row or {})),
            "needs_conrad_review": bool(claim.get("needs_conrad_review", True)),
        })
    return scored


def summarize_claim_level_rows(rows: list[dict]) -> dict:
    """Summarize claim-level score rows."""
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


def _failed_checks(row: dict | None, claim: dict) -> list[str]:
    if not row:
        return ["question_row_missing"]

    label = claim.get("label")
    answer = row.get("answer") or ""
    failed = []

    if label == "should_support":
        failed.extend(_support_failures(row, claim, answer))
    elif label == "should_avoid":
        failed.extend(_avoid_failures(claim, answer))
    elif label == "should_mark_uncertain":
        if not _contains_any(answer, claim.get("uncertainty_markers") or UNCERTAINTY_MARKERS):
            failed.append("missing_uncertainty_language")
    else:
        failed.append("unknown_claim_label")

    return failed


def _support_failures(row: dict, claim: dict, answer: str) -> list[str]:
    failed = []
    terms = claim.get("answer_must_contain_any") or []
    if terms and not _contains_any(answer, terms):
        failed.append("missing_answer_terms")

    forbidden_terms = claim.get("answer_must_not_contain_any") or []
    if forbidden_terms and _contains_any(answer, forbidden_terms):
        failed.append("forbidden_answer_terms_present")

    citations = row.get("citations") or []
    if len(citations) < claim.get("min_citations", 0):
        failed.append("insufficient_citations")
    if len(_external_citations(row)) < claim.get("min_external_citations", 0):
        failed.append("missing_external_citations")
    if len(_internal_citations(row)) < claim.get("min_internal_citations", 0):
        failed.append("missing_internal_citations")
    if len(_graph_citations(row)) < claim.get("min_graph_citations", 0):
        failed.append("missing_graph_citations")

    for citation_type in claim.get("required_citation_types") or []:
        if citation_type == "internal" and not _internal_citations(row):
            failed.append("missing_internal_citations")
        if citation_type == "external" and not _external_citations(row):
            failed.append("missing_external_citations")
        if citation_type == "graph" and not _graph_citations(row):
            failed.append("missing_graph_citations")

    required_quality = claim.get("required_source_quality_any") or []
    if required_quality and not _has_external_source_quality(row, set(required_quality)):
        failed.append("missing_required_source_quality")

    return sorted(set(failed))


def _avoid_failures(claim: dict, answer: str) -> list[str]:
    if _contains_any(answer, claim.get("answer_must_not_contain_any") or []):
        return ["forbidden_answer_terms_present"]
    return []


def _contains_any(text: str, needles: list[str] | tuple[str, ...]) -> bool:
    normalized = text.casefold()
    return any(needle.casefold() in normalized for needle in needles)


def _internal_citations(row: dict) -> list[dict]:
    return [
        citation for citation in row.get("citations", [])
        if citation.get("evidence_type", "internal") == "internal"
    ]


def _external_citations(row: dict) -> list[dict]:
    return [
        citation for citation in row.get("citations", [])
        if citation.get("evidence_type") == "external"
    ]


def _graph_citations(row: dict) -> list[dict]:
    return [
        citation for citation in _internal_citations(row)
        if "/graph-topic/" in citation.get("citation_id", "")
    ]


def _has_external_source_quality(row: dict, required: set[str]) -> bool:
    return any(
        citation.get("source_quality") in required
        for citation in _external_citations(row)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score claim-level checks for a chat snapshot.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = load_snapshot_rows(args.input)
    claims = load_claim_seed(args.seed)
    scored = score_claim_level_rows(rows, claims)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "seed": str(args.seed),
        "summary": summarize_claim_level_rows(scored),
        "rows": scored,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
