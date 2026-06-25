"""Select usable citations from batched external evidence artifacts."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from rag.trend_brief import select_brief_citations


PRIMARY_SOURCE_QUALITIES = ("academic", "official", "developer")
SOURCE_QUALITY_RANK = {quality: index for index, quality in enumerate(PRIMARY_SOURCE_QUALITIES)}


def load_batch_evidence_trace(
    path: Path,
    *,
    topic: str,
    max_citations: int = 4,
) -> dict:
    """Load a batch evidence result and select citations suitable for a brief."""
    artifact = json.loads(path.read_text(encoding="utf-8"))
    citations = list((artifact.get("result") or {}).get("citations", []) or [])
    selected = select_batch_evidence_citations(
        citations,
        topic=topic,
        max_citations=max_citations,
    )
    quality_counts = dict(sorted(Counter(
        citation.get("source_quality", "unknown")
        for citation in citations
    ).items()))
    return {
        "attempted": True,
        "path": str(path),
        "candidate_count": len(citations),
        "selected_count": len(selected),
        "source_quality_counts": quality_counts,
        "selected_citations": selected,
        "background_candidate_count": max(0, len(citations) - len(selected)),
    }


def select_batch_evidence_citations(
    citations: list[dict],
    *,
    topic: str,
    max_citations: int = 4,
) -> list[dict]:
    """Select primary-quality, topic-relevant batch citations."""
    topic_relevant = select_brief_citations(list(citations), topic=topic)
    primary = [
        citation for citation in topic_relevant
        if citation.get("source_quality") in PRIMARY_SOURCE_QUALITIES
    ]
    deduped = _dedupe_by_url(primary)
    deduped.sort(key=_citation_rank)
    return _select_with_quality_diversity(deduped, max_citations=max_citations)


def _dedupe_by_url(citations: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for citation in citations:
        key = str(citation.get("url") or citation.get("citation_id") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(citation)
    return result


def _citation_rank(citation: dict) -> tuple[int, str, str]:
    quality = citation.get("source_quality", "")
    return (
        SOURCE_QUALITY_RANK.get(quality, len(SOURCE_QUALITY_RANK)),
        str(citation.get("source", "")),
        str(citation.get("title", "")),
    )


def _select_with_quality_diversity(citations: list[dict], *, max_citations: int) -> list[dict]:
    selected = []
    selected_urls = set()
    for quality in PRIMARY_SOURCE_QUALITIES:
        candidate = next(
            (citation for citation in citations if citation.get("source_quality") == quality),
            None,
        )
        if candidate:
            key = str(candidate.get("url") or candidate.get("citation_id") or "")
            selected.append(candidate)
            selected_urls.add(key)
        if len(selected) >= max_citations:
            return selected

    for citation in citations:
        key = str(citation.get("url") or citation.get("citation_id") or "")
        if key in selected_urls:
            continue
        selected.append(citation)
        selected_urls.add(key)
        if len(selected) >= max_citations:
            break
    return selected
