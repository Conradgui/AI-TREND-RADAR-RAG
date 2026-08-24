"""One public seam from a real Query to a narrow Route Contract envelope."""

from __future__ import annotations

from typing import Protocol

from rag.narrow_route_contract_v2 import build_narrow_route_envelope


class NarrowDecisionExtractor(Protocol):
    def extract(
        self, query: str, conversation_context: str | None = None
    ) -> tuple[dict, dict]: ...


def understand_narrow_query_v1(
    query: str,
    extractor: NarrowDecisionExtractor,
    conversation_context: str | None = None,
) -> dict:
    """Produce one complete shadow contract or a safe clarification envelope."""
    original_query = query.strip()
    if not original_query:
        return _clarification("empty query", {"error_type": "EmptyQuery"})
    try:
        decisions, diagnostics = extractor.extract(original_query, conversation_context)
        envelope = build_narrow_route_envelope(
            original_query, decisions, conversation_context
        )
    except Exception as exc:
        return _clarification(
            "semantic extraction unavailable",
            {"error_type": type(exc).__name__},
        )
    return {
        **envelope,
        "diagnostics": diagnostics,
    }

def _clarification(reason: str, diagnostics: dict) -> dict:
    return {
        "status": "clarification_required",
        "contract": None,
        "reasons": [reason],
        "diagnostics": diagnostics,
    }
