"""URL-labelled retrieval quality evaluation for the production retrieval path."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from rag.citations import retrieve_citations_with_status
from rag.graphrag.driver import Neo4jDriver
from rag.query_understanding import analyze_query
from rag.retrieval_planning import build_metadata_filter
from rag.retriever.hybrid import HybridRetriever
from rag.retriever.vector_store import VectorStore


DEFAULT_DATASET = Path("docs/rag-transformation/evals/retrieval-quality-dataset-2026-08-07.json")
DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/retrieval-quality-baseline-2026-08-07.json")
TRACKING_QUERY_KEYS = {"utm_campaign", "utm_medium", "utm_source", "utm_term", "utm_content"}


def normalize_url(value: str) -> str:
    """Normalize URL identity without hiding malformed source URLs."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        return raw.casefold().rstrip("/")
    query = urlencode(
        [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True) if key.casefold() not in TRACKING_QUERY_KEYS]
    )
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), parts.path.rstrip("/"), query, ""))


def result_identity(item: dict) -> str:
    url = normalize_url(item.get("url", ""))
    if url:
        return f"url:{url}"
    fallback = "|".join(str(item.get(key, "")).strip().casefold() for key in ("date", "source", "title"))
    return f"meta:{fallback}"


def score_query(query: dict, retrieved: list[dict], k: int) -> dict:
    """Score one query using frozen URL-level relevance judgments."""
    expected = {result_identity(item): int(item.get("grade", 1)) for item in query.get("relevant", [])}
    unique_retrieved = []
    seen = set()
    for item in retrieved[:k]:
        identity = result_identity(item)
        if identity in seen:
            continue
        seen.add(identity)
        unique_retrieved.append((identity, item))

    answerable = bool(query.get("answerable", True))
    if not answerable:
        return {
            "query_id": query.get("id"),
            "answerable": False,
            "returned": len(unique_retrieved),
            "correct_rejection": len(unique_retrieved) == 0,
            "query_success": len(unique_retrieved) == 0,
            "precision_at_k": None,
            "recall_at_k": None,
            "f1_at_k": None,
            "mrr": None,
            "ndcg_at_k": None,
            "matched": [],
        }

    matched = [(rank, identity, item) for rank, (identity, item) in enumerate(unique_retrieved, start=1) if identity in expected]
    true_positive = len(matched)
    precision = true_positive / k if k else 0.0
    recall = true_positive / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    mrr = 1.0 / matched[0][0] if matched else 0.0

    dcg = sum((2 ** expected[identity] - 1) / math.log2(rank + 1) for rank, identity, _ in matched)
    ideal_grades = sorted(expected.values(), reverse=True)[:k]
    ideal_dcg = sum((2 ** grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal_grades, start=1))
    ndcg = dcg / ideal_dcg if ideal_dcg else 0.0

    return {
        "query_id": query.get("id"),
        "answerable": True,
        "returned": len(unique_retrieved),
        "relevant_total": len(expected),
        "true_positive": true_positive,
        "false_positive": max(0, len(unique_retrieved) - true_positive),
        "false_negative": max(0, len(expected) - true_positive),
        "query_success": true_positive > 0,
        "precision_at_k": round(precision, 4),
        "precision_at_returned": round(true_positive / len(unique_retrieved), 4) if unique_retrieved else 0.0,
        "recall_at_k": round(recall, 4),
        "f1_at_k": round(f1, 4),
        "mrr": round(mrr, 4),
        "ndcg_at_k": round(ndcg, 4),
        "matched": [
            {"rank": rank, "identity": identity, "title": item.get("title", ""), "source": item.get("source", "")}
            for rank, identity, item in matched
        ],
    }


def summarize(rows: list[dict], k: int) -> dict:
    answerable = [row for row in rows if row.get("answerable")]
    unanswerable = [row for row in rows if not row.get("answerable")]
    total = len(rows)
    query_successes = sum(bool(row.get("query_success")) for row in rows)
    macro_fields = ("precision_at_k", "recall_at_k", "f1_at_k", "mrr", "ndcg_at_k")
    macro = {
        field: round(sum(float(row.get(field) or 0) for row in answerable) / len(answerable), 4) if answerable else 0.0
        for field in macro_fields
    }
    tp = sum(int(row.get("true_positive") or 0) for row in answerable)
    relevant = sum(int(row.get("relevant_total") or 0) for row in answerable)
    micro_precision = tp / (len(answerable) * k) if answerable and k else 0.0
    micro_recall = tp / relevant if relevant else 0.0
    micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall) if micro_precision + micro_recall else 0.0
    return {
        "query_count": total,
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "query_success_accuracy": round(query_successes / total, 4) if total else 0.0,
        "correct_rejection_rate": round(sum(bool(row.get("correct_rejection")) for row in unanswerable) / len(unanswerable), 4) if unanswerable else None,
        "macro": macro,
        "micro": {
            "true_positive": tp,
            "relevant_total": relevant,
            "precision_at_k": round(micro_precision, 4),
            "recall_at_k": round(micro_recall, 4),
            "f1_at_k": round(micro_f1, 4),
        },
    }


async def run_dataset(dataset: dict, *, persist_dir: str | None = None) -> dict:
    k = int(dataset.get("metric_policy", {}).get("k", 10))
    latest_date = dataset.get("snapshot", {}).get("latest_corpus_date")
    vector = VectorStore(persist_dir) if persist_dir else VectorStore()
    graph = Neo4jDriver()
    await graph.connect()
    retriever = HybridRetriever(vector, graph)
    rows = []
    try:
        for query in dataset.get("queries", []):
            plan = analyze_query(query["query"])
            where = build_metadata_filter(plan, latest_date)
            outcome = await retrieve_citations_with_status(
                retriever,
                plan.retrieval_query,
                k=k,
                where=where,
                prefer_recent=plan.time_window.get("label") == "recent_corpus_first",
                latest_date=latest_date,
            )
            scored = score_query(query, outcome.citations, k)
            scored.update({
                "query": query["query"],
                "kind": query.get("kind"),
                "retrieval_status": outcome.status,
                "retrieval_error_code": outcome.error_code,
                "elapsed_ms": round(outcome.elapsed_ms, 2),
                "metadata_filter": where,
                "retrieved": outcome.citations,
            })
            rows.append(scored)
    finally:
        await graph.close()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset.get("dataset_id"),
        "label_tier": dataset.get("label_tier"),
        "needs_human_review": dataset.get("needs_human_review", True),
        "summary": summarize(rows, k),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run URL-labelled retrieval quality evaluation.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--persist-dir")
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    result = asyncio.run(run_dataset(dataset, persist_dir=args.persist_dir))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
