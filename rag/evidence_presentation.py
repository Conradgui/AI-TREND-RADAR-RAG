"""Turn canonical request evidence into a stable user-facing presentation."""

from __future__ import annotations

import re

from rag.external_source_admission import canonicalize_url


_EVIDENCE_MARKER = re.compile(r"\[(E\d+)\]")


def build_evidence_presentation(
    answer: str,
    citations: list[dict],
    *,
    search_references: list[dict] | None = None,
    internal_retrieval_status: str = "ready",
    web_search_status: str = "not_attempted",
) -> dict:
    """Derive I/W labels only after the final displayed citations are known.

    Canonical E identifiers remain unchanged in ``answer`` and citation records;
    display labels are an additional presentation contract for the dashboard.
    """
    internal_index = 0
    external_index = 0
    display_map: dict[str, str] = {}
    displayed_citations: list[dict] = []

    for citation in citations:
        record = dict(citation)
        evidence_id = str(record.get("evidence_id", "")).strip()
        if record.get("evidence_type") == "external":
            external_index += 1
            label = f"W{external_index}"
        else:
            internal_index += 1
            label = f"I{internal_index}"
        record["display_label"] = label
        if evidence_id:
            display_map[evidence_id] = label
        displayed_citations.append(record)

    def replace_marker(match: re.Match[str]) -> str:
        evidence_id = match.group(1)
        label = display_map.get(evidence_id)
        if not label:
            return match.group(0)
        return f"[{label} 🌐]" if label.startswith("W") else f"[{label}]"

    display_body = _EVIDENCE_MARKER.sub(replace_marker, answer or "")
    if internal_retrieval_status in {"error", "timeout"} and external_index:
        disclosure = "🌐 仅外部证据（内部检索失败）"
    elif web_search_status == "failed":
        disclosure = (
            "⚠️ 已尝试联网但失败；以下仅展示内部语料"
            if internal_index
            else "⚠️ 已尝试联网但失败；当前没有可用于回答的证据"
        )
    elif web_search_status == "degraded":
        disclosure = (
            "⚠️ 已联网检索但没有结果达到正式引用标准；以下仅展示内部语料"
            if internal_index
            else "⚠️ 已联网检索但没有结果达到正式引用标准"
        )
    elif internal_index and external_index:
        disclosure = "🌐 已联网补充（内部语料优先）"
    elif external_index:
        disclosure = "🌐 仅外部证据（内部语料无相关结果）"
    elif internal_index:
        disclosure = "📚 仅内部语料"
    else:
        disclosure = ""

    display_answer = f"{disclosure}\n\n{display_body}" if disclosure else display_body
    citation_urls = {
        canonicalize_url(str(item.get("canonical_url") or item.get("url") or ""))
        for item in displayed_citations
        if item.get("canonical_url") or item.get("url")
    }
    references = []
    seen_reference_urls: set[str] = set()
    for item in search_references or []:
        if not isinstance(item, dict):
            continue
        record = dict(item)
        canonical_url = canonicalize_url(str(record.get("canonical_url") or record.get("url") or ""))
        if canonical_url and (canonical_url in citation_urls or canonical_url in seen_reference_urls):
            continue
        if canonical_url:
            seen_reference_urls.add(canonical_url)
        references.append(record)

    return {
        "display_answer": display_answer,
        "citations": displayed_citations,
        "evidence_display_map": display_map,
        "search_references": references,
        "source_summary": {
            "internal_citations": internal_index,
            "external_citations": external_index,
            "search_references": len(references),
        },
    }
