"""CLI entry point: python -m rag.ingest — ingests digest data into Neo4j + ChromaDB."""

from __future__ import annotations

import asyncio
import argparse
import json
import re
from pathlib import Path

from rag.config import DIGESTS_DIR, CHROMA_DIR, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def build_topic_candidate_chunks(topic_pool: dict, date_str: str) -> tuple[list[str], list[dict], list[str]]:
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
        citation_id = f"{date_str}/topic-pool/{index}"
        metadata = {
            "content_type": "topic_candidate",
            "date": date_str,
            "report_type": "topic-pool",
            "source": candidate.get("source", ""),
            "source_family": infer_source_family(candidate.get("source", "")),
            "title": title,
            "url": candidate.get("url", ""),
            "score": candidate.get("score", 0),
            "action": candidate.get("action", ""),
            "category": candidate.get("category", ""),
            "citation_id": citation_id,
            "evidence": _metadata_value(candidate.get("evidence", "")),
            "tags": ", ".join(str(tag) for tag in candidate.get("tags", [])),
        }
        chunks.append(chunk)
        metadatas.append({key: _metadata_value(value) for key, value in metadata.items()})
        ids.append(citation_id)

    return chunks, metadatas, ids


def ingest_vector_chunks_for_date(vector_store, date_str: str, topic_pool: dict, reports: dict[str, str]) -> int:
    """Replace one day's vector chunks with citation-ready report and topic chunks."""
    vector_store.delete_by_date(date_str)

    chunk_count = 0
    for report_type, content in reports.items():
        chunks = chunk_text(content)
        if not chunks:
            continue
        ids = [f"{date_str}/{report_type}/{i}" for i in range(len(chunks))]
        metadatas = [
            build_report_chunk_metadata(date_str, report_type, i)
            for i in range(len(chunks))
        ]
        vector_store.add_chunks(chunks, metadatas, ids)
        chunk_count += len(chunks)

    topic_chunks, topic_metadatas, topic_ids = build_topic_candidate_chunks(topic_pool, date_str)
    if topic_chunks:
        vector_store.add_chunks(topic_chunks, topic_metadatas, topic_ids)
        chunk_count += len(topic_chunks)

    return chunk_count


def ingest_all_vector_chunks(vector_store, digests_dir: str = DIGESTS_DIR) -> int:
    """Ingest all local digest dates into ChromaDB without requiring Neo4j."""
    total_chunks = 0
    dates = _find_digest_dates_in(Path(digests_dir))

    for date_str in dates:
        date_dir = Path(digests_dir) / date_str
        topic_pool = normalize_topic_pool(_load_topic_pool(date_dir), date_str)
        reports = _load_reports(date_dir)
        if not topic_pool.get("candidates") and not reports:
            continue
        chunk_count = ingest_vector_chunks_for_date(vector_store, date_str, topic_pool, reports)
        total_chunks += chunk_count
        print(f"[ingest:vector] {date_str}: ingested {chunk_count} chunks")

    print(f"[ingest:vector] ChromaDB total: {vector_store.count()} chunks")
    return total_chunks


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


async def run_ingestion() -> int:
    from rag.graphrag.builder import KnowledgeGraphBuilder
    from rag.graphrag.driver import Neo4jDriver
    from rag.graphrag.schema import init_schema
    from rag.retriever.vector_store import VectorStore

    driver = Neo4jDriver(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    await driver.connect()
    vector_store = VectorStore(CHROMA_DIR)

    try:
        await init_schema(driver)
        builder = KnowledgeGraphBuilder(driver)
        dates = _find_digest_dates()
        print(f"[ingest] Found {len(dates)} digest dates")

        for date_str in dates:
            date_dir = Path(DIGESTS_DIR) / date_str
            topic_pool = normalize_topic_pool(_load_topic_pool(date_dir), date_str)
            reports = _load_reports(date_dir)
            if not topic_pool.get("candidates") and not reports:
                continue

            # Neo4j knowledge graph
            await builder.ingest_date(date_str, topic_pool, reports)

            # ChromaDB vector store
            try:
                chunk_count = ingest_vector_chunks_for_date(vector_store, date_str, topic_pool, reports)
            except Exception as e:
                chunk_count = 0
                print(f"  [ingest] ChromaDB write failed for {date_str}: {e}")

            print(f"[ingest] {date_str}: ingested ({chunk_count} chunks → ChromaDB)")

        print(f"[ingest] ChromaDB total: {vector_store.count()} chunks")
        return len(dates)
    finally:
        await driver.close()


def main():
    parser = argparse.ArgumentParser(description="Ingest AI Trend Radar digests into RAG stores.")
    parser.add_argument(
        "--vector-only",
        action="store_true",
        help="Ingest only ChromaDB vector chunks without connecting to Neo4j.",
    )
    args = parser.parse_args()

    if args.vector_only:
        from rag.retriever.vector_store import VectorStore

        count = ingest_all_vector_chunks(VectorStore(CHROMA_DIR))
        print(f"[ingest:vector] Done. Ingested {count} chunks.")
        return

    count = asyncio.run(run_ingestion())
    print(f"[ingest] Done. Processed {count} dates.")


if __name__ == "__main__":
    main()
