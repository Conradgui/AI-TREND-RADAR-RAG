"""Deterministic request-scoped web-search policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date


_INTERNAL_ONLY_PHRASES = (
    "只基于内部",
    "仅基于内部",
    "只看内部",
    "不要联网",
    "无需联网",
    "do not search the web",
    "without web search",
)

_EXPLICIT_WEB_PHRASES = (
    "联网搜索",
    "联网查",
    "查官网",
    "搜索外部",
    "核实最新",
    "web search",
    "search online",
)


@dataclass(frozen=True)
class WebSearchDecision:
    requested_mode: str
    effective_mode: str
    should_search: bool
    reason: str
    retrieval_status: str
    intent_constraint: str = "none"
    evidence_quality_status: str = "INSUFFICIENT"
    evidence_gaps: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def decide_web_search(
    plan,
    *,
    requested_mode: str,
    retrieval_status: str,
    citations: list[dict],
    capability_available: bool,
    today: str | None = None,
) -> WebSearchDecision:
    """Resolve capability, user constraint, retrieval state, and freshness."""
    requested = requested_mode if requested_mode in {"auto", "always", "never"} else "auto"
    question = str(getattr(plan, "original_question", ""))
    lowered = question.casefold()
    intent_constraint = (
        "internal_only"
        if any(phrase.casefold() in lowered for phrase in _INTERNAL_ONLY_PHRASES)
        else "none"
    )
    quality_status, quality_gaps = _evaluate_internal_evidence(
        plan,
        retrieval_status=retrieval_status,
        citations=citations,
        today=today,
    )

    def decision(effective_mode: str, should_search: bool, reason: str) -> WebSearchDecision:
        return WebSearchDecision(
            requested,
            effective_mode,
            should_search,
            reason,
            retrieval_status,
            intent_constraint,
            quality_status,
            tuple(quality_gaps),
        )

    if not capability_available:
        return decision("never", False, "capability_unavailable")
    if intent_constraint == "internal_only":
        return decision("never", False, "internal_only_constraint")
    if requested == "never":
        return decision("never", False, "request_mode_never")
    if requested == "always" or any(phrase.casefold() in lowered for phrase in _EXPLICIT_WEB_PHRASES):
        return decision("always", True, "user_forced")
    if retrieval_status in {"error", "timeout"}:
        return decision("auto", False, f"internal_{retrieval_status}")
    if retrieval_status == "empty":
        return decision("auto", True, "internal_empty")
    if bool(getattr(plan, "needs_web_search", False)):
        return decision("auto", True, "query_requires_web")
    if _has_freshness_gap(plan, citations, today=today):
        return decision("auto", True, "freshness_gap")
    if quality_status == "PARTIAL":
        return decision("auto", True, "internal_partial")
    if quality_status == "INSUFFICIENT":
        return decision("auto", True, "internal_empty")
    return decision("auto", False, "internal_ready")


def _evaluate_internal_evidence(plan, *, retrieval_status: str, citations: list[dict], today: str | None) -> tuple[str, list[str]]:
    if retrieval_status in {"error", "timeout"}:
        return "SYSTEM_ERROR", [f"retrieval_{retrieval_status}"]
    if retrieval_status == "empty" or not citations:
        return "INSUFFICIENT", ["no_citation_ready_evidence"]

    gaps: list[str] = []
    required_fields = ("date", "source", "title", "citation_id", "excerpt")
    if not any(all(citation.get(field) for field in required_fields) for citation in citations):
        gaps.append("citation_fields_incomplete")

    required_entities = {str(entity).casefold() for entity in (getattr(plan, "entities", []) or []) if entity}
    if required_entities:
        covered_entities: set[str] = set()
        for citation in citations:
            raw_entities = citation.get("entities") or []
            if isinstance(raw_entities, str):
                raw_entities = [raw_entities]
            covered_entities.update(str(entity).casefold() for entity in raw_entities if entity)
        if not required_entities.issubset(covered_entities):
            gaps.append("entity_coverage_unverified")

    if _has_freshness_gap(plan, citations, today=today):
        gaps.append("relevant_evidence_outside_time_window")
    return ("PARTIAL", gaps) if gaps else ("READY", [])


def _has_freshness_gap(plan, citations: list[dict], *, today: str | None) -> bool:
    time_window = getattr(plan, "time_window", {}) or {}
    if time_window.get("label") not in {"recent_corpus_first", "last_7_days"}:
        return False

    try:
        reference_date = date.fromisoformat(today) if today else date.today()
    except ValueError:
        reference_date = date.today()
    allowed_days = int(time_window.get("days") or 14)

    parsed_dates = []
    for citation in citations:
        raw = citation.get("effective_event_date") or citation.get("date")
        try:
            parsed = date.fromisoformat(str(raw))
        except (TypeError, ValueError):
            continue
        if parsed <= reference_date:
            parsed_dates.append(parsed)

    if not parsed_dates:
        return True
    return (reference_date - max(parsed_dates)).days > allowed_days
