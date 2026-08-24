"""URL-labelled retrieval quality evaluation for the production retrieval path."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from rag.query_understanding import analyze_query


DEFAULT_DATASET = Path("docs/rag-transformation/evals/retrieval-quality-dataset-2026-08-07.json")
DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/retrieval-quality-baseline-2026-08-07.json")
TRACKING_QUERY_KEYS = {"utm_campaign", "utm_medium", "utm_source", "utm_term", "utm_content"}


def _apply_contract_defaults(query: dict, defaults: dict) -> dict:
    """Apply reviewable dataset defaults without overwriting explicit query contracts."""
    resolved = dict(query)
    by_kind = defaults.get("by_kind", {})
    by_negative_type = defaults.get("by_negative_type", {})
    proposed = {}
    proposed.update(by_kind.get(str(query.get("kind") or ""), {}))
    proposed.update(by_negative_type.get(str(query.get("negative_type") or ""), {}))
    for key, value in proposed.items():
        resolved.setdefault(key, value)
    return resolved


def load_dataset(path: Path) -> dict:
    """Load a dataset, resolving an optional reviewable overlay on top of a base file."""
    dataset = json.loads(path.read_text(encoding="utf-8"))
    base_reference = dataset.get("base_dataset")
    if not base_reference:
        return dataset

    base_path = Path(base_reference)
    if not base_path.is_absolute():
        base_path = path.parent / base_path
    resolved = load_dataset(base_path.resolve())

    base_queries = [dict(query) for query in resolved.get("queries", [])]
    overrides = dataset.get("query_overrides", {})
    known_ids = {str(query.get("id")) for query in base_queries}
    unknown_overrides = sorted(set(overrides) - known_ids)
    if unknown_overrides:
        raise ValueError(f"query_overrides references unknown query ids: {', '.join(unknown_overrides)}")

    contract_defaults = dataset.get("contract_defaults", {})
    merged_queries = []
    for query in base_queries:
        query_id = str(query.get("id"))
        merged = dict(query)
        merged.update(overrides.get(query_id, {}))
        merged_queries.append(_apply_contract_defaults(merged, contract_defaults))

    additional = [
        _apply_contract_defaults(dict(query), contract_defaults)
        for query in dataset.get("additional_queries", [])
    ]
    additional_ids = [str(query.get("id")) for query in additional]
    duplicate_ids = sorted({query_id for query_id in additional_ids if query_id in known_ids or additional_ids.count(query_id) > 1})
    if duplicate_ids:
        raise ValueError(f"additional_queries contains duplicate query ids: {', '.join(duplicate_ids)}")
    merged_queries.extend(additional)

    overlay_control_keys = {
        "base_dataset", "query_overrides", "additional_queries", "queries", "contract_defaults",
    }
    resolved.update({key: value for key, value in dataset.items() if key not in overlay_control_keys})
    resolved["queries"] = merged_queries
    resolved["resolved_from"] = {
        "base_dataset": str(base_path.resolve()),
        "overlay_dataset": str(path.resolve()),
    }
    return resolved


def evaluation_contract(query: dict) -> dict:
    """Return the task-specific contract used to judge this query.

    Legacy datasets are mapped conservatively so old reports remain readable. New
    datasets should provide explicit fields instead of relying on these defaults.
    """
    explicit = "evaluation_contract" in query
    if explicit:
        return {
            "task_family": str(query.get("task_family") or "unspecified"),
            "evaluation_contract": str(query["evaluation_contract"]),
            "relevance_set_status": str(query.get("relevance_set_status") or "missing"),
            "legacy_inferred": False,
        }

    kind = str(query.get("kind") or "")
    if kind in {"exact_title", "exact_event"}:
        family, contract = "item_navigation", "ranked_retrieval"
    elif kind in {"broad_recent_trend", "source_and_topic"}:
        family, contract = "trend_discovery", "discovery_ranking"
    elif kind == "event_cluster":
        family, contract = "relation_exploration", "diagnostic_only"
    elif kind == "unanswerable_control" or query.get("answerable") is False:
        family, contract = "claim_verification", "legacy_unanswerable"
    else:
        family, contract = "evidence_research", "ranked_retrieval"
    return {
        "task_family": family,
        "evaluation_contract": contract,
        "relevance_set_status": "sampled",
        "legacy_inferred": True,
    }


def assess_snapshot(target: dict | None, observed: dict | None, *, directional: bool = False) -> dict:
    """Decide whether an evaluation may compare its labels with the current index."""
    target = dict(target or {})
    observed = dict(observed or {})
    target_date = str(target.get("latest_corpus_date") or "")
    observed_date = str(observed.get("latest_corpus_date") or "")
    target_revision = str(target.get("corpus_revision") or "")
    observed_revision = str(observed.get("corpus_revision") or "")
    mismatches = []
    if target_date and target_date != observed_date:
        mismatches.append("latest_corpus_date")
    if target_revision and observed_revision and target_revision != observed_revision:
        mismatches.append("corpus_revision")
    if target_date and not observed_date:
        mismatches.append("observed_latest_corpus_date_missing")

    if mismatches:
        status = "mismatched_directional" if directional else "mismatch_blocked"
        return {
            "status": status,
            "can_run": directional,
            "release_gate_eligible": False,
            "mismatches": mismatches,
            "target": target,
            "observed": observed,
        }
    if target_revision and not observed_revision:
        return {
            "status": "matched_revision_unobserved",
            "can_run": True,
            "release_gate_eligible": False,
            "mismatches": [],
            "target": target,
            "observed": observed,
            "revision_observability": "unavailable",
        }
    return {
        "status": "matched",
        "can_run": True,
        "release_gate_eligible": True,
        "mismatches": [],
        "target": target,
        "observed": observed,
        "revision_observability": "matched" if target_revision else "not_required",
    }


def inspect_vector_snapshot(vector: VectorStore) -> dict:
    """Read only the observable vector-generation facts needed by the eval gate."""
    payload = vector.collection.get(include=["metadatas"])
    metadatas = list(payload.get("metadatas") or [])
    dates = sorted(
        {
            str(metadata.get("date") or "")
            for metadata in metadatas
            if isinstance(metadata, dict) and metadata.get("date")
        }
    )
    return {
        "latest_corpus_date": dates[-1] if dates else "",
        "document_count": len(metadatas),
        "corpus_revision": "",
    }


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


def metric_ceiling(query: dict, default_k: int = 10) -> dict:
    """Return the best mathematically possible P/R/F1 for a query's metric cutoff."""
    cutoff = max(0, int(query.get("metric_cutoff", default_k)))
    contract = evaluation_contract(query)
    if contract["evaluation_contract"] in {"diagnostic_only", "future_claim_classification"}:
        return {
            "metric_cutoff": cutoff,
            "precision_at_k": None,
            "recall_at_k": None,
            "f1_at_k": None,
            "scored": False,
            "unscored_reason": _diagnostic_reason(query, contract),
        }
    if not query.get("answerable", True):
        return {
            "metric_cutoff": cutoff,
            "precision_at_k": None,
            "recall_at_k": None,
            "f1_at_k": None,
            "correct_rejection_rate": 1.0,
        }

    relevant_count = len({result_identity(item) for item in query.get("relevant", [])})
    true_positive = min(relevant_count, cutoff)
    precision = true_positive / cutoff if cutoff else 0.0
    recall = true_positive / relevant_count if relevant_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "metric_cutoff": cutoff,
        "precision_at_k": round(precision, 4),
        "recall_at_k": round(recall, 4),
        "f1_at_k": round(f1, 4),
    }


