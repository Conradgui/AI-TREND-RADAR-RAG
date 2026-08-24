"""Conservative offline extraction of the minimum event contract.

The extractor prefers an explicit review state over inventing event semantics.
It is a shadow prototype and is not wired into production ingestion.
"""

from __future__ import annotations

import hashlib
import re

from rag.entity_identity import canonical_entity_id, infer_entity_ids, normalize_entity_name
from rag.event_contract import source_locked_temporal_fields


_OFFICIAL_SOURCES = {
    "openai": "openai",
    "anthropic": "anthropic",
    "anthropic claude": "anthropic",
    "google": "google",
    "google deepmind": "google-deepmind",
}

_LISTING_SOURCES = ("github search", "product hunt", "hugging face")


def extract_event_fields(document: dict) -> dict:
    title = str(document.get("title") or "")
    summary = str(document.get("summary") or "")
    source = str(document.get("source") or "")
    normalized_source = normalize_entity_name(source)
    text = normalize_entity_name(f"{title} {summary}")
    mentioned = infer_entity_ids(None, title, summary)
    official_subject = _OFFICIAL_SOURCES.get(normalized_source, "")

    content_kind, event_type = _classify_content(document)
    source_role = "first_party" if official_subject else "third_party"
    if official_subject:
        subject = [canonical_entity_id(official_subject)]
        mentioned = [entity for entity in mentioned if entity not in subject]
    elif content_kind == "product_listing":
        listing_subject = _listing_subject(title)
        subject = [listing_subject] if listing_subject else []
        mentioned = [entity for entity in mentioned if entity not in subject]
    elif content_kind == "news":
        # A third-party report may still describe a multi-party event. These
        # participants are candidates for review, not confirmed causal roles.
        subject = list(mentioned)
        mentioned = []
    else:
        subject = []

    publication_date, temporal_confidence = source_locked_temporal_fields(document)

    return {
        "content_kind": content_kind,
        "source_role": source_role,
        "event_type": event_type,
        "subject_entity_ids": subject,
        "mentioned_entity_ids": mentioned,
        "publication_date": publication_date,
        "temporal_confidence": temporal_confidence,
        "extraction_status": "review_required" if content_kind == "unknown" else "extracted",
    }


def extract_event_batch(documents: list[dict]) -> list[dict]:
    """Extract fields and assign conservative, reviewable event-group candidates."""
    output = []
    for document in documents:
        fields = extract_event_fields(document)
        participants = sorted(set([
            *fields["subject_entity_ids"], *fields["mentioned_entity_ids"],
        ]))
        if fields["content_kind"] == "news" and participants:
            raw_group = "|".join((
                str(document.get("date") or document.get("report_date") or ""),
                fields["event_type"],
                ",".join(participants),
            ))
            fields["event_group_id"] = "event-" + hashlib.sha256(
                raw_group.encode("utf-8")
            ).hexdigest()[:12]
        else:
            fields["event_group_id"] = ""
        output.append({**document, **fields})
    return output


def _classify_content(document: dict) -> tuple[str, str]:
    title = str(document.get("title") or "")
    summary = str(document.get("summary") or "")
    source = str(document.get("source") or "")
    text = normalize_entity_name(f"{title} {summary}")
    source_text = normalize_entity_name(source)
    tags = " ".join(str(tag) for tag in document.get("tags") or [])
    tag_text = normalize_entity_name(tags)
    if any(source_text.startswith(prefix) for prefix in _LISTING_SOURCES):
        if any(term in text for term in ("model", "diffusers", "text to video", "image to video")):
            return "product_listing", "model_release"
        if any(term in text or term in tag_text for term in ("compatib", "comfyui")):
            return "product_listing", "compatibility"
        return "product_listing", "product_launch"
    if any(term in text for term in ("how to", "step by step", "tutorial", "guide")):
        return "tutorial", "documentation_or_tutorial"
    if any(term in text for term in ("developer", "interaction", "build test", "api", "sdk")):
        return "developer_content", "documentation_or_tutorial"
    if any(term in text for term in ("price", "pricing", "discount", "cost per token", "seat pricing")):
        return "pricing_or_configuration", "pricing_or_access"
    if any(term in text for term in ("launch", "announce", "appoint", "join", "lawsuit", "sues", "settlement", "acquire", "funding", "partner", "incident", "disclosed")):
        return "news", _event_type(text)
    if any(term in text for term in ("research", "proof", "paper")):
        return "research", "research_release"
    return "unknown", "other"


def _event_type(text: str) -> str:
    for event_type, terms in (
        ("safety_incident", ("cybersecurity", "security incident", "unauthorized access", "zero day")),
        ("model_release", ("model release", "models", "model family", "robotics 2")),
        ("litigation", ("lawsuit", "sues", "settlement", "probe")),
        ("leadership", ("appoint", "join", "resign", "leave")),
        ("partnership", ("partner", "collaboration")),
        ("acquisition", ("acquire", "acquisition", "merger")),
        ("funding", ("funding", "investment", "round")),
        ("product_launch", ("launch", "release", "announce")),
    ):
        if any(term in text for term in terms):
            return event_type
    return "other"


def _listing_subject(title: str) -> str:
    candidate = title.split("/", 1)[-1].strip()
    candidate = re.sub(r"[^A-Za-z0-9]+", "-", candidate).strip("-").casefold()
    return canonical_entity_id(candidate)
