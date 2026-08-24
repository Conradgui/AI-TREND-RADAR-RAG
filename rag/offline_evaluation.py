"""Offline scoring for frozen evaluation runs.

This module deliberately has no database, retriever, or model dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from rag.eval_retrieval_quality import score_query, summarize


_TRACKING_QUERY_KEYS = {"utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term"}


def _normalize_url(value: str) -> str:
    parts = urlsplit(str(value or "").strip())
    query = urlencode(
        [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True) if key.casefold() not in _TRACKING_QUERY_KEYS]
    )
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), parts.path.rstrip("/"), query, ""))


def _deduplicate_by_url(items: list[dict]) -> list[dict]:
    unique = []
    seen = set()
    for item in items:
        normalized = _normalize_url(item.get("url", ""))
        key = normalized or str(item.get("identity", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def evaluate_frozen_run(dataset_path: str | Path, run_path: str | Path) -> dict:
    """Evaluate the explicitly selected queries in one frozen literal run."""
    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    run = json.loads(Path(run_path).read_text(encoding="utf-8"))
    if run.get("dataset_id") != dataset.get("dataset_id"):
        raise ValueError("dataset_id mismatch between frozen run and evaluation dataset")
    expected_revision = dataset.get("target_snapshot", {}).get("corpus_revision")
    if run.get("corpus_revision") != expected_revision:
        raise ValueError("corpus_revision mismatch between frozen run and evaluation dataset")
    selected_query_ids = list(run["selected_query_ids"])
    if len(selected_query_ids) != len(set(selected_query_ids)):
        raise ValueError("duplicate selected_query_ids")
    queries = {query["id"]: query for query in dataset["queries"]}
    unknown = sorted(set(selected_query_ids) - set(queries))
    if unknown:
        raise ValueError(f"unknown selected query: {', '.join(unknown)}")

    result_items = list(run["results"])
    result_ids = [result["query_id"] for result in result_items]
    if len(result_ids) != len(set(result_ids)):
        raise ValueError("duplicate result query_id")
    missing = sorted(set(selected_query_ids) - set(result_ids))
    if missing:
        raise ValueError(f"missing selected result: {', '.join(missing)}")
    unexpected = sorted(set(result_ids) - set(selected_query_ids))
    if unexpected:
        raise ValueError(f"unexpected unselected result: {', '.join(unexpected)}")
    results = {result["query_id"]: result for result in result_items}

    rows = []
    for query_id in selected_query_ids:
        query = queries[query_id]
        result = results[query_id]
        if not query.get("relevant") and "missing" in str(query.get("relevance_set_status") or ""):
            rows.append({
                "query_id": query_id,
                "task_family": query["task_family"],
                "scored": False,
                "unscored_reason": "relevance_labels_missing",
            })
            continue
        if query.get("task_family") != "item_navigation":
            metric_cutoff = max(1, int(query.get("metric_cutoff", 10)))
            rows.append(score_query(query, result.get("retrieved") or [], metric_cutoff))
            continue
        if int(query.get("hit_cutoff", 1)) != 1:
            raise ValueError("hit_cutoff must be 1 for the navigation tracer bullet")
        target_url = next(
            item["url"]
            for item in query["relevant"]
            if item.get("evidence_role") == "canonical_target"
        )
        evaluation_depth = max(1, int(query.get("evaluation_depth", 10)))
        retrieved = _deduplicate_by_url(result.get("retrieved") or [])[:evaluation_depth]
        target_rank = next(
            (
                rank
                for rank, item in enumerate(retrieved, start=1)
                if _normalize_url(item.get("url", "")) == _normalize_url(target_url)
            ),
            None,
        )
        rows.append(
            {
                "query_id": query_id,
                "task_family": query["task_family"],
                "target_rank": target_rank,
                "hit_at_1": 1 if target_rank == 1 else 0,
                "mrr": round(1.0 / target_rank, 4) if target_rank else 0.0,
            }
        )

    report = {
        "dataset_id": dataset["dataset_id"],
        "run_id": run["run_id"],
        "evaluated_query_ids": selected_query_ids,
        "release_gate_eligible": bool(dataset.get("release_gate_eligible", False)),
        "rows": rows,
    }
    report["summary"] = summarize(rows)
    return report
