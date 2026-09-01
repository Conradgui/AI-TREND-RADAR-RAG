"""Conservative feedback from already-grounded answers into relation memory.

This module never calls a model. It accepts a small set of explicit
product/company sentence shapes and promotes them only when the cited record
is first-party or already carries both entity IDs.
"""

from __future__ import annotations

import re

from rag.entity_identity import (
    canonical_entity_id,
    canonical_entity_ids,
    query_entity_ids,
    related_entity_expansions,
)


_MARKER = re.compile(r"\[(E\d+)\]")
_DEVELOPMENT_TERMS = ("开发", "研发", "打造", "developed", "built")
_PRODUCT_TERMS = ("推出", "发布", "launched", "released")


def capture_relation_feedback(
    answer: str,
    citations: list[dict],
    *,
    subjects: list[str],
    memory,
) -> list[dict]:
    """Record explicit cited product relationships without delaying the answer."""
    if memory is None or not subjects:
        return []
    evidence_by_id = {
        str(record.get("evidence_id") or ""): record
        for record in citations
        if isinstance(record, dict) and record.get("evidence_id")
    }
    captured: list[dict] = []
    for line in str(answer or "").splitlines():
        marker_ids = [marker for marker in _MARKER.findall(line) if marker in evidence_by_id]
        if not marker_ids:
            continue
        folded = line.casefold()
        relation = _relation_from_line(folded)
        if not relation:
            continue
        for subject in subjects:
            subject_text = str(subject or "").strip()
            if not subject_text or subject_text.casefold() not in folded:
                continue
            source_id = canonical_entity_id(subject_text)
            targets = [
                entity_id
                for entity_id in query_entity_ids(line)
                if entity_id != source_id
            ]
            for target_id in targets:
                if _already_curated(source_id, target_id, relation):
                    continue
                evidence = [
                    _memory_evidence(evidence_by_id[marker_id], source_id, target_id)
                    for marker_id in marker_ids
                ]
                candidate = memory.observe(
                    source_id,
                    target_id,
                    relation,
                    evidence=evidence,
                    parser_version="grounded-answer/1",
                )
                if any(item["supports"] for item in evidence):
                    candidate = memory.decide(candidate["candidate_id"], "verified")
                captured.append({
                    "candidate_id": candidate["candidate_id"],
                    "from_entity_id": source_id,
                    "to_entity_id": target_id,
                    "relation": relation,
                    "status": candidate["status"],
                })
    return captured


def _relation_from_line(folded_line: str) -> str:
    if any(term in folded_line for term in _DEVELOPMENT_TERMS):
        return "developed_by"
    if any(term in folded_line for term in _PRODUCT_TERMS) or re.search(
        r"\bis\b[^。.!?]{0,80}\bproduct\b",
        folded_line,
    ):
        return "product_of"
    return ""


def _already_curated(source_id: str, target_id: str, relation: str) -> bool:
    return any(
        item["entity_id"] == target_id and item["relation"] == relation
        for item in related_entity_expansions([source_id])
    )


def _memory_evidence(record: dict, source_id: str, target_id: str) -> dict:
    citation_id = str(record.get("citation_id") or "").strip()
    locator = str(record.get("url") or record.get("canonical_url") or "").strip()
    entity_ids = set(canonical_entity_ids(record.get("entity_ids") or []))
    source_owner = canonical_entity_id(record.get("source"))
    first_party = (
        str(record.get("source_quality") or "") == "official"
        and source_owner == target_id
    )
    structured_support = source_id in entity_ids and target_id in entity_ids
    evidence = {
        "supports": bool(first_party or structured_support),
        "evidence_id": str(record.get("evidence_id") or ""),
        "source": str(record.get("source") or ""),
    }
    if locator:
        evidence["url"] = locator
    elif citation_id.startswith("ATR-"):
        evidence["atr_id"] = citation_id
    return evidence
