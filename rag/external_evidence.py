"""External evidence schema helpers for future web search."""

from __future__ import annotations

from datetime import date


REQUIRED_EXTERNAL_CITATION_FIELDS = (
    "evidence_type",
    "source",
    "title",
    "url",
    "retrieved_at",
    "excerpt",
)


def validate_external_citation(citation: dict) -> list[str]:
    """Return schema errors for an external citation candidate."""
    errors = []

    if citation.get("evidence_type") != "external":
        errors.append("invalid_evidence_type")

    for field in REQUIRED_EXTERNAL_CITATION_FIELDS:
        if not citation.get(field):
            errors.append(f"missing_{field}")

    url = citation.get("url") or ""
    if url and not url.startswith(("https://", "http://")):
        errors.append("invalid_url")

    return errors


def build_web_search_unavailable_result(query: str) -> dict:
    """Return a stable disabled-tool response for future web search calls."""
    return {
        "tool": "web_search",
        "available": False,
        "query": query,
        "reason": "not_enabled_in_current_module",
        "citations": [],
        "retrieved_at": date.today().isoformat(),
        "user_message": (
            "当前版本尚未启用联网搜索，因此不能声称已经获取外部证据。"
            "请先基于内部语料回答，并标注仍需要外部证据确认。"
        ),
    }
