"""Claim-aware admission policy for external search candidates."""

from __future__ import annotations

import ipaddress
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_TRACKING_QUERY_PREFIXES = ("utm_",)
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "ref", "source"}
_PRIMARY_VENDOR_CLAIMS = {
    "product_release",
    "api_change",
    "pricing",
    "service_status",
    "capability_evaluation",
}
_INDEPENDENT_REQUIRED_CLAIMS = {"market_evaluation", "market_leadership", "broad_adoption"}


def infer_claim_type(plan) -> str:
    """Map known query intents to an extensible source-responsibility policy."""
    intent = str(getattr(plan, "intent", ""))
    task_mode = str(getattr(plan, "task_mode", ""))
    question = str(getattr(plan, "original_question", "")).casefold()
    if any(term in question for term in ("融资", "营收", "亏损", "ipo", "估值")):
        return "finance"
    if any(term in question for term in ("领先", "市场份额", "广泛采用", "用户评价")):
        return "market_evaluation"
    if intent in {"product_update", "recent_trend", "important_news", "web_search_request"}:
        return "product_release"
    if intent == "learning_map" or task_mode == "timeline":
        return "research"
    if task_mode in {"source_check", "compare"} or intent in {"evidence_sufficiency", "technical_comparison"}:
        return "capability_evaluation"
    return "unclassified"


def infer_evidence_demand(plan) -> str:
    """Identify requests where a search snippet is discovery, not final proof."""
    question = str(getattr(plan, "original_question", "")).casefold()
    time_window = getattr(plan, "time_window", {}) or {}
    if time_window.get("label") == "last_7_days":
        return "verify_recent_primary"
    if any(
        term in question
        for term in (
            "原文",
            "全文",
            "核实",
            "核验",
            "验证",
            "查证",
            "真实性",
            "可靠性",
            "方法限制",
            "准确数字",
        )
    ):
        return "verify_primary_source"
    claim_type = infer_claim_type(plan)
    if claim_type in {"finance", "market_evaluation"}:
        return "verify_high_risk_claim"
    if claim_type == "capability_evaluation" and any(
        term in question
        for term in ("领先", "更好", "效果", "性能", "benchmark", "准确率", "成功率")
    ):
        return "verify_high_risk_claim"
    return ""


def review_external_candidates(
    candidates: list[dict],
    *,
    claim_type: str = "unclassified",
    recent_required: bool = False,
    recent_window_days: int = 10,
    today: str | None = None,
    evidence_demand: str = "",
) -> dict:
    """Split candidates into final evidence, search references, and exclusions."""
    reference_date = _parse_date(today) or date.today()
    admitted: list[dict] = []
    search_references: list[dict] = []
    excluded: list[dict] = []
    seen_urls: set[str] = set()
    duplicate_count = 0

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        record = dict(candidate)
        canonical_url = canonicalize_url(str(record.get("canonical_url") or record.get("url") or ""))
        record["canonical_url"] = canonical_url
        if canonical_url and canonical_url in seen_urls:
            duplicate_count += 1
            continue
        if canonical_url:
            seen_urls.add(canonical_url)

        if not _is_public_http_url(canonical_url):
            record.update({"admission_action": "reject", "exclusion_reason": "unsafe_url"})
            excluded.append(_audit_record(record))
            continue
        if record.get("supports_claim") is False:
            record.update({"admission_action": "reject", "exclusion_reason": "content_does_not_support_claim"})
            excluded.append(_audit_record(record))
            continue

        record["document_role"] = (
            "navigation_page" if is_navigation_or_listing_page(record) else "content_page"
        )
        record.update(_normalize_dates(record, reference_date))
        record.update(_normalize_provenance(record))
        record["claim_type"] = claim_type or "unclassified"
        if evidence_demand:
            record["evidence_demand"] = evidence_demand
        record["source_role"] = _source_role(record, record["claim_type"])
        record["admission_action"] = (
            "admit"
            if record["source_role"] in {"primary_claim_source", "independent_corroboration"}
            else "downgrade"
        )

        if record["source_role"] == "supporting_context":
            record["not_admitted_reason"] = (
                "navigation_page_only"
                if record["document_role"] == "navigation_page"
                else "supporting_context_only"
            )
            search_references.append(record)
            continue

        if recent_required:
            effective = _parse_date(record.get("effective_event_date"))
            if record["date_status"] != "verified" or effective is None:
                record["admission_action"] = "downgrade"
                record["not_admitted_reason"] = f"date_{record['date_status']}"
                search_references.append(record)
                continue
            if (reference_date - effective).days > recent_window_days:
                record["admission_action"] = "background"
                record["not_admitted_reason"] = "outside_recent_window"
                search_references.append(record)
                continue

        admitted.append(record)

    return {
        "admitted": admitted,
        "search_references": search_references,
        "excluded": excluded,
        "summary": {
            "candidate_count": len(candidates),
            "admitted_count": len(admitted),
            "search_reference_count": len(search_references),
            "excluded_count": len(excluded),
            "duplicate_count": duplicate_count,
            "claim_type": claim_type or "unclassified",
        },
    }


