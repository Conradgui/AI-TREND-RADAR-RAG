"""Small, snapshot-bound release gate for the retrieval gateway.

This evaluator deliberately checks the public ``EvidenceBundle`` seam rather
than private ranking helpers.  It is a cheap guardrail before we attach a
Gateway change to the API or Web UI; it is *not* a substitute for a labelled
retrieval-quality benchmark or human relevance review.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from rag.citations import retrieve_citations_with_status
from rag.eval_retrieval_quality import inspect_vector_snapshot
from rag.query_understanding import analyze_query
from rag.retrieval_gateway import EvidenceRetrievalGateway, EvidenceBundle, ResearchRequest
from rag.retrieval_planning import build_metadata_filter, source_diversity_cap
from rag.retriever.lexical_store import LexicalStore
from rag.retriever.vector_only import VectorOnlyRetriever
from rag.retriever.vector_store import VectorStore


DEFAULT_DATASET = Path("docs/rag-transformation/evals/gateway-canary-2026-08-05.json")
DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/gateway-canary-results-2026-08-10.json")


def _record_summary(record: dict) -> dict:
    """Keep report evidence inspectable without duplicating full corpus text."""
    return {
        key: record.get(key, "")
        for key in ("citation_id", "date", "source", "title", "local_url", "url")
    }


def evaluate_case(case: dict, bundle: EvidenceBundle, baseline_records: list[dict]) -> dict:
    """Evaluate one user-visible Gateway result against a small fixed contract."""
    records = list(bundle.records or [])
    checks: dict[str, bool] = {
        "status_ready": bundle.status in {"ready", "degraded", "partial_error"},
        "task_family": bundle.task_family == case.get("expected_task_family"),
    }

    minimum = case.get("min_records")
    if minimum is not None:
        checks["min_records"] = len(records) >= int(minimum)

    citation_ids = [str(record.get("citation_id") or "") for record in records]
    if case.get("require_unique_citation_ids"):
        checks["unique_citation_ids"] = bool(citation_ids) and len(citation_ids) == len(set(citation_ids))

    source_counts = Counter(
        str(record.get("source") or "未知来源") for record in records
    )
    minimum_sources = case.get("min_unique_sources")
    if minimum_sources is not None:
        checks["unique_sources"] = len(source_counts) >= int(minimum_sources)

    max_per_source = case.get("max_per_source")
    if max_per_source is not None:
        checks["source_cap"] = all(count <= int(max_per_source) for count in source_counts.values())

    expected_citation_id = str(case.get("expected_citation_id") or "")
    if expected_citation_id:
        checks["expected_top_result"] = bool(records) and str(records[0].get("citation_id") or "") == expected_citation_id

    if case.get("requires_local_url"):
        checks["stable_local_url"] = bool(records) and bool(str(records[0].get("local_url") or "").strip())

    # Broad cases do not have a reliable relevance label yet.  The least we
    # can enforce is that a Gateway change never turns existing evidence into
    # an empty answer on the same pinned corpus snapshot.
    if case.get("no_empty_regression"):
        checks["no_empty_regression"] = not baseline_records or bool(records)

    return {
        "id": case.get("id"),
        "query": case.get("query"),
        "passed": all(checks.values()),
        "checks": checks,
        "candidate": {
            "status": bundle.status,
            "task_family": bundle.task_family,
            "error_code": bundle.error_code,
            "elapsed_ms": round(bundle.elapsed_ms, 2),
            "trace": bundle.trace,
            "records": [_record_summary(record) for record in records],
        },
        "baseline": {
            "record_count": len(baseline_records),
            "records": [_record_summary(record) for record in baseline_records],
        },
    }


def _inspect_lexical_snapshot(lexical: LexicalStore) -> dict:
    newest = lexical.recent(limit=1)
    metadata = newest[0].get("metadata") if newest else {}
    return {
        "latest_corpus_date": str((metadata or {}).get("date") or ""),
        "document_count": lexical.count(),
    }


async def _baseline_records(retriever, query: str, latest_date: str, limit: int) -> list[dict]:
    """Run the pre-Gateway evidence path only for a no-regression comparison."""
    plan = analyze_query(query)
    outcome = await retrieve_citations_with_status(
        retriever,
        plan.retrieval_query,
        k=limit,
        where=build_metadata_filter(plan, latest_date),
        prefer_recent=plan.time_window.get("label") == "recent_corpus_first",
        latest_date=latest_date,
        graph_requirement=plan.graph_requirement,
        source_cap=source_diversity_cap(plan),
    )
    return outcome.citations


async def run_canary(
    dataset: dict,
    *,
    persist_dir: str | None = None,
    lexical_path: str | None = None,
) -> dict:
    """Run a snapshot-locked Gateway Canary without LLM/API/graph side effects."""
    target = dict(dataset.get("target_snapshot") or {})
    expected_date = str(target.get("latest_corpus_date") or "")
    vector = VectorStore(persist_dir) if persist_dir else VectorStore()
    lexical_file = Path(lexical_path) if lexical_path else None
    if lexical_file is None or not lexical_file.exists():
        vector.close()
        raise FileNotFoundError("Gateway Canary requires an existing lexical index via --lexical-path.")

    lexical = LexicalStore(lexical_file)
    try:
        observed_vector = inspect_vector_snapshot(vector)
        observed_lexical = _inspect_lexical_snapshot(lexical)
        snapshot_matches = (
            bool(expected_date)
            and observed_vector.get("latest_corpus_date") == expected_date
            and observed_lexical.get("latest_corpus_date") == expected_date
        )
        if not snapshot_matches:
            raise ValueError(
                "Gateway Canary snapshot mismatch: labels, vector index and lexical index must all share the same latest corpus date."
            )

        retriever = VectorOnlyRetriever(vector, lexical_store=lexical)
        gateway = EvidenceRetrievalGateway(retriever, structured_store=lexical)
        rows = []
        for case in dataset.get("cases", []):
            limit = max(1, int(case.get("limit", 5)))
            baseline = await _baseline_records(retriever, case["query"], expected_date, limit)
            bundle = await gateway.retrieve(
                ResearchRequest(
                    question=case["query"],
                    latest_corpus_date=expected_date,
                    limit=limit,
                )
            )
            rows.append(evaluate_case(case, bundle, baseline))
    finally:
        lexical.close()
        vector.close()

    passed = sum(1 for row in rows if row["passed"])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset.get("dataset_id"),
        "purpose": "Gateway Canary: functional/no-regression gate before broader integration",
        "scope_limit": "Vector + lexical index only; does not validate LLM answers, graph retrieval, external search, or human relevance.",
        "target_snapshot": target,
        "observed_snapshot": {"vector": observed_vector, "lexical": observed_lexical},
        "summary": {
            "total": len(rows),
            "passed": passed,
            "failed": len(rows) - passed,
            "gate_passed": passed == len(rows),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the snapshot-bound retrieval Gateway Canary.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--persist-dir")
    parser.add_argument("--lexical-path", required=True)
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    result = asyncio.run(
        run_canary(dataset, persist_dir=args.persist_dir, lexical_path=args.lexical_path)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
