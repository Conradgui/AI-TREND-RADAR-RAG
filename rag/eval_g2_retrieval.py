"""ATR-aware G2 retrieval and answer-path evaluation.

The scorer deliberately keeps task families separate. Navigation, trend discovery,
relation/timeline, and evidence-insufficiency do not share one meaningful global F1.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


FORMAL_REVIEW_STATUS = "human_reviewed"


def _occurrence_id(citation: dict) -> str:
    value = citation.get("occurrence_id") or citation.get("citation_id") or ""
    return str(value) if str(value).startswith("ATR-") else ""


def _unique_ids(citations: list[dict]) -> list[str]:
    return list(dict.fromkeys(filter(None, (_occurrence_id(row) for row in citations))))


def _content_id(citation: dict) -> str:
    return str(citation.get("content_id") or "").strip()


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _expected_layers(case: dict) -> tuple[list[str], list[str]]:
    expected = case.get("relevant_occurrence_ids") or []
    if isinstance(expected, list):
        return list(expected), []
    return list(expected.get("primary") or []), list(expected.get("supporting") or [])


def _expected_content_layers(case: dict) -> tuple[list[str], list[str]]:
    """Return optional stable-content equivalents aligned with gold occurrences.

    Occurrence IDs keep daily provenance. Content IDs let a reviewed evaluation
    recognize the same stable content when a later daily report observes it
    again, rather than scoring that legitimate freshness update as a miss.
    """
    expected = case.get("relevant_content_ids") or []
    if isinstance(expected, list):
        return list(expected), []
    return list(expected.get("primary") or []), list(expected.get("supporting") or [])


def _identity_aligned_ids(
    citations: list[dict],
    expected_occurrences: list[str],
    expected_contents: list[str],
) -> list[str]:
    """Project each returned citation to a gold occurrence when content matches."""
    aligned = []
    for citation in citations:
        occurrence_id = _occurrence_id(citation)
        content_id = _content_id(citation)
        matched = occurrence_id
        for index, expected_occurrence in enumerate(expected_occurrences):
            expected_content = (
                expected_contents[index]
                if index < len(expected_contents)
                else ""
            )
            if occurrence_id == expected_occurrence or (
                content_id and expected_content and content_id == expected_content
            ):
                matched = expected_occurrence
                break
        if matched:
            aligned.append(matched)
    return list(dict.fromkeys(aligned))


def _unjudged_occurrence_ids(
    citations: list[dict],
    expected_occurrences: list[str],
    expected_contents: list[str],
) -> list[str]:
    """Keep the diagnostic provenance ID, but honor reviewed content equivalence."""
    labelled = set(expected_occurrences)
    unjudged = []
    for citation in citations:
        raw_id = _occurrence_id(citation)
        aligned = _identity_aligned_ids(
            [citation], expected_occurrences, expected_contents
        )
        judged_id = aligned[0] if aligned else raw_id
        if raw_id and judged_id not in labelled:
            unjudged.append(raw_id)
    return list(dict.fromkeys(unjudged))


def score_case(case: dict, response: dict) -> dict:
    """Score one response against its task-specific ATR contract."""
    family = str(case.get("task_family") or "")
    mode = str(case.get("answer_mode") or "")
    citations = list(response.get("citations") or [])
    returned_ids = _unique_ids(citations)
    primary, supporting = _expected_layers(case)
    primary_contents, supporting_contents = _expected_content_layers(case)
    base = {
        "case_id": case.get("case_id"),
        "task_family": family,
        "answer_mode": mode,
        "returned_occurrence_ids": returned_ids,
    }

    if family == "item_navigation":
        aligned_ids = _identity_aligned_ids(citations, primary, primary_contents)
        ranks = [aligned_ids.index(item) + 1 for item in primary if item in aligned_ids]
        rank = min(ranks) if ranks else None
        return {
            **base,
            "passed": rank is not None and rank <= 5,
            "target_rank": rank,
            "recall_at_5": _ratio(sum(item in aligned_ids[:5] for item in primary), len(primary)),
        }

    if family == "recent_trend":
        main_citations = [
            row for row in citations
            if row.get("news_tier") not in {"supplementary", "background", "unverified"}
        ]
        main_ids = _unique_ids(main_citations)
        main_aligned_ids = _identity_aligned_ids(
            main_citations,
            [*primary, *supporting],
            [*primary_contents, *supporting_contents],
        )
        all_aligned_ids = _identity_aligned_ids(
            citations,
            [*primary, *supporting],
            [*primary_contents, *supporting_contents],
        )
        primary_hits = [item for item in primary if item in main_aligned_ids]
        supporting_hits = [item for item in supporting if item in all_aligned_ids]
        main_true_positive = sum(item in set(primary) for item in main_aligned_ids)
        primary_recall = _ratio(len(primary_hits), len(primary))
        labels_exhaustive = bool(case.get("labels_exhaustive", True))
        main_precision = (
            _ratio(main_true_positive, len(main_ids)) if labels_exhaustive else None
        )
        minimum_primary_hits = int(
            case.get("minimum_primary_hits")
            or max(1, len(primary))
        )
        passed = (
            primary_recall >= 0.8 and main_precision == 1.0
            if labels_exhaustive
            else len(primary_hits) >= minimum_primary_hits
        )
        return {
            **base,
            "passed": passed,
            "main_occurrence_ids": main_ids,
            "primary_hits": primary_hits,
            "supporting_hits": supporting_hits,
            "primary_recall": primary_recall,
            "main_precision": main_precision,
            "labels_exhaustive": labels_exhaustive,
            "minimum_primary_hits": minimum_primary_hits,
            "unjudged_main_occurrence_ids": _unjudged_occurrence_ids(
                main_citations,
                [*primary, *supporting],
                [*primary_contents, *supporting_contents],
            ),
        }

    if family in {"relation_comparison", "timeline"}:
        expected = set(primary)
        returned = set(_identity_aligned_ids(citations, primary, primary_contents))
        recall = _ratio(len(expected & returned), len(expected))
        precision = _ratio(len(expected & returned), len(returned))
        return {
            **base,
            "passed": recall == 1.0 and precision == 1.0,
            "recall": recall,
            "precision": precision,
        }

    if family == "evidence_insufficiency" and mode == "clarification_required":
        trace = response.get("tool_trace") or {}
        counts = trace.get("execution_counts") or {}
        valid = (
            not returned_ids
            and trace.get("execution_path") == "clarification_required"
            and int(counts.get("model_turns") or 0) == 0
        )
        return {
            **base,
            "passed": valid,
            "clarification_without_model": valid,
        }

    if family == "evidence_insufficiency" and mode == "bounded_not_found":
        answer = str(response.get("answer") or "")
        boundary_disclosed = any(marker in answer for marker in ("未找到", "没有找到", "证据不足"))
        valid = not returned_ids and boundary_disclosed
        return {
            **base,
            "passed": valid,
            "bounded_not_found": valid,
            "boundary_disclosed": boundary_disclosed,
        }

    return {**base, "passed": False, "error": "unsupported_task_contract"}


def summarize_scores(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("task_family") or "unknown")].append(row)
    return {
        "total": len(rows),
        "passed": sum(row.get("passed") is True for row in rows),
        "failed": sum(row.get("passed") is not True for row in rows),
        "by_task_family": {
            family: {
                "total": len(items),
                "passed": sum(item.get("passed") is True for item in items),
                "failed": sum(item.get("passed") is not True for item in items),
            }
            for family, items in sorted(grouped.items())
        },
        "metric_policy": "task_specific_no_fake_global_f1",
    }


def score_snapshot(gold: dict, snapshot: dict, *, allow_review_draft: bool = False) -> dict:
    review_status = str(gold.get("review_status") or "")
    if review_status != FORMAL_REVIEW_STATUS and not allow_review_draft:
        raise ValueError(
            f"formal scoring requires review_status={FORMAL_REVIEW_STATUS}; got {review_status or 'missing'}"
        )
    responses = {
        str(row.get("case_id")): (row.get("response") or row)
        for row in snapshot.get("rows", [])
    }
    scores = []
    for case in gold.get("cases", []):
        case_id = str(case.get("case_id"))
        response = responses.get(case_id)
        if response is None:
            scores.append({
                "case_id": case_id,
                "task_family": case.get("task_family"),
                "passed": False,
                "error": "snapshot_row_missing",
            })
            continue
        scores.append(score_case(case, response))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_schema_version": gold.get("schema_version"),
        "review_status": review_status,
        "summary": summarize_scores(scores),
        "rows": scores,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score G2 ATR-layered retrieval snapshots.")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-review-draft", action="store_true")
    args = parser.parse_args()
    result = score_snapshot(
        json.loads(args.gold.read_text(encoding="utf-8")),
        json.loads(args.input.read_text(encoding="utf-8")),
        allow_review_draft=args.allow_review_draft,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
