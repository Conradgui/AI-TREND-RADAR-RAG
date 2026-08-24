"""CLI entry point: python -m rag.ingest — ingests digest data into Neo4j + ChromaDB."""

from __future__ import annotations

import asyncio
import argparse
import hashlib
import html
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from rag.config import DIGESTS_DIR, CHROMA_DIR, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from rag.entity_identity import infer_entity_ids
from rag.temporal_semantics import build_temporal_metadata

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SEARCH_INDEX_PATH = Path(DIGESTS_DIR) / "search-index.json"


def _find_digest_dates() -> list[str]:
    """Return sorted list of YYYY-MM-DD directory names under digests/."""
    digests = Path(DIGESTS_DIR)
    if not digests.exists():
        return []
    return sorted(d.name for d in digests.iterdir() if d.is_dir() and DATE_PATTERN.match(d.name))


def _load_topic_pool(date_dir: Path) -> dict | None:
    """Load and parse topic-pool.json from a digest date directory."""
    pool_path = date_dir / "topic-pool.json"
    if not pool_path.exists():
        return None
    try:
        return json.loads(pool_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [ingest] Failed to load topic-pool.json from {date_dir}: {e}")
        return None


def normalize_topic_pool(topic_pool: dict | None, date_str: str) -> dict:
    """Return topic pool in the canonical {'candidates': [...]} shape."""
    if not isinstance(topic_pool, dict):
        return {"candidates": []}

    raw_candidates = topic_pool.get("candidates")
    if not isinstance(raw_candidates, list):
        raw_candidates = topic_pool.get("topics")
    if not isinstance(raw_candidates, list):
        return {"candidates": []}

    candidates = []
    for item in raw_candidates:
        if not isinstance(item, dict):
            continue
        candidate = dict(item)
        candidate.setdefault("date", date_str)
        candidates.append(candidate)
    return {"candidates": candidates}


def _metadata_value(value):
    """Convert metadata values to Chroma-compatible scalar values."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return "\n".join(str(v) for v in value)
    return str(value)


def _identity_text(value: object) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(value or "").casefold()).strip()


def _identity_url(value: object) -> str:
    return str(value or "").strip().rstrip("/").casefold()


def load_search_documents(
    path: Path = SEARCH_INDEX_PATH,
    digests_dir: str = DIGESTS_DIR,
) -> list[dict]:
    """Rebuild the product-owned v2 projection from local atomic candidates."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    existing = payload.get("documents", []) if isinstance(payload, dict) else []
    documents = build_runtime_search_documents(digests_dir)
    if not documents:
        return [item for item in existing if isinstance(item, dict)]
    if documents:
        artifact = {
            "schema_version": 2,
            "id_scheme": "atr-v1",
            "generated": datetime.now(timezone.utc).isoformat(),
            "source_candidate_count": len(documents),
            "document_count": len(documents),
            "duplicate_record_count": 0,
            "diagnostics": [],
            "documents": documents,
        }
        try:
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(artifact, ensure_ascii=False) + "\n", encoding="utf-8")
            temporary.replace(path)
        except OSError:
            pass
    return documents


def attach_search_document_identity(
    topic_pool: dict,
    date_str: str,
    lookup: dict[tuple[str, str, str], dict],
) -> dict:
    """Attach ATR identity to candidates before graph projection."""
    candidates = []
    for raw in topic_pool.get("candidates", []):
        candidate = dict(raw)
        document = _search_document_for_candidate(candidate, date_str, lookup)
        candidate["daily_item_id"] = str(document.get("daily_item_id") or document.get("occurrence_id") or "")
        candidate["content_id"] = str(document.get("content_id") or "")
        candidate["local_url"] = str(document.get("local_url") or "")
        for field in (
            "report_date", "publication_date", "publication_date_source", "source_updated_at",
            "observed_at", "ingested_at", "effective_date", "effective_date_basis",
        ):
            candidate[field] = document.get(field)
        candidates.append(candidate)
    return {"candidates": candidates}