def _diagnostic_reason(query: dict, contract: dict) -> str:
    if contract["evaluation_contract"] == "future_claim_classification":
        return "claim_labels_missing"
    if str(query.get("negative_type") or "") == "entity_absent":
        return "evidence_sufficiency_gate_missing"
    return "task_contract_not_implemented"


def apply_query_contract(plan, query: dict):
    """Apply the dataset's explicit time contract over inferred query defaults."""
    policy = query.get("time_policy")
    if policy == "strict_recent":
        days = max(1, int(query.get("time_window_days", 7)))
        return replace(
            plan,
            time_window={
                "label": "recent_corpus_first",
                "days": days,
                "requires_date_filter": True,
            },
        )
    if policy in {"not_limited", "current_relevance"}:
        return replace(
            plan,
            time_window={
                "label": "not_limited",
                "days": None,
                "requires_date_filter": False,
            },
        )
    return plan


def score_query(query: dict, retrieved: list[dict], k: int) -> dict:
    """Score one query using frozen URL-level relevance judgments."""
    contract = evaluation_contract(query)
    expected = {result_identity(item): int(item.get("grade", 1)) for item in query.get("relevant", [])}
    unique_retrieved = []
    seen = set()
    for item in retrieved[:k]:
        identity = result_identity(item)
        if identity in seen:
            continue
        seen.add(identity)
        unique_retrieved.append((identity, item))

    if contract["evaluation_contract"] in {"diagnostic_only", "future_claim_classification"}:
        reason = _diagnostic_reason(query, contract)
        return {
            "query_id": query.get("id"),
            "answerable": bool(query.get("answerable", True)),
            "metric_cutoff": k,
            "returned": len(unique_retrieved),
            "scored": False,
            "query_success": None,
            "precision_at_k": None,
            "recall_at_k": None,
            "f1_at_k": None,
            "mrr": None,
            "ndcg_at_k": None,
            "matched": [],
            "task_family": contract["task_family"],
            "evaluation_contract": contract["evaluation_contract"],
            "relevance_set_status": contract["relevance_set_status"],
            "legacy_contract_inferred": contract["legacy_inferred"],
            "unscored_reason": reason,
        }

    answerable = bool(query.get("answerable", True))
    if not answerable:
        return {
            "query_id": query.get("id"),
            "answerable": False,
            "metric_cutoff": k,
            "returned": len(unique_retrieved),
            "scored": True,
            "correct_rejection": len(unique_retrieved) == 0,
            "query_success": len(unique_retrieved) == 0,
            "precision_at_k": None,
            "recall_at_k": None,
            "f1_at_k": None,
            "mrr": None,
            "ndcg_at_k": None,
            "matched": [],
            "task_family": contract["task_family"],
            "evaluation_contract": contract["evaluation_contract"],
            "relevance_set_status": contract["relevance_set_status"],
            "legacy_contract_inferred": contract["legacy_inferred"],
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
        "metric_cutoff": k,
        "returned": len(unique_retrieved),
        "scored": True,
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
        "task_family": contract["task_family"],
        "evaluation_contract": contract["evaluation_contract"],
        "relevance_set_status": contract["relevance_set_status"],
        "legacy_contract_inferred": contract["legacy_inferred"],
    }


