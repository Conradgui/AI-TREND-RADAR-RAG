"""Bounded deep-fetch policy for external citations."""

from __future__ import annotations

import asyncio
from copy import deepcopy


AUTHORITATIVE_QUALITIES = {"official", "academic", "developer"}
WEAK_QUALITIES = {"generic", "social", "trusted_media"}
DEFAULT_MAX_DEEP_FETCH_URLS = 2
DEFAULT_MAX_CONCURRENT_DEEP_FETCHES = 3  # A-6 修复：最大并发数


def choose_deep_fetch_targets(citations: list[dict], max_urls: int = DEFAULT_MAX_DEEP_FETCH_URLS) -> list[dict]:
    """Choose a bounded set of external citations for URL deep fetch."""
    candidates = [
        (index, citation)
        for index, citation in enumerate(citations)
        if (
            citation.get("evidence_type") == "external"
            and citation.get("url")
            and _requires_deep_fetch(citation)
        )
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


async def _fetch_single_url(fetcher, target: dict) -> tuple[int, dict]:
    """A-6 修复：单个URL抓取（异步）"""
    try:
        if asyncio.iscoroutinefunction(fetcher):
            result = await fetcher(target["url"])
        else:
            result = fetcher(target["url"])
        return target["index"], result
    except Exception as e:
        return target["index"], {"ok": False, "error": str(e)}


async def apply_deep_fetch_policy_async(
    citations: list[dict],
    fetcher,
    max_urls: int = DEFAULT_MAX_DEEP_FETCH_URLS,
    max_concurrent: int = DEFAULT_MAX_CONCURRENT_DEEP_FETCHES,
    enabled: bool = True,
) -> tuple[list[dict], dict]:
    """A-6 修复：并发执行deep fetch"""
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

    if not targets:
        return deepened, {
            "attempted": False,
            "reason": "no_external_url_targets",
            "selected_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "targets": [],
        }

    # A-6 修复：并发抓取，限制并发数
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_with_semaphore(target):
        async with semaphore:
            return await _fetch_single_url(fetcher, target)

    # 并发执行所有抓取任务
    results = await asyncio.gather(
        *[fetch_with_semaphore(target) for target in targets],
        return_exceptions=True
    )

    success_count = 0
    failure_count = 0

    for result in results:
        if isinstance(result, Exception):
            failure_count += 1
            continue

        index, fetch_result = result
        deepened[index]["deep_fetch"] = fetch_result
        if fetch_result.get("ok"):
            success_count += 1
        else:
            failure_count += 1

    return deepened, {
        "attempted": True,
        "reason": "completed",
        "selected_count": len(targets),
        "success_count": success_count,
        "failure_count": failure_count,
        "max_urls": max_urls,
        "max_concurrent": max_concurrent,
        "targets": [
            {
                "url": target["url"],
                "source_quality": target["source_quality"],
                "needs_deep_fetch": target["needs_deep_fetch"],
            }
            for target in targets
        ],
    }


def apply_deep_fetch_policy(
    citations: list[dict],
    fetcher,
    max_urls: int = DEFAULT_MAX_DEEP_FETCH_URLS,
    enabled: bool = True,
) -> tuple[list[dict], dict]:
    """同步版本的deep fetch策略（保持向后兼容）"""
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


def _requires_deep_fetch(citation: dict) -> bool:
    """Fetch only when the search snippet cannot support the requested claim."""
    if citation.get("needs_deep_fetch") or citation.get("evidence_demand"):
        return True
    excerpt = str(citation.get("excerpt") or "").strip()
    source_role = citation.get("source_role")
    provenance_verified = citation.get("provenance_status") in {
        "verified",
        "confirmed_same_origin",
        "likely_same_origin",
        "independent",
    } or source_role == "primary_claim_source"
    date_verified = citation.get("date_status") in {"verified", "not_required"}
    return len(excerpt) < 160 or not provenance_verified or not date_verified