def _canonical_public_url(value: object) -> str:
    raw = str(value or "").strip().removeprefix("<![CDATA[").removesuffix("]]>").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return ""
        blocked = re.compile(r"(?:^|[_-])(?:api[_-]?key|access[_-]?token|auth|authorization|credential|password|secret|signature)(?:$|[_-])", re.I)
        query = []
        for key, item in parse_qsl(parts.query, keep_blank_values=True):
            lowered = key.lower()
            if blocked.search(key):
                return ""
            if lowered.startswith("utm_") or lowered in {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "ref_src"}:
                continue
            query.append((key, item))
        host = parts.hostname.lower()
        port = parts.port
        netloc = host if not port or (parts.scheme == "https" and port == 443) or (parts.scheme == "http" and port == 80) else f"{host}:{port}"
        path = parts.path or "/"
        return urlunsplit((parts.scheme, netloc, path, urlencode(query), parts.fragment))
    except (ValueError, UnicodeError):
        return ""


def _runtime_daily_item_id(date_str: str, candidate: dict) -> str:
    source = _identity_text(candidate.get("source")) or "unknown source"
    title = _identity_text(candidate.get("title") or candidate.get("topic"))
    upstream_id = next(
        (str(candidate.get(key) or "").strip() for key in ("id", "itemId", "item_id", "guid") if str(candidate.get(key) or "").strip()),
        "",
    )
    url = _canonical_public_url(candidate.get("url"))
    base = f"upstream:{source}:{upstream_id}" if upstream_id else (f"url:{url}|source:{source}" if url else f"fallback:{source}|title:{title}")
    identity = f"atr-v1|{date_str}|ai-topic-radar|{base}"
    suffix = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:6].upper()
    return f"ATR-{date_str.replace('-', '')}-{suffix}"


def build_runtime_search_documents(digests_dir: str = DIGESTS_DIR) -> list[dict]:
    """Project local daily candidates into the runtime's stable item contract."""
    documents: list[dict] = []
    seen: set[str] = set()
    root = Path(digests_dir)
    for date_str in _find_digest_dates_in(root):
        pool = normalize_topic_pool(_load_topic_pool(root / date_str), date_str)
        for candidate in pool.get("candidates", []):
            title = html.unescape(str(candidate.get("title") or candidate.get("topic") or "")).strip()
            if not title:
                continue
            daily_item_id = _runtime_daily_item_id(date_str, candidate)
            if daily_item_id in seen:
                continue
            seen.add(daily_item_id)
            url = _canonical_public_url(candidate.get("url"))
            content_key = url or f"{_identity_text(candidate.get('source'))}|{_identity_text(title)}"
            temporal = build_temporal_metadata(candidate, date_str)
            documents.append({
                "schema_version": 2,
                "id_scheme": "atr-v1",
                "content_id": hashlib.sha256(f"atr-v1|content|{content_key}".encode("utf-8")).hexdigest()[:32],
                "daily_item_id": daily_item_id,
                "occurrence_id": daily_item_id,
                "item_anchor": f"item-{daily_item_id}",
                "date": date_str,
                **{key: value for key, value in temporal.items() if key != "temporal_diagnostic"},
                "report_id": "ai-topic-radar",
                "report_type": "daily",
                "result_type": "item",
                "title": title,
                "normalized_title": _identity_text(unicodedata.normalize("NFKC", title)),
                "summary": html.unescape(str(candidate.get("summary") or "")),
                "source": str(candidate.get("source") or ""),
                "category": str(candidate.get("category") or ""),
                "score": candidate.get("score", 0) if isinstance(candidate.get("score", 0), (int, float)) else 0,
                "action": str(candidate.get("action") or ""),
                "display_fields": {
                    "recommended_topic": html.unescape(str(candidate.get("recommendedTopic") or candidate.get("recommended_topic") or "")),
                    "reason": html.unescape(str(candidate.get("reason") or "")),
                    "angle": html.unescape(str(candidate.get("angle") or "")),
                    "evidence": [html.unescape(str(item)) for item in candidate.get("evidence", [])] if isinstance(candidate.get("evidence"), list) else [],
                },
                "tags": candidate.get("tags", []) if isinstance(candidate.get("tags"), list) else [],
                "entities": candidate.get("entities", []) if isinstance(candidate.get("entities"), list) else [],
                "aliases": candidate.get("aliases", []) if isinstance(candidate.get("aliases"), list) else [],
                "external_url": url or None,
                "local_url": f"#{date_str}/ai-topic-radar/item/{daily_item_id}",
            })
    return documents


