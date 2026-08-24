"""Canonical entity identities shared by ingestion and retrieval.

The public ID is deliberately small and stable. Display aliases may change;
the ID stored in index metadata must not.
"""

from __future__ import annotations

import re


_ENTITY_ALIASES = {
    "openai": "openai",
    "open ai": "openai",
    "chatgpt": "openai",
    "codex": "codex",
    "gpt live": "gpt-live",
    "anthropic": "anthropic",
    "claude": "anthropic",
    "claude code": "claude-code",
    "apple": "apple",
    "苹果": "apple",
    "google": "google",
    "gemini": "google",
    "谷歌": "google",
    "google deepmind": "google-deepmind",
    "deepmind": "google-deepmind",
    "google cloud": "google-cloud",
    "minimax": "minimax",
    "minimaxai": "minimax",
    "minimax h3": "minimax-h3",
    "comfyui": "comfyui",
}


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


def infer_entity_ids(explicit: object = None, *texts: object) -> list[str]:
    """Combine explicit IDs with conservative mentions from trusted fields."""
    result = canonical_entity_ids(explicit)
    seen = set(result)
    haystack = f" {normalize_entity_name(' '.join(str(text or '') for text in texts))} "
    for alias, entity_id in _ENTITY_ALIASES.items():
        normalized_alias = normalize_entity_name(alias)
        if normalized_alias and f" {normalized_alias} " in haystack and entity_id not in seen:
            seen.add(entity_id)
            result.append(entity_id)
    return result
