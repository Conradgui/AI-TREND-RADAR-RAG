"""Lightweight rubric for answer-policy compliance in live chat snapshots."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_INPUT = Path("docs/rag-transformation/evals/live-chat-snapshot-2026-06-22.json")
DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/live-chat-rubric-2026-06-22.json")
REQUIRED_CITATION_FIELDS = ("date", "source", "title", "citation_id", "excerpt")


def score_live_chat_rows(rows: list[dict]) -> list[dict]:
    """Score rows against deterministic answer-policy checks."""
    scored = []
    for row in rows:
        failed_checks = _failed_checks(row)
        scored.append({
            "id": row.get("id"),
            "expected_answerability": row.get("expected_answerability"),
            "passed": not failed_checks,
            "failed_checks": failed_checks,
        })
    return scored


def summarize_rubric_rows(rows: list[dict]) -> dict:
    """Summarize rubric results."""
    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
    }


def _failed_checks(row: dict) -> list[str]:
    checks = []
    answer = row.get("answer") or ""
    citations = row.get("citations") or []
    expected_answerability = row.get("expected_answerability")

    if row.get("citation_count", 0) <= 0 or not citations:
        checks.append("missing_citations")

    if "证据范围：" not in answer:
        checks.append("missing_evidence_boundary_disclosure")

    if "内部语料" not in answer:
        checks.append("missing_internal_corpus_label")

    if expected_answerability == "needs-web" and not _contains_any(answer, ["外部证据", "联网", "外部来源"]):
        checks.append("missing_external_evidence_label")

    if _has_incomplete_citations(citations):
        checks.append("missing_required_citation_fields")

    return checks


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _has_incomplete_citations(citations: list[dict]) -> bool:
    for citation in citations:
        if any(not citation.get(field) for field in REQUIRED_CITATION_FIELDS):
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Score live chat answers for answer-policy compliance.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    snapshot = json.loads(args.input.read_text(encoding="utf-8"))
    rows = score_live_chat_rows(snapshot.get("rows", []))
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "summary": summarize_rubric_rows(rows),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