def build_search_document_lookup(documents: list[dict]) -> dict[tuple[str, str, str], dict]:
    """Index stable item identities by URL and by date/title/source fallback."""
    lookup: dict[tuple[str, str, str], dict] = {}
    for document in documents:
        date = str(document.get("date", ""))
        daily_item_id = str(document.get("daily_item_id") or document.get("occurrence_id") or "")
        if date and daily_item_id:
            lookup[(date, "id", daily_item_id)] = document
        url = _identity_url(document.get("external_url"))
        if date and url:
            lookup[(date, "url", url)] = document
        title = _identity_text(document.get("title"))
        source = _identity_text(document.get("source"))
        if date and title:
            lookup[(date, title, source)] = document
    return lookup


def _search_document_for_candidate(
    candidate: dict,
    date_str: str,
    lookup: dict[tuple[str, str, str], dict] | None,
) -> dict:
    if not lookup:
        return {}
    identity_key = (date_str, "id", _runtime_daily_item_id(date_str, candidate))
    if identity_key in lookup:
        return lookup[identity_key]
    url_key = (date_str, "url", _identity_url(candidate.get("url")))
    if url_key[2] and url_key in lookup:
        return lookup[url_key]
    return lookup.get(
        (
            date_str,
            _identity_text(candidate.get("title") or candidate.get("topic")),
            _identity_text(candidate.get("source")),
        ),
        {},
    )


def build_report_chunk_metadata(date_str: str, report_type: str, chunk_index: int) -> dict:
    """Build citation-ready metadata for a markdown report chunk."""
    citation_id = f"{date_str}/{report_type}/{chunk_index}"
    return {
        "content_type": "report_chunk",
        "date": date_str,
        "report_type": report_type,
        "source": report_type,
        "title": report_type,
        "chunk_index": chunk_index,
        "citation_id": citation_id,
    }


def _candidate_text(candidate: dict) -> str:
    parts = [
        candidate.get("title") or candidate.get("topic"),
        candidate.get("summary"),
        candidate.get("recommendedTopic"),
        candidate.get("reason"),
    ]
    evidence = candidate.get("evidence")
    if isinstance(evidence, list) and evidence:
        parts.append("证据: " + "；".join(str(item) for item in evidence))
    return "\n".join(str(part).strip() for part in parts if part)


def infer_source_family(source: str) -> str:
    """Normalize detailed source names into broad source families."""
    normalized = (source or "").strip().lower()
    if normalized.startswith("github"):
        return "GitHub"
    if normalized.startswith("product hunt"):
        return "Product Hunt"
    if "anthropic" in normalized or "claude" in normalized:
        return "Anthropic"
    return ""


