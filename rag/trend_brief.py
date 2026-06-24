"""Deterministic Markdown trend brief assembly."""

from __future__ import annotations

import json
import re
from html import unescape
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_BRIEF_DIR = Path("docs/rag-transformation/briefs")


def slugify_topic(topic: str) -> str:
    """Return a compact filename-safe topic slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", topic.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "topic"


def build_trend_brief_markdown(
    *,
    topic: str,
    citations: list[dict],
    graph_evidence: dict | None = None,
    source_review: dict | None = None,
    answer_policy: dict | None = None,
    latest_corpus_date: str | None = None,
    generated_at: str | None = None,
    mode: str = "local-only",
) -> str:
    """Build a reviewable Markdown trend brief from selected evidence."""
    citations = select_brief_citations(citations, topic=topic)
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    source_review = source_review or {}
    answer_policy = answer_policy or {}
    summary = summarize_brief_inputs(
        topic=topic,
        citations=citations,
        graph_evidence=graph_evidence,
        answer_policy=answer_policy,
        source_review=source_review,
    )

    lines = [
        f"# Trend Brief: {topic}",
        "",
        f"- Generated at: {generated_at}",
        f"- Corpus latest date: {latest_corpus_date or 'unknown'}",
        f"- Mode: {mode}",
        f"- Policy mode: {summary['policy_mode']}",
        "",
        "## Executive Summary",
        "",
        *_executive_summary(topic, citations, graph_evidence, answer_policy),
        "",
        "## Key Trend Themes",
        "",
        *_theme_lines(citations),
        "",
        "## Evidence Table",
        "",
        *_evidence_table(citations),
        "",
        "## Graph Relationship Summary",
        "",
        *_graph_summary_lines(graph_evidence),
        "",
        "## Source Quality Review",
        "",
        *_source_review_lines(source_review, citations),
        "",
        "## Uncertainty And Missing Evidence",
        "",
        *_uncertainty_lines(citations, graph_evidence, answer_policy),
        "",
        "## Recommended Follow-Up Actions",
        "",
        *_follow_up_lines(topic, answer_policy),
        "",
        "## Machine-Readable Appendix",
        "",
        "```json",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def summarize_brief_inputs(
    *,
    topic: str,
    citations: list[dict],
    graph_evidence: dict | None,
    answer_policy: dict | None,
    source_review: dict | None,
) -> dict:
    """Build a compact machine-readable summary for later benchmarking."""
    graph_evidence = graph_evidence or {}
    answer_policy = answer_policy or {}
    source_review = source_review or {}
    return {
        "topic": topic,
        "citation_count": len(citations),
        "evidence_types": dict(sorted(Counter(c.get("evidence_type", "unknown") for c in citations).items())),
        "citation_ids": [_citation_ref(c) for c in citations],
        "graph_counts": {
            "topic_count": int(graph_evidence.get("topic_count") or 0),
            "date_count": int(graph_evidence.get("date_count") or 0),
            "source_count": int(graph_evidence.get("source_count") or 0),
        },
        "policy_mode": answer_policy.get("mode", "unknown"),
        "external_search_required": bool(answer_policy.get("external_search_required")),
        "source_review_status": source_review.get("status", "unknown"),
        "residual_risks": _residual_risks(citations, graph_evidence, answer_policy),
    }


def save_trend_brief(markdown: str, *, topic: str, output_path: Path | None = None, date_label: str | None = None) -> Path:
    """Save a trend brief Markdown artifact and return its path."""
    if output_path is None:
        date_label = date_label or datetime.now(timezone.utc).date().isoformat()
        output_path = DEFAULT_BRIEF_DIR / f"trend-brief-{slugify_topic(topic)}-{date_label}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return output_path


def select_brief_citations(citations: list[dict], topic: str | None = None) -> list[dict]:
    """Remove low-specificity report chunks when more specific evidence exists."""
    filtered = [
        citation for citation in citations
        if _is_relevant_external_citation(citation, topic)
    ]
    has_specific_evidence = any(not _is_generic_report_chunk(citation) for citation in filtered)
    if not has_specific_evidence:
        return filtered
    return [citation for citation in filtered if not _is_generic_report_chunk(citation)]


def _executive_summary(
    topic: str,
    citations: list[dict],
    graph_evidence: dict | None,
    answer_policy: dict,
) -> list[str]:
    if not citations:
        return [
            f"- 当前内部语料不足以支持关于 {topic} 的趋势判断。",
            "- 建议先补充语料或启用明确标注的外部检索，再做结论。",
        ]

    dates = sorted({str(c.get("date", "")) for c in citations if c.get("date")})
    sources = sorted({str(c.get("source", "")) for c in citations if c.get("source")})
    lines = [
        f"- 当前简报基于 {len(citations)} 条可追踪引用，覆盖 {len(dates)} 个日期和 {len(sources)} 个来源。",
        f"- 可支持的结论应限定为：内部语料中出现了与 {topic} 相关的产品、工程或研究信号。",
    ]
    if len(citations) < 2 or len(sources) < 2:
        lines.append("- 当前证据更适合描述为单点信号，不应上升为稳定趋势。")
    else:
        lines.append("- 多个来源或日期出现相近信号时，可以谨慎描述为值得继续跟踪的趋势主题。")

    if graph_evidence:
        lines.append("- 图谱证据补充了实体、主题、日期和来源之间的覆盖关系，但不证明因果关系或市场采用。")
    if answer_policy.get("external_search_required"):
        lines.append("- 该问题仍需要外部证据确认；本地简报不能替代实时网页研究。")
    return lines[:5]


def _theme_lines(citations: list[dict]) -> list[str]:
    if not citations:
        return ["- No themes available because no usable citations were retrieved."]

    grouped = defaultdict(list)
    for citation in citations:
        key = _theme_label(citation)
        grouped[key].append(citation)

    lines = []
    for theme, items in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), str(pair[0]))):
        label = "trend candidate" if len(items) >= 2 else "emerging signal"
        evidence_ids = ", ".join(_citation_ref(item) for item in items)
        lines.append(f"- **{theme}** ({label}): evidence IDs: {evidence_ids}")
    return lines


def _evidence_table(citations: list[dict]) -> list[str]:
    lines = [
        "| Date | Source | Title | Evidence Type | Citation ID | Excerpt |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not citations:
        lines.append("|  |  | No usable evidence |  |  |  |")
        return lines
    for citation in citations:
        lines.append(
            "| "
            + " | ".join(
                _cell(_citation_field(citation, field), limit=320 if field == "excerpt" else 160)
                for field in ("date", "source", "title", "evidence_type", "citation_id", "excerpt")
            )
            + " |"
        )
    return lines


def _graph_summary_lines(graph_evidence: dict | None) -> list[str]:
    if not graph_evidence:
        return [
            "- 缺少图谱关系证据。",
            "- 因此本简报不能说明该主题是否跨日期、跨来源反复出现。",
        ]

    lines = [
        (
            f"- Entity: {graph_evidence.get('entity_label') or graph_evidence.get('entity_id') or 'unknown'}; "
            f"topics: {graph_evidence.get('topic_count', 0)}; "
            f"dates: {graph_evidence.get('date_count', 0)}; "
            f"sources: {graph_evidence.get('source_count', 0)}."
        ),
        "- 图谱证据只能证明语料中的覆盖和关联，不能证明因果关系、真实采用率或商业成功。",
    ]
    paths = graph_evidence.get("sample_paths") or []
    if paths:
        lines.append("- Sample paths:")
        for path in paths[:8]:
            lines.append(
                f"  - {path.get('entity', graph_evidence.get('entity_label', ''))} -> "
                f"{path.get('topic', '')} -> {path.get('date', '')} -> {path.get('source') or 'unknown source'}"
            )
    else:
        lines.append("- No sample paths returned.")
    return lines


def _source_review_lines(source_review: dict, citations: list[dict]) -> list[str]:
    lines = [
        f"- Status: {source_review.get('status', 'unknown')}",
        f"- Guidance: {source_review.get('instruction', 'No source-review instruction available.')}",
    ]
    if not any(c.get("evidence_type") == "external" for c in citations):
        lines.append("- 当前版本只使用内部语料；它能说明内部 Radar 捕捉到什么，不能直接证明外部事实完整性。")
    for role in source_review.get("source_roles", []):
        lines.append(
            f"- {role.get('source', '')}: {role.get('role', '')} / {role.get('source_quality', '')}"
        )
    return lines


def _uncertainty_lines(citations: list[dict], graph_evidence: dict | None, answer_policy: dict) -> list[str]:
    risks = _residual_risks(citations, graph_evidence or {}, answer_policy)
    if not risks:
        return ["- No major structural uncertainty detected, but semantic correctness still requires human review."]
    return [f"- {risk}" for risk in risks]


def _follow_up_lines(topic: str, answer_policy: dict) -> list[str]:
    lines = [
        f"- Search official/developer sources for: {topic} recent updates primary sources",
        f"- Search academic/developer references for: {topic} evaluation benchmarks",
        f"- Ask next: 哪些信号有跨来源、跨日期重复出现，哪些只是一次性热度？",
    ]
    if answer_policy.get("external_search_required"):
        lines.insert(0, "- Run live external search before making claims that require current or primary-source evidence.")
    return lines


def _residual_risks(citations: list[dict], graph_evidence: dict, answer_policy: dict) -> list[str]:
    risks = []
    if len(citations) < 2:
        risks.append("当前证据更适合描述为单点信号，不应上升为稳定趋势。")
    if citations and not any(citation.get("evidence_type") == "external" for citation in citations):
        risks.append("缺少外部一手来源；当前简报只能说明内部 Radar 语料捕捉到的信号。")
    if not graph_evidence:
        risks.append("缺少图谱关系证据，无法验证跨主题、跨日期或跨来源覆盖。")
    elif int(graph_evidence.get("date_count") or 0) < 2 or int(graph_evidence.get("source_count") or 0) < 2:
        risks.append("图谱覆盖不足，趋势语言需要降级为观察或假设。")
    if answer_policy.get("external_search_required"):
        risks.append("问题需要外部证据；当前 local-only 输出不能声称已完成实时研究。")
    risks.append("语义正确性仍需人工复核；本模块只保证结构化证据边界。")
    return risks


def _theme_label(citation: dict) -> str:
    if citation.get("evidence_type") == "graph" or citation.get("content_type") == "graph_reasoning":
        return "Graph coverage"
    if citation.get("evidence_type") == "external":
        return "External RAG references"

    haystack = " ".join(
        str(citation.get(field, ""))
        for field in ("title", "source", "category", "excerpt")
    ).casefold()
    if any(term in haystack for term in ("black box", "metadata", "verification", "eval", "benchmark", "observability")):
        return "RAG observability and evaluation"
    if any(term in haystack for term in ("github", "lightrag", "graphify", "anything-llm", "minds-platform")):
        return "Open-source RAG tools"
    if citation.get("category"):
        return str(citation["category"])
    return "Observed signals"


def _is_generic_report_chunk(citation: dict) -> bool:
    title = str(citation.get("title", "")).strip().casefold()
    source = str(citation.get("source", "")).strip().casefold()
    if citation.get("evidence_type") == "graph":
        return False
    return title in {"ai-topic-radar", "ai-trending"} and source in {"ai-topic-radar", "ai-trending"}


def _is_relevant_external_citation(citation: dict, topic: str | None) -> bool:
    if citation.get("evidence_type") != "external":
        return True
    if not topic or topic.strip().casefold() != "rag":
        return True

    text = " ".join(
        str(citation.get(field, ""))
        for field in ("title", "url", "excerpt")
    ).casefold()
    positive_terms = (
        "retrieval-augmented generation",
        "retrieval augmented generation",
        "retrieval-augmented",
        " rag ",
        "(rag)",
        "/rag",
        "rag?",
    )
    negative_terms = (
        "augmented reality",
        "virtual reality",
        "aspergillus",
        "hydroclimate",
        "antifungal",
        "southeast asia",
    )
    padded = f" {text} "
    return any(term in padded for term in positive_terms) and not any(term in padded for term in negative_terms)


def _citation_ref(citation: dict) -> str:
    if citation.get("citation_id"):
        return str(citation["citation_id"])
    if citation.get("evidence_type") == "external":
        return str(citation.get("url", ""))
    return ""


def _citation_field(citation: dict, field: str) -> object:
    if field == "date" and citation.get("evidence_type") == "external":
        return citation.get("retrieved_at", "")
    if field == "citation_id":
        return _citation_ref(citation)
    return citation.get(field, "")


def _cell(value: object, limit: int = 160) -> str:
    text = _clean_markdown_text(value)
    if len(text) > limit:
        text = f"{text[: max(0, limit - 1)].rstrip()}…"
    return text.replace("|", "\\|")


def _clean_markdown_text(value: object) -> str:
    text = unescape(str(value or ""))
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
