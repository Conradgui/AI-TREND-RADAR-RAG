"""Canonical event semantics shared by extraction and evaluation."""

from __future__ import annotations


CONTRACT_VERSION = "event-contract-v2"

CONTENT_KINDS = {
    "news", "research", "tutorial", "product_listing",
    "developer_content", "pricing_or_configuration", "roundup", "unknown",
}

EVENT_TYPES = {
    "model_release", "product_launch", "partnership", "leadership",
    "acquisition", "funding", "litigation", "safety_incident",
    "research_release", "pricing_or_access", "compatibility",
    "documentation_or_tutorial", "unknown",
}

CONTENT_KIND_ALIASES = {
    "news_event": "news",
    "first_party_news": "news",
    "third_party_news": "news",
    "first_party_program_announcement": "news",
    "research": "research",
    "tutorial": "tutorial",
    "first_party_engineering_tutorial": "tutorial",
    "developer_content": "developer_content",
    "first_party_developer_content": "developer_content",
    "product_update": "developer_content",
    "project_listing": "product_listing",
    "third_party_product": "product_listing",
    "first_party_model_repository": "product_listing",
    "third_party_model_compatibility_repository": "product_listing",
    "pricing_detail": "pricing_or_configuration",
    "news_digest": "roundup",
    "roundup": "roundup",
    "unknown": "unknown",
}

EVENT_TYPE_ALIASES = {
    "cybersecurity_incident_disclosure": "safety_incident",
    "model_family_release": "model_release",
    "model_release": "model_release",
    "developer_guide": "documentation_or_tutorial",
    "engineering_tutorial": "documentation_or_tutorial",
    "how_to": "documentation_or_tutorial",
    "third_party_tool_launch": "product_launch",
    "program_launch": "product_launch",
    "feature_release": "product_launch",
    "product_launch": "product_launch",
    "pricing_and_access_program_launch": "pricing_or_access",
    "pricing_detail": "pricing_or_access",
    "model_packaging_compatibility": "compatibility",
    "compatibility": "compatibility",
    "project_listing": "unknown",
    "roundup": "unknown",
    "other": "unknown",
    "unknown": "unknown",
    "litigation": "litigation",
    "leadership": "leadership",
    "partnership": "partnership",
    "acquisition": "acquisition",
    "funding": "funding",
    "research_release": "research_release",
    "safety_incident": "safety_incident",
}


def canonical_content_kind(value: object) -> str:
    return CONTENT_KIND_ALIASES.get(str(value or "unknown"), "unknown")


def canonical_event_type(value: object) -> str:
    return EVENT_TYPE_ALIASES.get(str(value or "unknown"), "unknown")


def source_role_from_annotation(annotation: dict) -> str | None:
    explicit = str(annotation.get("source_role") or "")
    if explicit in {"first_party", "third_party", "unknown"}:
        return explicit
    old_kind = str(annotation.get("content_kind") or "")
    if old_kind.startswith("first_party_"):
        return "first_party"
    if old_kind.startswith("third_party_"):
        return "third_party"
    return None


def source_locked_temporal_fields(document: dict) -> tuple[object, str]:
    publication_date = document.get("publication_date") or None
    provenance = str(document.get("publication_date_source") or "unknown").casefold()
    if not publication_date or provenance == "unknown":
        return publication_date, "unknown"
    return publication_date, "high"


def canonicalize_expected(annotation: dict, document: dict) -> dict:
    """Translate historical labels while locking source-owned date facts."""
    publication_date, temporal_confidence = source_locked_temporal_fields(document)
    return {
        **annotation,
        "content_kind": canonical_content_kind(annotation.get("content_kind")),
        "source_role": source_role_from_annotation(annotation),
        "event_type": canonical_event_type(annotation.get("event_type")),
        "publication_date": publication_date,
        "temporal_confidence": temporal_confidence,
    }
