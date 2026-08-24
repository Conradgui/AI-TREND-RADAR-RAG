"""Shared temporal contract for runtime projections and ingestion metadata."""

from __future__ import annotations

from datetime import date
import re


ISO_DATE_PREFIX = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:$|T)")
LEGACY_PUBLICATION_PREFIX = "发布时间："
LEGACY_UPDATE_ONLY_SOURCE = re.compile(
    r"^(GitHub(?: Trending| Search:.*)?|Hugging Face|Gitee)$", re.IGNORECASE
)
LEGACY_PUBLICATION_SOURCE = re.compile(
    r"^(Hacker News|Product Hunt|ArXiv)$",
    re.IGNORECASE,
)


def normalize_explicit_date(value: object) -> str | None:
    """Accept only an explicit, valid ISO date/date-time within a sane range."""
    if not isinstance(value, str):
        return None
    match = ISO_DATE_PREFIX.match(value.strip())
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    if year < 2000 or year > 2100:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def build_temporal_metadata(candidate: dict, report_date: str) -> dict:
    """Separate publication, report, observation and ingestion semantics."""
    source_updated_at = normalize_explicit_date(
        candidate.get("sourceUpdatedAt") or candidate.get("source_updated_at")
    )
    structured = candidate.get("publishedAt") or candidate.get("published_at")
    if structured:
        publication_date = normalize_explicit_date(structured)
        if publication_date:
            return _published(report_date, publication_date, "upstream_declared", source_updated_at)
        return _fallback(report_date, "invalid_upstream_declared", source_updated_at)

    evidence = candidate.get("evidence")
    if isinstance(evidence, list):
        legacy_line = next(
            (
                item.strip()
                for item in evidence
                if isinstance(item, str)
                and item.strip().startswith(LEGACY_PUBLICATION_PREFIX)
            ),
            "",
        )
        if legacy_line:
            legacy_date = normalize_explicit_date(
                legacy_line[len(LEGACY_PUBLICATION_PREFIX):].strip()
            )
            if legacy_date:
                source = str(candidate.get("source") or "").strip()
                if LEGACY_PUBLICATION_SOURCE.fullmatch(source):
                    return _published(
                        report_date,
                        legacy_date,
                        "legacy_adapter_contract",
                        source_updated_at,
                    )
                return _fallback(
                    report_date,
                    "unverified_legacy_date",
                    source_updated_at
                    or (legacy_date if LEGACY_UPDATE_ONLY_SOURCE.fullmatch(source) else None),
                )
            return _fallback(report_date, "invalid_legacy_evidence", source_updated_at)
    return _fallback(report_date, None, source_updated_at)


def _published(report_date: str, publication_date: str, source: str, source_updated_at: str | None) -> dict:
    return {
        "report_date": report_date,
        "publication_date": publication_date,
        "publication_date_source": source,
        "source_updated_at": source_updated_at,
        "observed_at": report_date,
        "ingested_at": None,
        "effective_date": publication_date,
        "effective_date_basis": "publication_date",
        "temporal_diagnostic": None,
    }


def _fallback(report_date: str, diagnostic: str | None, source_updated_at: str | None) -> dict:
    return {
        "report_date": report_date,
        "publication_date": None,
        "publication_date_source": "unknown",
        "source_updated_at": source_updated_at,
        "observed_at": report_date,
        "ingested_at": None,
        "effective_date": report_date,
        "effective_date_basis": "report_date_fallback",
        "temporal_diagnostic": diagnostic,
    }


def audit_temporal_documents(documents: list[dict]) -> dict:
    """Return the small activation gate for provable date-role invariants."""
    legacy_promoted = sum(
        1 for item in documents
        if item.get("publication_date_source") == "legacy_evidence"
        or (
            item.get("effective_date_basis") == "publication_date"
            and not item.get("publication_date")
        )
    )
    update_only_promoted = sum(
        1 for item in documents
        if LEGACY_UPDATE_ONLY_SOURCE.fullmatch(str(item.get("source") or "").strip())
        and item.get("publication_date")
    )
    unauthorized_legacy_source = sum(
        1 for item in documents
        if item.get("publication_date_source") == "legacy_adapter_contract"
        and not LEGACY_PUBLICATION_SOURCE.fullmatch(str(item.get("source") or "").strip())
    )
    invalid_publication_date = sum(
        1 for item in documents
        if item.get("publication_date")
        and normalize_explicit_date(item.get("publication_date")) is None
    )
    invalid_source_updated_at = sum(
        1 for item in documents
        if item.get("source_updated_at")
        and normalize_explicit_date(item.get("source_updated_at")) is None
    )
    invalid_report_date = sum(
        1 for item in documents
        if normalize_explicit_date(item.get("report_date")) is None
    )
    inconsistent_temporal_roles = sum(
        1 for item in documents if not _has_consistent_temporal_roles(item)
    )
    passed = all(count == 0 for count in (
        legacy_promoted,
        update_only_promoted,
        unauthorized_legacy_source,
        invalid_publication_date,
        invalid_source_updated_at,
        invalid_report_date,
        inconsistent_temporal_roles,
    ))
    return {
        "document_count": len(documents),
        "legacy_promoted_to_publication": legacy_promoted,
        "update_only_promoted_to_publication": update_only_promoted,
        "unauthorized_legacy_publication_source": unauthorized_legacy_source,
        "invalid_publication_date": invalid_publication_date,
        "invalid_source_updated_at": invalid_source_updated_at,
        "invalid_report_date": invalid_report_date,
        "inconsistent_temporal_roles": inconsistent_temporal_roles,
        "passed": passed,
    }


def _has_consistent_temporal_roles(item: dict) -> bool:
    publication_date = item.get("publication_date")
    publication_source = str(item.get("publication_date_source") or "unknown")
    basis = str(item.get("effective_date_basis") or "")
    effective_date = item.get("effective_date")
    if publication_date:
        return (
            publication_source in {"upstream_declared", "legacy_adapter_contract"}
            and basis == "publication_date"
            and effective_date == publication_date
        )
    report_date = item.get("report_date")
    return (
        publication_source == "unknown"
        and basis == "report_date_fallback"
        and effective_date == report_date
    )