def _aggregate_scored_rows(rows: list[dict], k: int | None = None) -> dict:
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
    fallback_cutoff = 10 if k is None else k
    cutoff_total = sum(max(0, int(row.get("metric_cutoff", fallback_cutoff))) for row in answerable)
    micro_precision = tp / cutoff_total if cutoff_total else 0.0
    micro_recall = tp / relevant if relevant else 0.0
    micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall) if micro_precision + micro_recall else 0.0
    return {
        "scoreable_count": total,
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "query_success_accuracy": round(query_successes / total, 4) if total else 0.0,
        "correct_rejection_rate": round(sum(bool(row.get("correct_rejection")) for row in unanswerable) / len(unanswerable), 4) if unanswerable else None,
        "metric_cutoff_total": cutoff_total,
        "macro": macro,
        "micro": {
            "true_positive": tp,
            "relevant_total": relevant,
            "precision_at_k": round(micro_precision, 4),
            "recall_at_k": round(micro_recall, 4),
            "f1_at_k": round(micro_f1, 4),
        },
    }


def summarize(rows: list[dict], k: int | None = None) -> dict:
    """Summarize only comparable scored rows, then expose diagnostics separately."""
    scoreable = [row for row in rows if row.get("scored", True)]
    diagnostics = [row for row in rows if not row.get("scored", True)]
    aggregate = _aggregate_scored_rows(scoreable, k)
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row.get("task_family") or "legacy")].append(row)

    by_task_family = {}
    for family, family_rows in sorted(grouped.items()):
        family_scored = [row for row in family_rows if row.get("scored", True)]
        family_diagnostics = [row for row in family_rows if not row.get("scored", True)]
        family_aggregate = _aggregate_scored_rows(family_scored, k)
        by_task_family[family] = {
            "query_count": len(family_rows),
            "scoreable_count": len(family_scored),
            "diagnostic_count": len(family_diagnostics),
            **family_aggregate,
        }

    reasons = Counter(
        str(row.get("unscored_reason") or "unspecified")
        for row in diagnostics
    )
    return {
        "query_count": len(rows),
        "scoreable_query_count": len(scoreable),
        "diagnostic_query_count": len(diagnostics),
        "not_a_release_gate": True,
        **aggregate,
        "by_task_family": by_task_family,
        "unscored_reason_counts": dict(sorted(reasons.items())),
    }