def build_topic_candidate_chunks(
    topic_pool: dict,
    date_str: str,
    *,
    search_document_lookup: dict[tuple[str, str, str], dict] | None = None,
) -> tuple[list[str], list[dict], list[str]]:
    """Build citation-ready vector chunks from topic candidates."""
    chunks: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    for index, candidate in enumerate(topic_pool.get("candidates", [])):
        title = candidate.get("title") or candidate.get("topic")
        if not title:
            continue
        chunk = _candidate_text(candidate)
        if not chunk:
            continue
        search_document = _search_document_for_candidate(
            candidate,
            date_str,
            search_document_lookup,
        )
        occurrence_id = str(search_document.get("occurrence_id") or "")
        temporal = {
            key: search_document.get(key)
            for key in (
                "report_date", "publication_date", "publication_date_source", "source_updated_at",
                "observed_at", "ingested_at", "effective_date", "effective_date_basis",
            )
            if key in search_document
        } or {
            key: value
            for key, value in build_temporal_metadata(candidate, date_str).items()
            if key != "temporal_diagnostic"
        }
        citation_id = occurrence_id or f"{date_str}/topic-pool/{index}"
        metadata = {
            "content_type": "topic_candidate",
            "date": date_str,
            **temporal,
            "report_type": "topic-pool",
            "source": candidate.get("source", ""),
            "source_family": infer_source_family(candidate.get("source", "")),
            "title": title,
            "url": candidate.get("url", ""),
            "score": candidate.get("score", 0),
            "action": candidate.get("action", ""),
            "category": candidate.get("category", ""),
            "citation_id": citation_id,
            "content_id": search_document.get("content_id", ""),
            "occurrence_id": occurrence_id,
            "local_url": search_document.get("local_url", ""),
            "evidence": _metadata_value(candidate.get("evidence", "")),
            "tags": ", ".join(str(tag) for tag in candidate.get("tags", [])),
            "entity_ids": infer_entity_ids(
                search_document.get("entity_ids")
                or search_document.get("entities")
                or candidate.get("entity_ids")
                or candidate.get("entities"),
                title,
                candidate.get("source"),
            ),
        }
        chunks.append(chunk)
        metadatas.append({key: _metadata_value(value) for key, value in metadata.items()})
        ids.append(citation_id)

    return chunks, metadatas, ids


def ingest_vector_chunks_for_date(
    vector_store,
    date_str: str,
    topic_pool: dict,
    reports: dict[str, str],
    *,
    search_document_lookup: dict[tuple[str, str, str], dict] | None = None,
) -> int:
    """Replace one day's vectors with atomic daily items only.

    Rendered Markdown is a browse projection. Indexing it again duplicates the
    same news and can mix multiple items inside one retrieval chunk.
    """
    vector_store.delete_by_date(date_str)

    topic_chunks, topic_metadatas, topic_ids = build_topic_candidate_chunks(
        topic_pool,
        date_str,
        search_document_lookup=search_document_lookup,
    )
    if topic_chunks:
        vector_store.add_chunks(topic_chunks, topic_metadatas, topic_ids)
    return len(topic_chunks)


def ingest_all_vector_chunks(vector_store, digests_dir: str = DIGESTS_DIR) -> int:
    """Ingest all local digest dates into ChromaDB without requiring Neo4j."""
    total_chunks = 0
    dates = _find_digest_dates_in(Path(digests_dir))
    search_document_lookup = build_search_document_lookup(
        load_search_documents(
            path=Path(digests_dir) / "search-index.json",
            digests_dir=digests_dir,
        )
    )

    for date_str in dates:
        date_dir = Path(digests_dir) / date_str
        topic_pool = normalize_topic_pool(_load_topic_pool(date_dir), date_str)
        reports = _load_reports(date_dir)
        if not topic_pool.get("candidates") and not reports:
            continue
        chunk_count = ingest_vector_chunks_for_date(
            vector_store,
            date_str,
            topic_pool,
            reports,
            search_document_lookup=search_document_lookup,
        )
        total_chunks += chunk_count
        print(f"[ingest:vector] {date_str}: ingested {chunk_count} chunks")

    print(f"[ingest:vector] ChromaDB total: {vector_store.count()} chunks")
    return total_chunks


