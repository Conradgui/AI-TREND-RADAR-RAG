"""Keyword-based corpus availability benchmark for golden questions."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from rag.eval_golden import DEFAULT_GOLDEN_PATH, load_golden_questions, validate_golden_questions
from rag.query_understanding import analyze_query
from rag.retrieval_planning import load_latest_corpus_date


@dataclass(frozen=True)
class CorpusDocument:
    date: str
    source: str
    path: str
    text: str


def load_corpus_documents(corpus_root: Path = Path("digests")) -> list[CorpusDocument]:
    """Load local digest markdown and topic-pool JSON documents."""
    if not corpus_root.exists():
        return []

    documents = []
    for path in sorted(corpus_root.glob("*/**/*")):
        if not path.is_file() or path.suffix not in {".md", ".json"}:
            continue
        date_value = path.parts[-2]
        if not _looks_like_date(date_value):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        documents.append(
            CorpusDocument(
                date=date_value,
                source=path.stem,
                path=str(path),
                text=text,
            )
        )
    return documents


def build_corpus_availability_snapshot(
    questions: list[dict],
    documents: list[CorpusDocument],
    latest_corpus_date: str | None = None,
) -> list[dict]:
    """Build keyword-based corpus availability rows for golden questions."""
    rows = []
    for item in questions:
        plan = analyze_query(item["question"])
        scoped_documents = _filter_documents_by_plan(documents, plan.time_window, latest_corpus_date)
        keywords = item.get("expected_retrieval", {}).get("keywords", [])
        matches = _match_keywords(scoped_documents, keywords)
        matched_count = len(matches["keywords"])
        coverage_level = _coverage_level(matched_count, len(keywords))
        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "answerability": item["answerability"],
                "planned_intent": plan.intent,
                "latest_corpus_date": latest_corpus_date,
                "scanned_documents": len(scoped_documents),
                "keyword_count": len(keywords),
                "matched_keyword_count": matched_count,
                "matched_keywords": matches["keywords"],
                "matched_dates": matches["dates"],
                "matched_sources": matches["sources"],
                "coverage_level": coverage_level,
                "has_local_signals": matched_count > 0,
                "likely_has_corpus_evidence": coverage_level in {"partial", "strong"},
            }
        )
    return rows


def summarize_availability(rows: list[dict]) -> dict:
    """Summarize corpus availability snapshot."""
    return {
        "total": len(rows),
        "likely_has_corpus_evidence": sum(1 for row in rows if row["likely_has_corpus_evidence"]),
        "likely_missing_corpus_evidence": sum(1 for row in rows if not row["likely_has_corpus_evidence"]),
        "needs_web_but_has_local_signals": sum(
            1
            for row in rows
            if row["answerability"] == "needs-web" and row["has_local_signals"]
        ),
    }


def _filter_documents_by_plan(
    documents: list[CorpusDocument],
    time_window: dict,
    latest_corpus_date: str | None,
) -> list[CorpusDocument]:
    if not latest_corpus_date:
        return documents

    label = time_window.get("label")
    if label == "last_7_days":
        return _filter_documents_by_days(documents, latest_corpus_date, 7)
    if label == "recent_corpus_first":
        return _filter_documents_by_days(documents, latest_corpus_date, int(time_window.get("days") or 14))
    return documents


def _filter_documents_by_days(documents: list[CorpusDocument], latest_corpus_date: str, days: int) -> list[CorpusDocument]:
    end = date.fromisoformat(latest_corpus_date)
    start = end - timedelta(days=days - 1)
    return [doc for doc in documents if start <= date.fromisoformat(doc.date) <= end]


def _match_keywords(documents: list[CorpusDocument], keywords: list[str]) -> dict:
    matched_keywords = set()
    matched_dates = set()
    matched_sources = set()

    for doc in documents:
        text = doc.text.casefold()
        for keyword in keywords:
            if keyword.casefold() in text:
                matched_keywords.add(keyword)
                matched_dates.add(doc.date)
                matched_sources.add(doc.source)

    return {
        "keywords": sorted(matched_keywords, key=str.casefold),
        "dates": sorted(matched_dates),
        "sources": sorted(matched_sources),
    }


def _coverage_level(matched_count: int, keyword_count: int) -> str:
    if matched_count == 0 or keyword_count == 0:
        return "none"
    ratio = matched_count / keyword_count
    if ratio < 0.4:
        return "weak"
    if ratio < 0.75:
        return "partial"
    return "strong"


def _looks_like_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Check local corpus availability for golden questions.")
    parser.add_argument("--path", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--corpus-root", type=Path, default=Path("digests"))
    parser.add_argument("--latest-corpus-date", default=None)
    args = parser.parse_args()

    questions = load_golden_questions(args.path)
    errors = validate_golden_questions(questions)
    if errors:
        print(json.dumps({"errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    latest_corpus_date = args.latest_corpus_date or load_latest_corpus_date()
    documents = load_corpus_documents(args.corpus_root)
    rows = build_corpus_availability_snapshot(questions, documents, latest_corpus_date)
    print(
        json.dumps(
            {
                "errors": [],
                "summary": summarize_availability(rows),
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
