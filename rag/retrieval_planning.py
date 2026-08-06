"""Build retrieval filters from query-understanding plans."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path


SOURCE_ALIASES = {
    "Product Hunt": ["Product Hunt"],
    "Anthropic": ["Anthropic"],
}

SOURCE_FAMILY_FILTERS = {
    "GitHub": {"source_family": "GitHub"},
}


def build_metadata_filter(plan, latest_corpus_date: str | None = None) -> dict | None:
    """Build a Chroma-compatible metadata filter from a query plan."""
    clauses = []

    content_type_filter = _build_content_type_filter(plan)
    if content_type_filter:
        clauses.append(content_type_filter)

    source_filter = _build_source_filter(getattr(plan, "sources", []))
    if source_filter:
        clauses.append(source_filter)

    date_filter = _build_date_filter(getattr(plan, "time_window", {}), latest_corpus_date)
    if date_filter:
        clauses.append(date_filter)

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _build_content_type_filter(plan) -> dict | None:
    """Route broad trend discovery to structured candidates, not report boilerplate."""
    has_focus = any(
        getattr(plan, field, [])
        for field in ("topics", "entities", "sources")
    )
    if getattr(plan, "intent", "") == "recent_trend" and not has_focus:
        return {"content_type": "topic_candidate"}
    return None


def load_latest_corpus_date(manifest_path: Path | None = None) -> str | None:
    """Read the latest corpus date from manifest.json when available."""
    path = manifest_path or Path(__file__).resolve().parent.parent / "manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    dates = manifest.get("dates")
    if not isinstance(dates, list) or not dates:
        return None

    first = dates[0]
    if not isinstance(first, dict):
        return None

    value = first.get("date")
    return value if isinstance(value, str) and value else None


def _build_source_filter(sources: list[str]) -> dict | None:
    clauses = [SOURCE_FAMILY_FILTERS[source] for source in sources if source in SOURCE_FAMILY_FILTERS]
    values = []
    for source in sources:
        if source in SOURCE_FAMILY_FILTERS:
            continue
        values.extend(SOURCE_ALIASES.get(source, [source]))
    values = _unique(values)

    if len(values) == 1:
        clauses.append({"source": values[0]})
    elif len(values) > 1:
        clauses.append({"source": {"$in": values}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$or": clauses}


def _build_date_filter(time_window: dict, latest_corpus_date: str | None) -> dict | None:
    if not latest_corpus_date:
        return None

    if time_window.get("label") not in {"last_7_days", "recent_corpus_first"}:
        return None

    days = int(time_window.get("days") or 7)
    end = date.fromisoformat(latest_corpus_date)
    start = end - timedelta(days=days - 1)
    values = [
        (start + timedelta(days=offset)).isoformat()
        for offset in range(days)
    ]
    return {"date": {"$in": values}}


def _unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