def migrate_atomic_vector_chunks(
    source_store,
    target_store,
    documents: list[dict],
    *,
    report_sink: dict | None = None,
) -> int:
    """Reuse old candidate embeddings and embed only genuinely new ATR items."""
    lookup = build_search_document_lookup(documents)
    exported = source_store.export_records()
    exported_documents = exported.get("documents")
    exported_metadatas = exported.get("metadatas")
    exported_embeddings = exported.get("embeddings")
    exported_record_count = len(exported_documents) if exported_documents is not None else 0
    source_atomic_records: list[dict] = []
    unmapped_source_records: list[dict] = []
    rows = zip(
        exported_documents if exported_documents is not None else [],
        exported_metadatas if exported_metadatas is not None else [],
        exported_embeddings if exported_embeddings is not None else [],
    )
    prepared: dict[str, tuple[str, dict, object]] = {}
    for text, metadata, embedding in rows:
        metadata = dict(metadata or {})
        if metadata.get("content_type") not in {"topic_candidate", "graph_topic"}:
            continue
        source_atomic_records.append(metadata)
        date_str = str(metadata.get("date") or "")
        search_document = _search_document_for_candidate(
            {
                "url": metadata.get("url"),
                "title": metadata.get("title"),
                "source": metadata.get("source"),
            },
            date_str,
            lookup,
        )
        daily_item_id = str(search_document.get("daily_item_id") or search_document.get("occurrence_id") or "")
        if not daily_item_id:
            unmapped_source_records.append({
                "date": date_str,
                "source": str(metadata.get("source") or ""),
                "title": str(metadata.get("title") or ""),
                "url": str(metadata.get("url") or ""),
            })
            continue
        metadata.update(
            {
                "content_type": "topic_candidate",
                "citation_id": daily_item_id,
                "occurrence_id": daily_item_id,
                "daily_item_id": daily_item_id,
                "content_id": str(search_document.get("content_id") or metadata.get("content_id") or ""),
                "local_url": str(search_document.get("local_url") or ""),
                "url": str(search_document.get("external_url") or metadata.get("url") or ""),
                "report_date": str(search_document.get("report_date") or search_document.get("date") or date_str),
                "publication_date": str(search_document.get("publication_date") or ""),
                "publication_date_source": str(search_document.get("publication_date_source") or "unknown"),
                "source_updated_at": str(search_document.get("source_updated_at") or ""),
                "observed_at": str(search_document.get("observed_at") or search_document.get("date") or date_str),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "effective_date": str(search_document.get("effective_date") or search_document.get("date") or date_str),
                "effective_date_basis": str(search_document.get("effective_date_basis") or "report_date_fallback"),
                "entity_ids": _metadata_value(infer_entity_ids(
                    search_document.get("entity_ids") or search_document.get("entities"),
                    search_document.get("title"),
                    search_document.get("source"),
                )),
            }
        )
        prepared.setdefault(daily_item_id, (str(text or ""), metadata, embedding))

    if exported_record_count > 0 and documents and not prepared:
        raise RuntimeError(
            "existing vectors could not be mapped to atomic search documents; "
            "full re-embedding was stopped"
        )

    items = list(prepared.items())
    batch_size = 500
    for start in range(0, len(items), batch_size):
        batch = items[start : start + batch_size]
        target_store.add_preembedded(
            [item[1][0] for item in batch],
            [item[1][1] for item in batch],
            [item[0] for item in batch],
            [item[1][2].tolist() if hasattr(item[1][2], "tolist") else item[1][2] for item in batch],
        )

    missing = [
        document for document in documents
        if str(document.get("daily_item_id") or document.get("occurrence_id") or "") not in prepared
    ]
    new_embedding_count = 0
    for start in range(0, len(missing), batch_size):
        batch = missing[start : start + batch_size]
        chunks = []
        metadatas = []
        ids = []
        for document in batch:
            identity = str(document.get("daily_item_id") or document.get("occurrence_id") or "")
            display = document.get("display_fields") or {}
            text = "\n".join(
                str(value).strip()
                for value in (
                    document.get("title"),
                    document.get("summary"),
                    display.get("recommended_topic"),
                    display.get("reason"),
                )
                if value
            )
            if not identity or not text:
                continue
            chunks.append(text)
            ids.append(identity)
            metadatas.append({
                "content_type": "topic_candidate",
                "date": str(document.get("date") or ""),
                "report_date": str(document.get("report_date") or document.get("date") or ""),
                "publication_date": str(document.get("publication_date") or ""),
                "publication_date_source": str(document.get("publication_date_source") or "unknown"),
                "source_updated_at": str(document.get("source_updated_at") or ""),
                "observed_at": str(document.get("observed_at") or document.get("date") or ""),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "effective_date": str(document.get("effective_date") or document.get("date") or ""),
                "effective_date_basis": str(document.get("effective_date_basis") or "report_date_fallback"),
                "report_type": "topic-pool",
                "source": str(document.get("source") or ""),
                "title": str(document.get("title") or ""),
                "url": str(document.get("external_url") or ""),
                "score": document.get("score") or 0,
                "action": str(document.get("action") or ""),
                "category": str(document.get("category") or ""),
                "citation_id": identity,
                "occurrence_id": identity,
                "daily_item_id": identity,
                "content_id": str(document.get("content_id") or ""),
                "local_url": str(document.get("local_url") or ""),
                "evidence": str(document.get("summary") or ""),
                "tags": ", ".join(str(tag) for tag in document.get("tags", [])),
                "entity_ids": _metadata_value(infer_entity_ids(
                    document.get("entity_ids") or document.get("entities"),
                    document.get("title"),
                    document.get("source"),
                )),
            })
        if chunks:
            target_store.add_chunks(chunks, metadatas, ids)
            new_embedding_count += len(chunks)
    output_count = len(prepared) + new_embedding_count
    if report_sink is not None:
        output_dates: dict[str, int] = {}
        atr_count = 0
        entity_count = 0
        for document in documents:
            identity = str(document.get("daily_item_id") or document.get("occurrence_id") or "")
            if not identity:
                continue
            date_str = str(document.get("date") or "")
            output_dates[date_str] = output_dates.get(date_str, 0) + 1
            atr_count += int(identity.startswith("ATR-"))
            entity_count += int(bool(infer_entity_ids(
                document.get("entity_ids") or document.get("entities"),
                document.get("title"),
                document.get("source"),
            )))
        target_count = len({
            str(document.get("daily_item_id") or document.get("occurrence_id") or "")
            for document in documents
            if document.get("daily_item_id") or document.get("occurrence_id")
        })
        report_sink.update({
            "source_record_count": exported_record_count,
            "source_atomic_count": len(source_atomic_records),
            "reused_embedding_count": len(prepared),
            "new_embedding_count": new_embedding_count,
            "unmapped_source_atomic_count": len(unmapped_source_records),
            "unmapped_source_records": unmapped_source_records,
            "target_document_count": target_count,
            "output_record_count": output_count,
            "atr_id_coverage": round(atr_count / target_count, 4) if target_count else 0.0,
            "entity_id_coverage": round(entity_count / target_count, 4) if target_count else 0.0,
            "per_date_output_counts": dict(sorted(output_dates.items())),
        })
    return output_count


