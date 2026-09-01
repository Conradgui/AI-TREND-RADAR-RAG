"""Canonical entity identities shared by ingestion and retrieval.

The public ID is deliberately small and stable. Display aliases may change;
the ID stored in index metadata must not.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


_REGISTRY_PATH = Path(__file__).with_name("entity_registry.json")


def _load_registry() -> tuple[dict[str, str], dict[str, tuple[dict, ...]]]:
    """Load versioned entity data; keep a tiny fallback for damaged deployments."""
    fallback_aliases = {
        "openai": "openai", "open ai": "openai", "chatgpt": "chatgpt",
        "codex": "codex", "anthropic": "anthropic", "claude": "claude",
        "claude code": "claude-code", "apple": "apple", "苹果": "apple",
        "google": "google", "谷歌": "google", "gemini": "gemini",
        "google deepmind": "google-deepmind", "deepmind": "google-deepmind",
        "grok": "grok", "grok bot": "grok-bot", "xai": "xai",
        "x ai": "xai", "x": "x", "twitter": "x", "spacex": "spacex",
    }
    fallback_relations = {
        "claude": ({"entity_id": "anthropic", "relation": "developed_by", "weight": 0.55},),
        "claude-code": ({"entity_id": "anthropic", "relation": "product_of", "weight": 0.55},),
        "chatgpt": ({"entity_id": "openai", "relation": "product_of", "weight": 0.55},),
        "codex": ({"entity_id": "openai", "relation": "product_of", "weight": 0.55},),
    }
    try:
        payload = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
        aliases = {}
        for entity in payload.get("entities", []):
            entity_id = str(entity.get("entity_id", "")).strip()
            for alias in entity.get("aliases", []):
                normalized = re.sub(
                    r"[^a-z0-9\u4e00-\u9fff]+",
                    " ",
                    str(alias or "").casefold(),
                ).strip()
                if normalized and entity_id:
                    aliases[normalized] = entity_id
        relations = {}
        for item in payload.get("relations", []):
            if item.get("status") != "verified":
                continue
            source = str(item.get("from", "")).strip()
            target = str(item.get("to", "")).strip()
            if not source or not target:
                continue
            relations.setdefault(source, []).append({
                "entity_id": target,
                "relation": item.get("relation", "related_to"),
                "weight": float(item.get("weight", 0.25)),
            })
        return aliases or fallback_aliases, {
            source: tuple(values) for source, values in relations.items()
        } or fallback_relations
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return fallback_aliases, fallback_relations


_ENTITY_ALIASES, ENTITY_RELATIONS = _load_registry()


def normalize_entity_name(value: object) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(value or "").casefold()).strip()


def canonical_entity_id(value: object) -> str:
    """Return a stable entity ID without fuzzy guessing."""
    normalized = normalize_entity_name(value)
    if not normalized:
        return ""
    return _ENTITY_ALIASES.get(normalized, normalized.replace(" ", "-"))


def canonical_entity_ids(values: object) -> list[str]:
    """Normalize a scalar or collection while preserving first-seen order."""
    if isinstance(values, str):
        raw_values = re.split(r"[\n,;]+", values)
    elif isinstance(values, (list, tuple, set)):
        raw_values = list(values)
    elif values in (None, ""):
        raw_values = []
    else:
        raw_values = [values]
    result = []
    seen = set()
    for value in raw_values:
        entity_id = canonical_entity_id(value)
        if entity_id and entity_id not in seen:
            seen.add(entity_id)
            result.append(entity_id)
    return result


def query_entity_ids(text: str) -> list[str]:
    """Match registered names, preferring longer names without guessing relations."""
    # Lower-case hyphenated tokens are commonly repository/package slugs
    # (for example ``claude-mem``).  Treating the ``claude`` component as the
    # Claude product creates a false subject filter and can remove the other
    # side of an explicit project comparison.
    without_repository_slugs = re.sub(
        r"(?<![A-Za-z0-9])[a-z][a-z0-9]*-[a-z0-9-]*[a-z0-9](?![A-Za-z0-9])",
        " ",
        str(text or ""),
    )
    normalized = normalize_entity_name(without_repository_slugs)
    matches = []
    occupied = []
    for alias, entity_id in sorted(_ENTITY_ALIASES.items(), key=lambda pair: -len(pair[0])):
        # ASCII boundaries allow natural Chinese queries such as 最近Gemini有什么动态.
        for match in re.finditer(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", normalized):
            start, end = match.span()
            if any(start < other_end and end > other_start for other_start, other_end in occupied):
                continue
            occupied.append((start, end))
            matches.append((start, entity_id))
    return list(dict.fromkeys(entity_id for _, entity_id in sorted(matches)))


def related_entity_expansions(values: object, *, memory=None) -> list[dict]:
    """Return curated plus explicitly verified learned relations.

    ``memory`` is optional so deterministic callers and tests never depend on
    user runtime state. Server wiring may inject the persistent memory later;
    candidate and revoked records are filtered by that module's interface.
    """
    expansions = []
    seen = set()
    for entity_id in canonical_entity_ids(values):
        for relation in ENTITY_RELATIONS.get(entity_id, ()):
            key = (entity_id, relation["entity_id"], relation["relation"])
            if key in seen:
                continue
            seen.add(key)
            expansions.append({"from_entity_id": entity_id, **relation})
    if memory is not None:
        for relation in memory.verified_expansions(values):
            key = (
                relation["from_entity_id"],
                relation["entity_id"],
                relation["relation"],
            )
            if key in seen:
                continue
            seen.add(key)
            expansions.append(relation)
    return expansions


def legacy_entity_ids(values: object) -> list[str]:
    """Read old event-extraction records without changing the new query model."""
    aliases = {
        "claude": "anthropic",
        "claude-code": "anthropic",
        "chatgpt": "openai",
        # Legacy event records historically stored Gemini under its parent
        # company. Keep that read/write compatibility outside the new query
        # identity model, where Gemini remains a distinct product.
        "gemini": "google",
        "google-deepmind": "google",
    }
    result = []
    for value in canonical_entity_ids(values):
        result.append(aliases.get(value, value))
    return list(dict.fromkeys(result))


def legacy_infer_entity_ids(explicit: object = None, *texts: object) -> list[str]:
    return legacy_entity_ids(infer_entity_ids(explicit, *texts))


def infer_entity_ids(explicit: object = None, *texts: object) -> list[str]:
    """Combine explicit IDs with conservative mentions from trusted fields."""
    result = canonical_entity_ids(explicit)
    seen = set(result)
    # Reuse the boundary-aware matcher so mixed Chinese/Latin text such as
    # ``参观xAI数据中心`` and ``开源Grok Build`` is not lost merely because
    # the publisher did not insert spaces around the entity name.
    for entity_id in query_entity_ids(" ".join(str(text or "") for text in texts)):
        if entity_id not in seen:
            seen.add(entity_id)
            result.append(entity_id)
    return result
