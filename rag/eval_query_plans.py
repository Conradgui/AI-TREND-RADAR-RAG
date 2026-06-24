"""Query-plan benchmark snapshot for golden questions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag.eval_golden import DEFAULT_GOLDEN_PATH, load_golden_questions, validate_golden_questions
from rag.query_understanding import analyze_query
from rag.retrieval_planning import build_metadata_filter, load_latest_corpus_date


def build_query_plan_snapshot(questions: list[dict], latest_corpus_date: str | None = None) -> list[dict]:
    """Build deterministic query-planning snapshot rows for golden questions."""
    rows = []
    for item in questions:
        plan = analyze_query(item["question"])
        metadata_filter = build_metadata_filter(plan, latest_corpus_date)
        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "expected_answerability": item["answerability"],
                "planned_intent": plan.intent,
                "planned_topics": plan.topics,
                "planned_entities": plan.entities,
                "planned_sources": plan.sources,
                "planned_time_window": plan.time_window,
                "planned_top_k": plan.top_k,
                "planned_needs_web_search": plan.needs_web_search,
                "planned_retrieval_query": plan.retrieval_query,
                "latest_corpus_date": latest_corpus_date,
                "metadata_filter": metadata_filter,
            }
        )
    return rows


def summarize_snapshot(rows: list[dict]) -> dict:
    """Summarize a query-plan snapshot for quick regression checks."""
    return {
        "total": len(rows),
        "needs_web_search": sum(1 for row in rows if row["planned_needs_web_search"]),
        "with_metadata_filter": sum(1 for row in rows if row["metadata_filter"]),
        "intents": {
            intent: sum(1 for row in rows if row["planned_intent"] == intent)
            for intent in sorted({row["planned_intent"] for row in rows})
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build query-plan benchmark snapshot for golden questions.")
    parser.add_argument("--path", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--latest-corpus-date", default=None)
    args = parser.parse_args()

    questions = load_golden_questions(args.path)
    errors = validate_golden_questions(questions)
    if errors:
        print(json.dumps({"errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    latest_corpus_date = args.latest_corpus_date or load_latest_corpus_date()
    rows = build_query_plan_snapshot(questions, latest_corpus_date=latest_corpus_date)
    print(
        json.dumps(
            {
                "errors": [],
                "summary": summarize_snapshot(rows),
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
