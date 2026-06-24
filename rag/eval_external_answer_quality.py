"""Deterministic rubric for external-evidence answer quality."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_INPUT = Path("docs/rag-transformation/evals/external-chat-smoke-2026-06-22.json")
DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/external-answer-quality-rubric-2026-06-22.json")

INTERNAL_CITATION_FIELDS = ("date", "source", "title", "citation_id", "excerpt")
EXTERNAL_CITATION_FIELDS = (
    "provider",
    "source",
    "source_quality",
    "quality_score",
    "title",
    "url",
    "retrieved_at",
    "excerpt",
)
WEAK_EXTERNAL_QUALITIES = {"generic", "social", "trusted_media"}
UNCERTAINTY_MARKERS = ("不足", "无法", "不能", "不确定", "尚不明确", "需要更多", "需要进一步")


def load_external_answer_quality_rows(path: Path) -> list[dict]:
    """Load either a single external chat smoke artifact or a rows-based snapshot."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        return data["rows"]
    if isinstance(data, dict):
        return [_single_smoke_to_row(data)]
    return []


def score_external_answer_quality_rows(rows: list[dict]) -> list[dict]:
    """Score rows against deterministic hybrid-evidence quality checks."""
    scored = []
    for row in rows:
        failed_checks = _failed_checks(row)
        scored.append({
            "id": row.get("id") or row.get("question", "external-chat-smoke"),
            "passed": not failed_checks,
            "failed_checks": failed_checks,
            "internal_citation_count": _count_citations(row, "internal"),
            "external_citation_count": _count_citations(row, "external"),
            "answer_policy_mode": _answer_policy_mode(row),
        })
    return scored


def summarize_external_answer_quality(rows: list[dict]) -> dict:
    """Summarize external-answer-quality results."""
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


def _single_smoke_to_row(data: dict) -> dict:
    return {
        "id": "external-chat-smoke",
        "question": data.get("question", ""),
        "answer": data.get("answer", ""),
        "citations": data.get("citations", []),
        "query_understanding": data.get("query_understanding", {}),
    }


def _failed_checks(row: dict) -> list[str]:
    checks = []
    answer = row.get("answer") or ""
    citations = row.get("citations") or []
    mode = _answer_policy_mode(row)
    internal_citations = _citations_by_type(row, "internal")
    external_citations = _citations_by_type(row, "external")

    if mode == "internal_and_external_grounded" and (not internal_citations or not external_citations):
        checks.append("missing_internal_external_citation_mix")

    if external_citations and not _contains_any(answer, ["外部证据", "外部来源", "联网"]):
        checks.append("missing_external_label")

    if internal_citations and not _contains_any(answer, ["内部语料", "内部证据", "AI Trend Radar"]):
        checks.append("missing_internal_label")

    if _has_incomplete_internal_citations(internal_citations):
        checks.append("missing_internal_citation_fields")

    if _has_incomplete_external_citations(external_citations):
        checks.append("missing_external_citation_fields")

    if mode == "internal_and_external_grounded" and not _external_search_attempted(row):
        checks.append("missing_external_search_trace")

    if _has_weak_external_source(external_citations) and not _contains_any(answer, list(UNCERTAINTY_MARKERS)):
        checks.append("weak_external_source_without_uncertainty")

    return checks


def _answer_policy_mode(row: dict) -> str:
    return (
        row.get("query_understanding", {})
        .get("answer_policy", {})
        .get("mode", "")
    )


def _external_search_attempted(row: dict) -> bool:
    return bool(row.get("query_understanding", {}).get("external_search", {}).get("attempted"))


def _citations_by_type(row: dict, evidence_type: str) -> list[dict]:
    citations = row.get("citations") or []
    if evidence_type == "internal":
        return [citation for citation in citations if citation.get("evidence_type", "internal") == "internal"]
    return [citation for citation in citations if citation.get("evidence_type") == evidence_type]


def _count_citations(row: dict, evidence_type: str) -> int:
    return len(_citations_by_type(row, evidence_type))


def _has_incomplete_internal_citations(citations: list[dict]) -> bool:
    return any(any(not citation.get(field) for field in INTERNAL_CITATION_FIELDS) for citation in citations)


def _has_incomplete_external_citations(citations: list[dict]) -> bool:
    return any(any(citation.get(field) in (None, "") for field in EXTERNAL_CITATION_FIELDS) for citation in citations)


def _has_weak_external_source(citations: list[dict]) -> bool:
    return any(
        citation.get("source_quality") in WEAK_EXTERNAL_QUALITIES or citation.get("needs_deep_fetch")
        for citation in citations
    )


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score external-evidence answer quality.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = load_external_answer_quality_rows(args.input)
    scored = score_external_answer_quality_rows(rows)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "summary": summarize_external_answer_quality(scored),
        "rows": scored,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