async def run_dataset(
    dataset: dict,
    *,
    persist_dir: str | None = None,
    retrieval_mode: str = "hybrid",
    lexical_path: str | None = None,
    directional: bool = False,
) -> dict:
    # Keep URL scoring and frozen-run evaluation importable without database,
    # vector-store, or model dependencies. Runtime adapters belong only here.
    from rag.citations import retrieve_citations_with_status
    from rag.graphrag.driver import Neo4jDriver
    from rag.retrieval_planning import build_metadata_filter, source_diversity_cap
    from rag.retriever.hybrid import HybridRetriever
    from rag.retriever.lexical_store import LexicalStore
    from rag.retriever.vector_only import VectorOnlyRetriever
    from rag.retriever.vector_store import VectorStore

    metric_policy = dataset.get("metric_policy", {})
    default_k = int(metric_policy.get("default_k", metric_policy.get("k", 10)))
    snapshot = dataset.get("target_snapshot") or dataset.get("snapshot", {})
    latest_date = snapshot.get("latest_corpus_date")
    vector = VectorStore(persist_dir) if persist_dir else VectorStore()
    resolved_lexical_path = (
        Path(lexical_path)
        if lexical_path
        else Path(persist_dir) / "lexical.sqlite3" if persist_dir else None
    )
    lexical = None
    graph = None
    rows = []
    try:
        lexical = (
            LexicalStore(resolved_lexical_path)
            if resolved_lexical_path and resolved_lexical_path.exists()
            else None
        )
        observed_snapshot = inspect_vector_snapshot(vector)
        snapshot_assessment = assess_snapshot(snapshot, observed_snapshot, directional=directional)
        if not snapshot_assessment["can_run"]:
            raise ValueError(
                "Evaluation snapshot mismatch. Rebuild the index to the labelled corpus snapshot, "
                "or pass --directional for a non-release comparison."
            )
        if retrieval_mode == "vector-only":
            retriever = VectorOnlyRetriever(vector, lexical_store=lexical)
        elif retrieval_mode == "hybrid":
            graph = Neo4jDriver()
            await graph.connect()
            retriever = HybridRetriever(vector, graph, lexical_store=lexical)
        else:
            raise ValueError(f"Unsupported retrieval mode: {retrieval_mode}")
        for query in dataset.get("queries", []):
            k = max(1, int(query.get("metric_cutoff", default_k)))
            plan = apply_query_contract(analyze_query(query["query"]), query)
            where = build_metadata_filter(plan, latest_date)
            outcome = await retrieve_citations_with_status(
                retriever,
                plan.retrieval_query,
                k=k,
                where=where,
                prefer_recent=plan.time_window.get("label") == "recent_corpus_first",
                latest_date=latest_date,
                graph_requirement=plan.graph_requirement,
                source_cap=source_diversity_cap(plan),
            )
            scored = score_query(query, outcome.citations, k)
            scored.update({
                "query": query["query"],
                "kind": query.get("kind"),
                "retrieval_status": outcome.status,
                "retrieval_error_code": outcome.error_code,
                "retrieval_channel_status": outcome.channel_status,
                "elapsed_ms": round(outcome.elapsed_ms, 2),
                "metadata_filter": where,
                "query_plan": plan.to_dict(),
                "metric_ceiling": metric_ceiling(query, default_k),
                "retrieved": outcome.citations,
            })
            rows.append(scored)
    finally:
        if graph is not None:
            await graph.close()
        if lexical is not None:
            lexical.close()
        vector.close()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset.get("dataset_id"),
        "label_tier": dataset.get("label_tier"),
        "needs_human_review": dataset.get("needs_human_review", True),
        "retrieval_mode": retrieval_mode,
        "target_snapshot": snapshot,
        "observed_snapshot": observed_snapshot,
        "snapshot_assessment": snapshot_assessment,
        "release_gate_eligible": snapshot_assessment["release_gate_eligible"],
        "summary": summarize(rows, default_k),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run URL-labelled retrieval quality evaluation.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--persist-dir")
    parser.add_argument("--lexical-path")
    parser.add_argument("--mode", choices=("vector-only", "hybrid"), default="hybrid")
    parser.add_argument(
        "--directional",
        action="store_true",
        help="Allow an explicitly non-release comparison when index and label snapshots differ.",
    )
    args = parser.parse_args()
    dataset = load_dataset(args.dataset)
    result = asyncio.run(
        run_dataset(
            dataset,
            persist_dir=args.persist_dir,
            retrieval_mode=args.mode,
            lexical_path=args.lexical_path,
            directional=args.directional,
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
