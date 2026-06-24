"""Deterministic source relevance and coarse claim-support review."""

from __future__ import annotations

import re
from collections import Counter


RAG_CORE_TERMS = (
    "retrieval-augmented generation",
    "retrieval augmented generation",
    "retrieval-augmented",
    " rag ",
    "(rag)",
    "/rag",
)

RAG_CLAIM_TERMS = (
    "benchmark",
    "evaluation",
    "eval",
    "observability",
    "graph",
    "agentic",
    "hybrid",
    "tools",
    "workflow",
)

RAG_NEGATIVE_TERMS = (
    "augmented reality",
    "virtual reality",
    "aspergillus",
    "hydroclimate",
    "antifungal",
    "security operations",
    "soc roles",
)


def classify_source_relevance(citation: dict, topic: str = "") -> dict:
    """Classify whether a citation supports the current topic and claim family."""
    if citation.get("evidence_type") != "external":
        return {
            "citation_id": _citation_id(citation),
            "source": citation.get("source", ""),
            "relevance_label": "not_applicable",
            "relevance_score": 0.0,
            "relevance_reasons": ["non_external_citation"],
        }

    text = _citation_text(citation)
    reasons = []
    if topic.strip().casefold() == "rag":
        if any(term in text for term in RAG_NEGATIVE_TERMS):
            return _result(citation, "irrelevant_context", 0.05, ["negative_topic_match"])
        core_matches = [term.strip() for term in RAG_CORE_TERMS if _term_matches(term, text)]
        claim_matches = [term for term in RAG_CLAIM_TERMS if _term_matches(term, text)]
        if core_matches:
            reasons.append("rag_core_match")
        if claim_matches:
            reasons.append("claim_term_match")
        strong_source = citation.get("source_quality") in {"official", "academic", "developer", "trusted_media"}
        if core_matches and len(set(claim_matches)) >= 2 and strong_source:
            return _result(citation, "direct_support", 0.85, reasons)
        if core_matches and claim_matches:
            return _result(citation, "partial_support", 0.65, reasons)
        if core_matches:
            return _result(citation, "weak_context", 0.45, reasons)
        return _result(citation, "irrelevant_context", 0.1, ["missing_topic_match"])

    topic_terms = [term for term in re.split(r"\W+", topic.casefold()) if len(term) >= 3]
    matches = [term for term in topic_terms if term in text]
    if len(matches) >= 2:
        return _result(citation, "partial_support", 0.6, ["topic_term_match"])
    if matches:
        return _result(citation, "weak_context", 0.4, ["weak_topic_term_match"])
    return _result(citation, "irrelevant_context", 0.1, ["missing_topic_match"])


def summarize_source_relevance(citations: list[dict], topic: str = "") -> dict:
    """Summarize relevance labels for external citations."""
    external = [citation for citation in citations if citation.get("evidence_type") == "external"]
    reviews = [classify_source_relevance(citation, topic=topic) for citation in external]
    counts = dict(sorted(Counter(review["relevance_label"] for review in reviews).items()))
    return {
        "topic": topic,
        "external_count": len(external),
        "relevance_counts": counts,
        "relevance_status": _relevance_status(counts, len(external)),
        "reviews": reviews,
    }


def inspect_trend_brief_source_relevance(markdown: str, topic: str = "") -> dict:
    """Inspect source relevance from a saved Trend Brief Markdown artifact."""
    source_quality = _extract_source_quality_by_source(markdown)
    citations = []
    for row in _extract_evidence_table_rows(markdown):
        if row.get("evidence_type") != "external":
            continue
        row["source_quality"] = source_quality.get(row.get("source", ""), "generic")
        citations.append(row)
    return summarize_source_relevance(citations, topic=topic)


def _relevance_status(counts: dict, external_count: int) -> str:
    if external_count == 0:
        return "internal_only"
    if counts.get("irrelevant_context"):
        return "mixed_relevance"
    if counts.get("direct_support") or counts.get("partial_support"):
        return "relevance_verified"
    return "weak_relevance_only"


def _result(citation: dict, label: str, score: float, reasons: list[str]) -> dict:
    return {
        "citation_id": _citation_id(citation),
        "source": citation.get("source", ""),
        "title": citation.get("title", ""),
        "url": citation.get("url", ""),
        "source_quality": citation.get("source_quality", ""),
        "relevance_label": label,
        "relevance_score": score,
        "relevance_reasons": reasons,
    }


def _citation_id(citation: dict) -> str:
    return str(citation.get("citation_id") or citation.get("url") or "")


def _citation_text(citation: dict) -> str:
    text = " ".join(str(citation.get(field, "")) for field in ("title", "url", "excerpt"))
    return f" {text.casefold()} "


def _term_matches(term: str, text: str) -> bool:
    cleaned = term.strip().casefold()
    if not cleaned:
        return False
    if " " in cleaned or "-" in cleaned or "/" in cleaned or "(" in cleaned:
        return cleaned in text
    return bool(re.search(rf"\b{re.escape(cleaned)}\b", text))


def _extract_source_quality_by_source(markdown: str) -> dict:
    qualities = {}
    in_review = False
    for line in markdown.splitlines():
        if line.strip() == "## Source Quality Review":
            in_review = True
            continue
        if in_review and line.startswith("## "):
            break
        if not in_review:
            continue
        match = re.match(r"-\s+([^:]+):\s+[^/]+/\s+(\S+)", line)
        if match:
            qualities[match.group(1).strip()] = match.group(2).strip()
    return qualities


def _extract_evidence_table_rows(markdown: str) -> list[dict]:
    rows = []
    in_table = False
    for line in markdown.splitlines():
        if line.strip() == "## Evidence Table":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        if "Evidence Type" in line or re.fullmatch(r"\|\s*[-: ]+\|.*", line):
            continue
        cells = [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line)]
        cells = [cell for cell in cells if cell]
        if len(cells) < 6 or "No usable evidence" in line:
            continue
        rows.append({
            "date": cells[0],
            "source": cells[1],
            "title": cells[2],
            "evidence_type": cells[3],
            "citation_id": cells[4],
            "url": cells[4] if cells[4].startswith("http") else "",
            "excerpt": cells[5],
        })
    return rows