def _load_reports(date_dir: Path) -> dict[str, str]:
    """Load all .md reports (excluding English variants and rollups)."""
    reports = {}
    skip_suffixes = ("-en.md",)
    skip_names = ("ai-weekly.md", "ai-monthly.md")
    for f in date_dir.glob("*.md"):
        if any(f.name.endswith(s) for s in skip_suffixes):
            continue
        if f.name in skip_names:
            continue
        try:
            reports[f.stem] = f.read_text(encoding="utf-8")
        except OSError as e:
            print(f"  [ingest] Failed to read {f}: {e}")
    return reports


def _find_digest_dates_in(digests: Path) -> list[str]:
    if not digests.exists():
        return []
    return sorted(d.name for d in digests.iterdir() if d.is_dir() and DATE_PATTERN.match(d.name))


def chunk_text(text: str | None, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into chunks by ## headers, then paragraphs, then characters with overlap."""
    if not text or not text.strip():
        return []
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be > overlap")

    chunks: list[str] = []
    # 1. Split by ## headers
    sections = re.split(r"\n(?=##\s)", text)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= chunk_size:
            chunks.append(section)
        else:
            # 2. Split by paragraphs
            paragraphs = section.split("\n\n")
            current = ""
            for para in paragraphs:
                if len(current) + len(para) + 2 <= chunk_size:
                    current = f"{current}\n\n{para}" if current else para
                else:
                    if current:
                        chunks.append(current.strip())
                    # 3. Oversized paragraph: split by character with overlap
                    while len(para) > chunk_size:
                        chunks.append(para[:chunk_size].strip())
                        para = para[chunk_size - overlap :]
                    current = para
            if current:
                chunks.append(current.strip())

    return [c for c in chunks if len(c) > 20]


def select_ingestion_dates(requested_dates: list[str] | None = None) -> list[str]:
    """Resolve an optional date subset against corpus dates that exist locally."""
    available = _find_digest_dates()
    if requested_dates is None:
        return available

    invalid = sorted({date for date in requested_dates if not DATE_PATTERN.fullmatch(date)})
    if invalid:
        raise ValueError(f"Invalid digest date(s): {', '.join(invalid)}")

    available_set = set(available)
    missing = sorted(set(requested_dates) - available_set)
    if missing:
        raise ValueError(f"Digest date(s) not found locally: {', '.join(missing)}")
    # The caller may intentionally prioritize recent reports for first-use
    # availability. Validation must not silently replace that product order.
    return list(dict.fromkeys(requested_dates))


async def ingest_graph_dates(
    driver,
    dates: list[str] | None = None,
    on_date_ingested: Callable[[str], None] | None = None,
) -> list[str]:
    """Replace each requested graph date in its own all-or-nothing transaction."""
    from rag.graphrag.builder import KnowledgeGraphBuilder
    from rag.graphrag.schema import init_schema

    await init_schema(driver)
    selected_dates = select_ingestion_dates(dates)
    search_document_lookup = build_search_document_lookup(load_search_documents())
    ingested_dates: list[str] = []
    for date_str in selected_dates:
        date_dir = Path(DIGESTS_DIR) / date_str
        topic_pool = normalize_topic_pool(_load_topic_pool(date_dir), date_str)
        topic_pool = attach_search_document_identity(topic_pool, date_str, search_document_lookup)
        reports = _load_reports(date_dir)
        if not topic_pool.get("candidates") and not reports:
            continue

        async def write_date(transaction_driver):
            builder = KnowledgeGraphBuilder(transaction_driver)
            await builder.ingest_date(
                date_str,
                topic_pool,
                reports,
                refresh_rollups=False,
            )

        await driver.execute_write_transaction(write_date)
        ingested_dates.append(date_str)
        if on_date_ingested:
            on_date_ingested(date_str)
    if ingested_dates:
        await KnowledgeGraphBuilder(driver).refresh_rollups()
    return ingested_dates


async def run_ingestion(
    dates: list[str] | None = None,
    on_date_ingested: Callable[[str], None] | None = None,
) -> tuple[int, dict]:
    """Ingest all dates or a requested subset, then verify store consistency.

    Returns:
        Tuple of (ingested_date_count, consistency_report_dict).
        G-4 修复：ingestion 完成后自动校验 Neo4j 与 ChromaDB 的数据一致性。
    """
    from rag.graphrag.builder import KnowledgeGraphBuilder
    from rag.graphrag.driver import Neo4jDriver
    from rag.graphrag.schema import init_schema
    from rag.retriever.vector_store import VectorStore
    from rag.consistency import post_ingestion_verify

    driver = Neo4jDriver(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    await driver.connect()
    vector_store = VectorStore(CHROMA_DIR)

    try:
        await init_schema(driver)
        builder = KnowledgeGraphBuilder(driver)
        selected_dates = select_ingestion_dates(dates)
        scope = "changed" if dates is not None else "available"
        print(f"[ingest] Found {len(selected_dates)} {scope} digest dates")

        ingested_dates = []
        search_document_lookup = build_search_document_lookup(load_search_documents())
        for date_str in selected_dates:
            date_dir = Path(DIGESTS_DIR) / date_str
            topic_pool = normalize_topic_pool(_load_topic_pool(date_dir), date_str)
            topic_pool = attach_search_document_identity(topic_pool, date_str, search_document_lookup)
            reports = _load_reports(date_dir)
            if not topic_pool.get("candidates") and not reports:
                continue

            # Neo4j knowledge graph
            await builder.ingest_date(date_str, topic_pool, reports)

            # ChromaDB vector store
            try:
                chunk_count = ingest_vector_chunks_for_date(
                    vector_store,
                    date_str,
                    topic_pool,
                    reports,
                    search_document_lookup=search_document_lookup,
                )
            except Exception as e:
                print(f"  [ingest] ChromaDB write failed for {date_str}: {e}")
                # Do not checkpoint a date whose vector evidence is missing.
                # A later restart can safely retry it from the beginning.
                continue

            ingested_dates.append(date_str)
            if on_date_ingested:
                on_date_ingested(date_str)
            print(f"[ingest] {date_str}: ingested ({chunk_count} chunks → ChromaDB)")

        print(f"[ingest] ChromaDB total: {vector_store.count()} chunks")

        # G-4 修复：ingestion 后执行一致性校验
        consistency_report = None
        if ingested_dates:
            try:
                report = await post_ingestion_verify(driver, vector_store, ingested_dates)
                consistency_report = report.to_dict()
                if report.is_consistent:
                    print("[ingest] Consistency check PASSED — Neo4j and ChromaDB are in sync")
                else:
                    print(f"[ingest] Consistency check FAILED — missing_in_chroma: {report.missing_in_chroma}, missing_in_neo4j: {report.missing_in_neo4j}")
            except Exception as e:
                print(f"[ingest] Consistency check error: {e}")
                consistency_report = {"error": str(e), "is_consistent": False}

        return len(ingested_dates), consistency_report or {}
    finally:
        await driver.close()
        vector_store.close()


def main():
    parser = argparse.ArgumentParser(description="Ingest AI Trend Radar digests into RAG stores.")
    parser.add_argument(
        "--vector-only",
        action="store_true",
        help="Ingest only ChromaDB vector chunks without connecting to Neo4j.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run consistency verification after ingestion (G-4 fix).",
    )
    args = parser.parse_args()

    from rag.runtime_admin_client import request_local_service

    forwarded = request_local_service("/ingest")
    if forwarded is not None:
        if args.vector_only:
            print("[ingest] Running service detected; using the safe full-generation update path.")
        print(json.dumps(forwarded, ensure_ascii=False, indent=2))
        return

    from rag.config import INDEX_GENERATIONS_DIR

    if (Path(INDEX_GENERATIONS_DIR) / "active-generation.json").exists():
        raise SystemExit(
            "[ingest] Managed index exists but the RAG service is offline. "
            "Start the service first so ingestion can use the single-writer generation path."
        )

    if args.vector_only:
        from rag.retriever.vector_store import VectorStore

        vector_store = VectorStore(CHROMA_DIR)
        try:
            count = ingest_all_vector_chunks(vector_store)
        finally:
            vector_store.close()
        print(f"[ingest:vector] Done. Ingested {count} chunks.")
        return

    count, consistency = asyncio.run(run_ingestion())
    print(f"[ingest] Done. Processed {count} dates.")
    if consistency:
        if consistency.get("is_consistent"):
            print("[ingest] Data consistency: VERIFIED")
        elif consistency.get("error"):
            print(f"[ingest] Data consistency check error: {consistency['error']}")
        else:
            print(f"[ingest] Data consistency: MISMATCH — {consistency}")


if __name__ == "__main__":
    main()
