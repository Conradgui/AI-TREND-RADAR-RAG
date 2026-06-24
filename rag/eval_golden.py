"""Golden question evaluation asset validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_GOLDEN_PATH = Path("docs/rag-transformation/evals/golden-questions.json")
ALLOWED_ANSWERABILITY = {"internal-only", "needs-web", "insufficient"}
REQUIRED_FIELDS = {
    "id",
    "question",
    "intent",
    "answerability",
    "expected_retrieval",
    "required_evidence",
    "citation_requirement",
    "good_answer_criteria",
    "bad_answer_patterns",
    "web_search_policy",
    "current_status",
    "needs_conrad_review",
}


def load_golden_questions(path: Path = DEFAULT_GOLDEN_PATH) -> list[dict]:
    """Load golden questions from a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def validate_golden_questions(questions: list[dict]) -> list[str]:
    """Return validation errors for the golden question dataset."""
    errors: list[str] = []
    seen_ids = set()

    if not isinstance(questions, list):
        return ["golden questions must be a list"]

    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            errors.append(f"item {index} must be an object")
            continue

        qid = question.get("id", f"item {index}")
        missing = sorted(REQUIRED_FIELDS - set(question))
        for field in missing:
            errors.append(f"{qid}: missing required field '{field}'")

        if qid in seen_ids:
            errors.append(f"{qid}: duplicate id")
        seen_ids.add(qid)

        answerability = question.get("answerability")
        if answerability and answerability not in ALLOWED_ANSWERABILITY:
            errors.append(f"{qid}: invalid answerability '{answerability}'")

        citation_requirement = question.get("citation_requirement")
        if citation_requirement is not None and not isinstance(citation_requirement, dict):
            errors.append(f"{qid}: citation_requirement must be an object")

        for list_field in ("good_answer_criteria", "bad_answer_patterns"):
            if list_field in question and not isinstance(question[list_field], list):
                errors.append(f"{qid}: {list_field} must be a list")

        if "needs_conrad_review" in question and not isinstance(question["needs_conrad_review"], bool):
            errors.append(f"{qid}: needs_conrad_review must be boolean")

    return errors


def summarize_eval_readiness(questions: list[dict]) -> dict:
    """Summarize evaluation set readiness."""
    answerability = {key: 0 for key in sorted(ALLOWED_ANSWERABILITY)}
    for question in questions:
        value = question.get("answerability")
        if value in answerability:
            answerability[value] += 1
    return {
        "total": len(questions),
        "answerability": answerability,
        "needs_conrad_review": sum(1 for q in questions if q.get("needs_conrad_review")),
        "current_status": {
            status: sum(1 for q in questions if q.get("current_status") == status)
            for status in sorted({q.get("current_status", "unknown") for q in questions})
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate AI Trend Radar RAG golden questions.")
    parser.add_argument("--path", type=Path, default=DEFAULT_GOLDEN_PATH)
    args = parser.parse_args()

    questions = load_golden_questions(args.path)
    errors = validate_golden_questions(questions)
    summary = summarize_eval_readiness(questions)
    print(json.dumps({"errors": errors, "summary": summary}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
