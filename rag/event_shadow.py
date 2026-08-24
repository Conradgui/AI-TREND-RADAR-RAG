"""Build a reviewed event-structured shadow view without touching live indexes."""

from __future__ import annotations


EVENT_FIELDS = (
    "content_kind",
    "event_type",
    "subject_entity_ids",
    "mentioned_entity_ids",
    "publication_date",
    "temporal_confidence",
)


def apply_event_annotations(documents: list[dict], annotations: list[dict]) -> list[dict]:
    """Return reviewed shadow documents while preserving canonical ATR identities."""
    by_id = {str(row.get("daily_item_id") or ""): row for row in documents}
    output = []
    for annotation in annotations:
        identity = str(annotation.get("daily_item_id") or "")
        source = by_id.get(identity)
        if source is None:
            raise ValueError(f"unknown daily_item_id: {identity}")
        missing = [field for field in EVENT_FIELDS if field not in annotation]
        if missing:
            raise ValueError(f"{identity} missing event fields: {', '.join(missing)}")
        shadow = dict(source)
        for field in EVENT_FIELDS:
            shadow[field] = annotation[field]
        output.append(shadow)
    return output
