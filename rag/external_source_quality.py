"""External source quality classification and excerpt policy."""

from __future__ import annotations

from urllib.parse import urlparse


OFFICIAL_DOMAINS_BY_ENTITY = {
    "google": ["google.com", "cloud.google.com", "research.google", "deepmind.google"],
    "anthropic": ["anthropic.com", "docs.anthropic.com"],
    "openai": ["openai.com", "platform.openai.com"],
    "github": ["github.com"],
}

SOCIAL_DOMAINS = [
    "linkedin.com",
    "www.linkedin.com",
    "x.com",
    "twitter.com",
    "reddit.com",
    "www.reddit.com",
    "medium.com",
]

ACADEMIC_DOMAINS = [
    "arxiv.org",
    "aclanthology.org",
    "openreview.net",
    "semanticscholar.org",
]

DEVELOPER_DOMAINS = [
    "github.com",
    "docs.github.com",
    "huggingface.co",
    "aws.amazon.com",
    "docs.aws.amazon.com",
    "ibm.com",
    "microsoft.com",
    "learn.microsoft.com",
    "nvidia.com",
    "docs.nvidia.com",
    "pinecone.io",
    "docs.pinecone.io",
    "elastic.co",
    "docs.databricks.com",
    "langchain.com",
    "python.langchain.com",
]

TRUSTED_MEDIA_DOMAINS = [
    "theverge.com",
    "techcrunch.com",
    "wired.com",
]

EXCERPT_LIMITS = {
    "official": 1400,
    "academic": 1600,
    "developer": 1200,
    "trusted_media": 900,
    "generic": 800,
    "social": 500,
}


def classify_source_quality(url: str, task_type: str = "", entities: list[str] | None = None) -> dict:
    """Classify external source quality from URL and task context."""
    host = _host(url)
    entity_names = [entity.lower() for entity in (entities or [])]

    if _matches_entity_official_domain(host, entity_names):
        return _quality("official", 0.95, False, ["primary official domain for requested entity"])
    if host in ACADEMIC_DOMAINS or any(host.endswith("." + domain) for domain in ACADEMIC_DOMAINS):
        return _quality("academic", 0.9, False, ["academic or paper source"])
    if host in DEVELOPER_DOMAINS or any(host.endswith("." + domain) for domain in DEVELOPER_DOMAINS):
        return _quality("developer", 0.82, False, ["developer platform or documentation source"])
    if host in SOCIAL_DOMAINS or any(host.endswith("." + domain) for domain in SOCIAL_DOMAINS):
        notes = ["social or repost source"]
        if task_type == "official_source_lookup":
            notes.append("needs primary official source replacement")
        return _quality("social", 0.35, True, notes)
    if host in TRUSTED_MEDIA_DOMAINS or any(host.endswith("." + domain) for domain in TRUSTED_MEDIA_DOMAINS):
        return _quality("trusted_media", 0.7, True, ["secondary reporting source"])
    return _quality("generic", 0.55, True, ["generic web source; verify before strong claims"])


def apply_excerpt_policy(text: str, quality: dict) -> str:
    """Apply source-aware excerpt length policy."""
    source_quality = quality.get("source_quality", "generic")
    limit = EXCERPT_LIMITS.get(source_quality, EXCERPT_LIMITS["generic"])
    return str(text or "").strip()[:limit]


def official_lookup_domain_policy(entities: list[str]) -> dict:
    """Return include/exclude domains for official-source lookup tasks."""
    include_domains = []
    for entity in entities:
        include_domains.extend(OFFICIAL_DOMAINS_BY_ENTITY.get(entity.lower(), []))

    return {
        "include_domains": _unique(include_domains),
        "exclude_domains": SOCIAL_DOMAINS,
    }


def _quality(source_quality: str, score: float, needs_deep_fetch: bool, notes: list[str]) -> dict:
    return {
        "source_quality": source_quality,
        "quality_score": score,
        "needs_deep_fetch": needs_deep_fetch,
        "quality_notes": notes,
    }


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _matches_entity_official_domain(host: str, entities: list[str]) -> bool:
    for entity in entities:
        for domain in OFFICIAL_DOMAINS_BY_ENTITY.get(entity, []):
            if host == domain or host.endswith("." + domain):
                return True
    return False


def _unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
