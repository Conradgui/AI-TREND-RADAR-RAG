"""Deterministic provider quality matrix for live chat snapshots."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_INPUT = Path("docs/rag-transformation/evals/live-chat-snapshot-2026-06-22.json")
DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/provider-quality-matrix-2026-06-23.json")
INTERNAL_CITATION_FIELDS = ("date", "source", "title", "citation_id", "excerpt")
EXTERNAL_CITATION_FIELDS = ("provider", "source", "source_quality", "title", "url", "retrieved_at", "excerpt")
WEAK_SOURCE_QUALITIES = {"generic", "social", "trusted_media"}


def load_provider_quality_rows(path: Path) -> list[dict]:
    """Load a snapshot that contains rows."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        return data["rows"]
    if isinstance(data, dict):
        return [data]
    return []


def score_provider_quality_rows(rows: list[dict]) -> list[dict]:
    """Score rows for structural answer and evidence quality."""
    scored = []
    for row in rows:
        failed_checks = _failed_checks(row)
        citations = row.get("citations") or []
        scored.append({
            "id": row.get("id") or row.get("question", "row"),
            "expected_answerability": row.get("expected_answerability"),
            "passed": not failed_checks,
            "failed_checks": failed_checks,
            "answer_policy_mode": _answer_policy_mode(row),
            "citation_count": len(citations),
            "internal_citation_count": len(_internal_citations(row)),
            "external_citation_count": len(_external_citations(row)),
            "graph_citation_count": len(_graph_citations(row)),
            "source_review_status": _source_review(row).get("status", ""),
            "external_search_attempted": _external_search_attempted(row),
        })
    return scored


def summarize_provider_quality_rows(rows: list[dict]) -> dict:
    """Summarize provider quality score rows."""
    failures = Counter()
    for row in rows:
        failures.update(row.get("failed_checks", []))
    total = len(rows)
    passed = sum(1 for row in rows if row.get("passed"))
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "with_graph_citations": sum(1 for row in rows if row.get("graph_citation_count", 0) > 0),
        "with_external_citations": sum(1 for row in rows if row.get("external_citation_count", 0) > 0),
        "failure_counts": dict(failures),
    }


def _failed_checks(row: dict) -> list[str]:
    checks = []
    answer = row.get("answer") or ""
    citations = row.get("citations") or []
    expected = row.get("expected_answerability")
    mode = _answer_policy_mode(row)
    internal = _internal_citations(row)
    external = _external_citations(row)
    source_review = _source_review(row)

    if not citations:
        checks.append("missing_citations")

    if "证据范围：" not in answer:
        checks.append("missing_evidence_boundary_disclosure")

    if internal and "内部语料" not in answer and "AI Trend Radar" not in answer:
        checks.append("missing_internal_evidence_label")

    if _has_incomplete_internal_citations(internal):
        checks.append("missing_internal_citation_fields")

    if _has_incomplete_external_citations(external):
        checks.append("missing_external_citation_fields")

    if expected == "internal-only" and mode not in {"internal_grounded", "internal_and_external_grounded"}:
        checks.append("unexpected_answer_policy_for_internal_question")

    if expected == "needs-web":
        if mode == "internal_grounded":
            checks.append("needs_web_marked_internal_grounded")
        if mode == "internal_and_external_grounded" and not external:
            checks.append("needs_web_mode_without_external_citations")
        if mode == "needs_external_evidence" and _external_search_attempted(row) and not external:
            checks.append("external_search_attempted_without_citations")

    if external and not _external_search_attempted(row):
        checks.append("external_citations_without_search_trace")

    if external and not source_review:
        checks.append("missing_source_review")

    if _has_weak_external_source(external) and source_review.get("weak_count", 0) <= 0:
        checks.append("weak_external_source_not_reflected_in_source_review")

    return checks


def _answer_policy_mode(row: dict) -> str:
    return (row.get("query_understanding") or {}).get("answer_policy", {}).get("mode", "")


def _source_review(row: dict) -> dict:
    return (row.get("query_understanding") or {}).get("source_review") or {}


def _external_search_attempted(row: dict) -> bool:
    return bool((row.get("query_understanding") or {}).get("external_search", {}).get("attempted"))


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


def _has_incomplete_internal_citations(citations: list[dict]) -> bool:
    return any(any(not citation.get(field) for field in INTERNAL_CITATION_FIELDS) for citation in citations)


def _has_incomplete_external_citations(citations: list[dict]) -> bool:
    return any(any(citation.get(field) in (None, "") for field in EXTERNAL_CITATION_FIELDS) for citation in citations)


def _has_weak_external_source(citations: list[dict]) -> bool:
    return any(
        citation.get("source_quality") in WEAK_SOURCE_QUALITIES or citation.get("needs_deep_fetch")
        for citation in citations
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score provider quality matrix for a chat snapshot.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = load_provider_quality_rows(args.input)
    scored = score_provider_quality_rows(rows)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "summary": summarize_provider_quality_rows(scored),
        "rows": scored,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
