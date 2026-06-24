"""Deterministic retrieval precision scoring for chat snapshots."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_INPUT = Path("docs/rag-transformation/evals/hybrid-live-chat-snapshot-2026-06-23.json")
DEFAULT_SEED = Path("docs/rag-transformation/evals/retrieval-precision-seed-2026-06-23.json")
DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/retrieval-precision-matrix-2026-06-23.json")


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


def load_precision_seed(path: Path) -> list[dict]:
    """Load retrieval precision seed rows."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("questions"), list):
        return data["questions"]
    if isinstance(data, list):
        return data
    return []


def classify_citations_for_question(citations: list[dict], seed: dict) -> list[dict]:
    """Classify citations as relevant, redundant, distracting, or weak."""
    relevant_terms = seed.get("relevant_terms_any") or []
    distracting_terms = seed.get("distracting_terms_any") or []
    seen_relevant_keys = set()
    classified = []

    for index, citation in enumerate(citations, start=1):
        text = _citation_text(citation)
        key = _citation_key(citation)
        has_relevant = _contains_any(text, relevant_terms)
        has_distracting = _contains_any(text, distracting_terms)

        if has_relevant and key in seen_relevant_keys:
            classification = "redundant"
        elif has_relevant:
            classification = "relevant"
            seen_relevant_keys.add(key)
        elif has_distracting:
            classification = "distracting"
        else:
            classification = "weak"

        classified.append({
            "rank": index,
            "classification": classification,
            "title": citation.get("title", ""),
            "source": citation.get("source", ""),
            "citation_id": citation.get("citation_id", ""),
            "evidence_type": citation.get("evidence_type", "internal"),
        })

    return classified


def score_retrieval_precision_rows(rows: list[dict], seeds: list[dict]) -> list[dict]:
    """Score retrieval precision for snapshot rows."""
    rows_by_id = {row.get("id"): row for row in rows}
    scored = []
    for seed in seeds:
        row = rows_by_id.get(seed.get("question_id"))
        if not row:
            scored.append(_missing_row_score(seed))
            continue

        citations = row.get("citations") or []
        classified = classify_citations_for_question(citations, seed)
        counts = Counter(item["classification"] for item in classified)
        failed_checks = _failed_checks(citations, counts, seed)
        citation_count = len(citations)

        scored.append({
            "question_id": seed.get("question_id"),
            "passed": not failed_checks,
            "failed_checks": failed_checks,
            "citation_count": citation_count,
            "relevant_count": counts.get("relevant", 0),
            "redundant_count": counts.get("redundant", 0),
            "distracting_count": counts.get("distracting", 0),
            "weak_count": counts.get("weak", 0),
            "distracting_rate": _rate(counts.get("distracting", 0), citation_count),
            "weak_rate": _rate(counts.get("weak", 0), citation_count),
            "classified_citations": classified,
            "needs_conrad_review": bool(seed.get("needs_conrad_review", True)),
        })
    return scored


def summarize_retrieval_precision_rows(rows: list[dict]) -> dict:
    """Summarize retrieval precision rows."""
    failures = Counter()
    for row in rows:
        failures.update(row.get("failed_checks", []))
    total = len(rows)
    passed = sum(1 for row in rows if row.get("passed"))
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "citation_count": sum(row.get("citation_count", 0) for row in rows),
        "distracting_count": sum(row.get("distracting_count", 0) for row in rows),
        "failure_counts": dict(failures),
    }


def _failed_checks(citations: list[dict], counts: Counter, seed: dict) -> list[str]:
    failed = []
    citation_count = len(citations)
    if counts.get("relevant", 0) < seed.get("min_relevant_citations", 0):
        failed.append("missing_relevant_citations")
    if _rate(counts.get("distracting", 0), citation_count) > seed.get("max_distracting_rate", 1):
        failed.append("distracting_rate_too_high")
    if _rate(counts.get("weak", 0), citation_count) > seed.get("max_weak_rate", 1):
        failed.append("weak_rate_too_high")
    if _rate(counts.get("redundant", 0), citation_count) > seed.get("max_redundant_rate", 1):
        failed.append("redundant_rate_too_high")
    return failed


def _missing_row_score(seed: dict) -> dict:
    return {
        "question_id": seed.get("question_id"),
        "passed": False,
        "failed_checks": ["question_row_missing"],
        "citation_count": 0,
        "relevant_count": 0,
        "redundant_count": 0,
        "distracting_count": 0,
        "weak_count": 0,
        "distracting_rate": 0,
        "weak_rate": 0,
        "classified_citations": [],
        "needs_conrad_review": bool(seed.get("needs_conrad_review", True)),
    }


def _citation_text(citation: dict) -> str:
    fields = (
        citation.get("title", ""),
        citation.get("source", ""),
        citation.get("category", ""),
        citation.get("url", ""),
        citation.get("excerpt", ""),
    )
    return "\n".join(str(field) for field in fields if field)


def _citation_key(citation: dict) -> str:
    raw = f"{citation.get('title', '')}|{citation.get('source', '')}|{citation.get('url', '')}"
    return re.sub(r"\s+", " ", raw.casefold()).strip()


def _contains_any(text: str, needles: list[str]) -> bool:
    normalized = text.casefold()
    return any(needle.casefold() in normalized for needle in needles)


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0
    return round(count / total, 4)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score retrieval precision for a chat snapshot.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = load_snapshot_rows(args.input)
    seeds = load_precision_seed(args.seed)
    scored = score_retrieval_precision_rows(rows, seeds)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "seed": str(args.seed),
        "summary": summarize_retrieval_precision_rows(scored),
        "rows": scored,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