def _source_role(record: dict, claim_type: str) -> str:
    if record.get("document_role") == "navigation_page":
        return "supporting_context"
    quality = str(record.get("source_quality", "generic"))
    if claim_type in _INDEPENDENT_REQUIRED_CLAIMS and quality == "official":
        return "supporting_context"
    if quality == "official" and claim_type in _PRIMARY_VENDOR_CLAIMS:
        return "primary_claim_source"
    if quality == "academic" and claim_type in {"research", "capability_evaluation", "unclassified"}:
        return "primary_claim_source"
    if quality in {"primary", "high-signal", "academic"}:
        return "independent_corroboration"
    return "supporting_context"


def _normalize_dates(record: dict, reference_date: date) -> dict:
    if record.get("document_role") == "navigation_page":
        return {
            "effective_event_date": "",
            "date_status": "missing",
            "date_basis": "navigation_page_not_event",
        }
    date_fields = ("event_date", "date_published", "published_at")
    parsed: list[tuple[str, date]] = []
    invalid_present = False
    for field in date_fields:
        raw = record.get(field)
        if not raw:
            continue
        value = _parse_date(raw)
        if value is None or value > reference_date:
            invalid_present = True
            continue
        parsed.append((field, value))

    unique_dates = {value for _, value in parsed}
    if invalid_present and not parsed:
        return {"effective_event_date": "", "date_status": "invalid", "date_basis": "invalid_source_date"}
    if not parsed:
        return {"effective_event_date": "", "date_status": "missing", "date_basis": "none"}
    preferred_field, preferred_date = parsed[0]
    if len(unique_dates) > 1:
        return {
            "effective_event_date": preferred_date.isoformat(),
            "date_status": "conflicting",
            "date_basis": "+".join(field for field, _ in parsed),
        }
    return {
        "effective_event_date": preferred_date.isoformat(),
        "date_status": "verified",
        "date_basis": preferred_field,
    }


def is_navigation_or_listing_page(record: dict) -> bool:
    """Detect hub pages that can discover releases but cannot prove one release."""
    try:
        path = urlsplit(str(record.get("canonical_url") or record.get("url") or "")).path
    except ValueError:
        path = ""
    normalized_path = path.rstrip("/").casefold()
    listing_paths = {
        "",
        "/news",
        "/newsroom",
        "/blog",
        "/releases",
        "/changelog",
        "/news/product-releases",
        "/news/company-announcements",
    }
    if normalized_path in listing_paths:
        return True

    host = str(urlsplit(str(record.get("canonical_url") or record.get("url") or "")).hostname or "").casefold()
    marketplace_paths = (
        "/store/apps/",
        "/app/",
        "/apps/",
        "/product/",
        "/products/",
    )
    marketplace_hosts = {
        "play.google.com",
        "apps.apple.com",
        "www.producthunt.com",
        "producthunt.com",
    }
    if host in marketplace_hosts and any(marker in normalized_path for marker in marketplace_paths):
        return True

    title = str(record.get("title") or "").casefold()
    return any(
        marker in title
        for marker in (
            "newsroom | recent news",
            "newsroom | product",
            "release notes | latest",
        )
    )


def _normalize_provenance(record: dict) -> dict:
    status = str(record.get("provenance_status") or "unknown")
    allowed = {"confirmed_same_origin", "likely_same_origin", "independent", "unknown"}
    if status not in allowed:
        status = "unknown"
    return {
        "provenance_status": status,
        "provenance_basis": str(record.get("provenance_basis") or "not_available"),
    }


def canonicalize_url(raw_url: str) -> str:
    try:
        parts = urlsplit(raw_url.strip())
    except ValueError:
        return raw_url.strip()
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in _TRACKING_QUERY_KEYS
        and not key.casefold().startswith(_TRACKING_QUERY_PREFIXES)
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, urlencode(filtered_query), ""))


def _is_public_http_url(raw_url: str) -> bool:
    try:
        parts = urlsplit(raw_url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return False
        hostname = parts.hostname.casefold()
        if hostname == "localhost" or hostname.endswith(".localhost"):
            return False
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            return True
        return not (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        )
    except ValueError:
        return False


def _parse_date(raw) -> date | None:
    if not raw:
        return None
    text = str(raw).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _audit_record(record: dict) -> dict:
    return {
        key: record.get(key)
        for key in ("title", "source", "canonical_url", "admission_action", "exclusion_reason")
        if record.get(key) not in (None, "")
    }
