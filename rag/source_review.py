"""Deterministic source role and conflict guidance for citations."""

from __future__ import annotations


PRIMARY_QUALITIES = {"official", "academic", "developer"}
SUPPORTING_QUALITIES = {"trusted_media"}
WEAK_QUALITIES = {"generic", "social"}


def build_source_review(citations: list[dict]) -> dict:
    """Build deterministic source guidance for the answer prompt."""
    external = [citation for citation in citations if citation.get("evidence_type") == "external"]
    source_roles = [_source_role(citation, index) for index, citation in enumerate(external, 1)]
    primary_count = sum(1 for role in source_roles if role["role"] == "primary_evidence")
    supporting_count = sum(1 for role in source_roles if role["role"] == "supporting_context")
    weak_count = sum(1 for role in source_roles if role["role"] == "weak_context")

    if not external:
        status = "internal_only"
        instruction = "No external source conflict to resolve; answer only from internal corpus evidence."
    elif primary_count and weak_count:
        status = "mixed_quality"
        instruction = (
            "Use official, academic, or developer sources as primary evidence. "
            "Treat generic or social sources as context only unless confirmed by primary sources."
        )
    elif primary_count:
        status = "primary_sources_available"
        instruction = "Use primary-quality external sources for strong external claims."
    elif supporting_count and not weak_count:
        status = "supporting_only"
        instruction = "Trusted media can support cautious claims, but avoid presenting it as primary proof."
    else:
        status = "weak_only"
        instruction = "External evidence is weak; state uncertainty and avoid strong factual claims."

    return {
        "status": status,
        "external_count": len(external),
        "primary_count": primary_count,
        "supporting_count": supporting_count,
        "weak_count": weak_count,
        "source_roles": source_roles,
        "instruction": instruction,
    }


def format_source_review_for_prompt(review: dict) -> str:
    """Format source review guidance for the LLM prompt."""
    lines = [
        "来源审查:",
        f"- 状态: {review.get('status', '')}",
        f"- 外部来源数: {review.get('external_count', 0)}",
        f"- 主证据数: {review.get('primary_count', 0)}",
        f"- 弱上下文数: {review.get('weak_count', 0)}",
        f"- 回答要求: {review.get('instruction', '')}",
    ]
    for role in review.get("source_roles", []):
        lines.append(
            f"  - [{role.get('citation_index')}] {role.get('source', '')}: "
            f"{role.get('role', '')} | {role.get('source_quality', '')}"
        )
    return "\n".join(lines)


def _source_role(citation: dict, citation_index: int) -> dict:
    quality = citation.get("source_quality", "generic")
    if quality in PRIMARY_QUALITIES:
        role = "primary_evidence"
    elif quality in SUPPORTING_QUALITIES:
        role = "supporting_context"
    else:
        role = "weak_context"
    return {
        "citation_index": citation_index,
        "source": citation.get("source", ""),
        "title": citation.get("title", ""),
        "url": citation.get("url", ""),
        "source_quality": quality,
        "role": role,
        "needs_deep_fetch": bool(citation.get("needs_deep_fetch")),
    }
