"""Conservative offline extraction of the minimum event contract.

The extractor prefers an explicit review state over inventing event semantics.
It is a shadow prototype and is not wired into production ingestion.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date

from rag.entity_identity import canonical_entity_id, legacy_infer_entity_ids, normalize_entity_name
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
    mentioned = legacy_infer_entity_ids(None, title, summary)
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
        if event_type == "business_update":
            # Comparators in financial headlines ("match SpaceX", "Apple of
            # AI") are context, not owners of the reported company update.
            subject, mentioned = list(mentioned[:1]), list(mentioned[1:])
        else:
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
        if fields["event_type"] == "business_update":
            participants = sorted(set(fields["subject_entity_ids"]))
            group_type = f"business_update:{_business_update_topic(document)}"
        else:
            participants = sorted(set([
                *fields["subject_entity_ids"], *fields["mentioned_entity_ids"],
            ]))
            group_type = fields["event_type"]
        if fields["content_kind"] == "news" and participants:
            raw_group = "|".join((
                _event_time_bucket(document, fields["event_type"]),
                group_type,
                ",".join(participants),
            ))
            fields["event_group_id"] = "event-" + hashlib.sha256(
                raw_group.encode("utf-8")
            ).hexdigest()[:12]
        else:
            fields["event_group_id"] = ""
        output.append({**document, **fields})
    return output


def _business_update_topic(document: dict) -> str:
    text = normalize_entity_name(
        f"{document.get('title') or ''} {document.get('summary') or ''}"
    )
    if "revenue" in text or "营收" in text or "收入" in text:
        return "revenue"
    if "valuation" in text or "估值" in text:
        return "valuation"
    if "ipo" in text or "上市" in text:
        return "ipo"
    return "general"


def _event_time_bucket(document: dict, event_type: str) -> str:
    raw = str(document.get("date") or document.get("report_date") or "")
    if event_type != "business_update":
        return raw
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return raw
    iso_year, iso_week, _ = parsed.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


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
    # Incidental phrases such as "model developers" or "agent interaction"
    # also occur in official research and policy announcements. Only promote
    # a row to developer content when it contains a developer-specific phrase
    # or a standalone API/SDK signal.
    developer_content_signal = any(term in text for term in (
        "developer platform", "developer documentation", "developer docs",
        "developer tools", "build test", "sdk",
    )) or bool(re.search(r"\bapi\b", text))
    if developer_content_signal:
        return "developer_content", "documentation_or_tutorial"
    if any(term in text for term in (
        "price", "pricing", "discount", "cost per token", "seat pricing",
        "configuration", "config release notes",
    )):
        return "pricing_or_configuration", "pricing_or_access"
    research_report = (
        any(term in text for term in ("paper", "study", "research report", "industry report", "论文", "研究报告"))
        or ("报告" in text and any(term in text for term in ("发布", "研究", "调研")))
        or ("report" in text and any(term in text for term in ("publish", "released", "research", "study")))
        or (
            "red team" in text
            and any(term in text for term in (
                "behavioral tendencies", "systemic failures", "multiagent systems",
            ))
        )
    )
    if research_report:
        return "research", "research_release"
    if any(term in text for term in (
        "launch", "announce", "announcement", "update", "release", "released",
        "appoint", "join", "lawsuit", "sues",
        "settlement", "dispute", "acquire", "funding", "partner",
        "incident", "disclosed", "ipo", "revenue", "valuation",
        "rolling out", "rollout", "public company", "going public",
        "reduces", "reduced", "cuts", "exodus", "tops",
        "investigation", "probe", "regulatory", "open source", "open sourcing",
        "发布", "更新", "任命", "卸任", "离职", "加入", "指控", "反击",
        "诉讼", "起诉", "争议", "收购", "融资", "合作", "调查", "监管", "开源",
    )):
        return "news", _event_type(text)
    if any(term in text for term in ("research", "proof", "研究")):
        return "research", "research_release"
    return "unknown", "other"


def _event_type(text: str) -> str:
    for event_type, terms in (
        ("safety_incident", ("cybersecurity", "security incident", "unauthorized access", "zero day")),
        ("regulatory_action", ("investigation", "probe", "regulatory", "调查", "监管", "要求参观")),
        ("model_release", ("model release", "models", "model family", "robotics 2")),
        ("litigation", ("lawsuit", "sues", "settlement", "probe", "dispute", "指控", "反击", "诉讼", "起诉", "争议", "法律程序")),
        ("leadership", ("appoint", "join", "resign", "leave", "exodus", "任命", "卸任", "离职", "加入")),
        ("partnership", ("partner", "collaboration", "合作")),
        ("acquisition", ("acquire", "acquisition", "merger", "收购", "合并")),
        ("funding", ("funding", "investment", "round", "融资", "投资")),
        ("business_update", ("ipo", "revenue", "valuation", "public company", "going public", "financing", "reduces", "reduced", "cuts", "tops")),
        ("product_launch", ("launch", "release", "announce", "announcement", "update", "rolling out", "rollout", "open source", "open sourcing", "发布", "更新", "开源")),
    ):
        if any(term in text for term in terms):
            return event_type
    return "other"


def _listing_subject(title: str) -> str:
    candidate = title.split("/", 1)[-1].strip()
    candidate = re.sub(r"[^A-Za-z0-9]+", "-", candidate).strip("-").casefold()
    return canonical_entity_id(candidate)
