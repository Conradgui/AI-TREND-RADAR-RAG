"""Bounded deep-fetch policy for external citations."""

from __future__ import annotations

from copy import deepcopy


AUTHORITATIVE_QUALITIES = {"official", "academic", "developer"}
WEAK_QUALITIES = {"generic", "social", "trusted_media"}
DEFAULT_MAX_DEEP_FETCH_URLS = 2


def choose_deep_fetch_targets(citations: list[dict], max_urls: int = DEFAULT_MAX_DEEP_FETCH_URLS) -> list[dict]:
    """Choose a bounded set of external citations for URL deep fetch."""
    candidates = [
        (index, citation)
        for index, citation in enumerate(citations)
        if citation.get("evidence_type") == "external" and citation.get("url")
    ]
    ranked = sorted(candidates, key=lambda item: (_priority(item[1]), item[0]))
    return [
        {
            "index": index,
            "url": citation["url"],
            "source_quality": citation.get("source_quality", ""),
            "needs_deep_fetch": bool(citation.get("needs_deep_fetch")),
        }
        for index, citation in ranked[:max_urls]
    ]


def apply_deep_fetch_policy(
    citations: list[dict],
    fetcher,
    max_urls: int = DEFAULT_MAX_DEEP_FETCH_URLS,
    enabled: bool = True,
) -> tuple[list[dict], dict]:
    """Attach deep-fetch records to selected citations and return a trace."""
    if not enabled:
        return deepcopy(citations), {
            "attempted": False,
            "reason": "disabled",
            "selected_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "targets": [],
        }

    deepened = deepcopy(citations)
    targets = choose_deep_fetch_targets(deepened, max_urls=max_urls)
    success_count = 0
    failure_count = 0

    for target in targets:
        result = fetcher(target["url"])
        deepened[target["index"]]["deep_fetch"] = result
        if result.get("ok"):
            success_count += 1
        else:
            failure_count += 1

    return deepened, {
        "attempted": bool(targets),
        "reason": "completed" if targets else "no_external_url_targets",
        "selected_count": len(targets),
        "success_count": success_count,
        "failure_count": failure_count,
        "max_urls": max_urls,
        "targets": [
            {
                "url": target["url"],
                "source_quality": target["source_quality"],
                "needs_deep_fetch": target["needs_deep_fetch"],
            }
            for target in targets
        ],
    }


def _priority(citation: dict) -> int:
    source_quality = citation.get("source_quality", "")
    if source_quality in AUTHORITATIVE_QUALITIES:
        return 0
    if citation.get("needs_deep_fetch") or source_quality in WEAK_QUALITIES:
        return 1
    return 2
