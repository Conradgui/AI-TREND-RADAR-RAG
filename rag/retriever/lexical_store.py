"""Generation-local exact and SQLite FTS5 lexical retrieval."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

from rag.entity_identity import infer_entity_ids


def normalize_lexical_text(value: object) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(value or "").casefold()).strip()


def metadata_matches_filter(metadata: dict, where: dict | None) -> bool:
    if not where:
        return True
    if "$and" in where:
        return all(metadata_matches_filter(metadata, clause) for clause in where["$and"])
    if "$or" in where:
        return any(metadata_matches_filter(metadata, clause) for clause in where["$or"])
    for key, expected in where.items():
        actual = metadata.get(key)
        if key == "content_type" and actual == "graph_topic" and expected == "topic_candidate":
            actual = "topic_candidate"
        if key == "source_family" and not actual:
            source = str(metadata.get("source") or "").casefold()
            if source.startswith("github"):
                actual = "GitHub"
        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif actual != expected:
            return False
    return True


class LexicalStore:
    """A small generation-scoped lexical index with deterministic identities."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS entries ("
            "identity TEXT PRIMARY KEY, title_normalized TEXT NOT NULL, "
            "title TEXT NOT NULL, body TEXT NOT NULL, metadata TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5("
            "identity UNINDEXED, title, body, tokenize='trigram')"
        )
        self.connection.commit()

    def rebuild(self, documents: list[dict]) -> int:
        self.connection.execute("DELETE FROM entries")
        self.connection.execute("DELETE FROM entries_fts")
        count = 0
        for document in documents:
            if document.get("result_type") not in {None, "item"}:
                continue
            if document.get("report_type") not in {None, "daily"}:
                continue
            identity = str(document.get("occurrence_id") or "").strip()
            title = str(document.get("title") or "").strip()
            if not identity or not title:
                continue
            metadata = self._metadata(document, identity)
            body = self._body(document)
            self.connection.execute(
                "INSERT OR REPLACE INTO entries VALUES (?, ?, ?, ?, ?)",
                (identity, normalize_lexical_text(title), title, body, json.dumps(metadata, ensure_ascii=False)),
            )
            self.connection.execute(
                "INSERT INTO entries_fts(identity, title, body) VALUES (?, ?, ?)",
                (identity, title, body),
            )
            count += 1
        self.connection.commit()
        return count

    def search(self, query: str, k: int = 5, where: dict | None = None) -> list[dict]:
        normalized = normalize_lexical_text(query)
        compact = normalized.replace(" ", "")
        if not compact:
            return []

        candidates: dict[str, tuple[sqlite3.Row, str, float]] = {}
        identity_match = re.search(
            r"(?<![A-Z0-9])ATR-\d{8}-[A-F0-9]{6}(?![A-Z0-9])",
            str(query or "").upper(),
        )
        exact_identity = identity_match.group(0) if identity_match else ""
        if exact_identity:
            row = self.connection.execute(
                "SELECT * FROM entries WHERE identity = ?",
                (exact_identity,),
            ).fetchone()
            if row is not None:
                candidates[row["identity"]] = (row, "exact_id", -1.0)
        if len(compact) > 2:
            rows = self.connection.execute(
                "SELECT * FROM entries WHERE instr(?, title_normalized) > 0 "
                "OR instr(title_normalized, ?) > 0 LIMIT ?",
                (normalized, normalized, max(k * 4, 20)),
            ).fetchall()
            for row in rows:
                if row["title_normalized"] == normalized:
                    match_type = "exact_title"
                    score = 0.0
                elif normalized.find(row["title_normalized"]) >= 0:
                    # Natural-language wrappers such as "X 讲了什么" still
                    # identify one complete title and keep the navigation path.
                    match_type = "exact_title"
                    score = 0.5
                else:
                    match_type = "title_contains_query"
                    score = 1.0
                candidates[row["identity"]] = (row, match_type, score)

        if len(compact) <= 2:
            rows = self.connection.execute(
                "SELECT * FROM entries WHERE instr(replace(title_normalized, ' ', ''), ?) > 0 "
                "OR instr(replace(body, ' ', ''), ?) > 0 LIMIT ?",
                (compact, compact, max(k * 4, 20)),
            ).fetchall()
            for row in rows:
                candidates.setdefault(row["identity"], (row, "substring", 1.0))
        else:
            phrase = '"' + normalized.replace('"', '""') + '"'
            try:
                rows = self.connection.execute(
                    "SELECT e.*, bm25(entries_fts, 3.0, 1.0) AS lexical_score "
                    "FROM entries_fts JOIN entries e USING(identity) "
                    "WHERE entries_fts MATCH ? ORDER BY lexical_score LIMIT ?",
                    (phrase, max(k * 4, 20)),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
            for row in rows:
                candidates.setdefault(
                    row["identity"],
                    (row, "lexical", float(row["lexical_score"])),
                )

        ranked = sorted(
            candidates.values(),
            key=lambda item: (
                0 if item[1] == "exact_id" else 1 if item[1] == "exact_title" else 2,
                item[2],
                item[0]["identity"],
            ),
        )
        results = []
        for row, match_type, lexical_score in ranked:
            metadata = json.loads(row["metadata"])
            if not metadata_matches_filter(metadata, where):
                continue
            results.append(
                {
                    "text": row["body"],
                    "metadata": metadata,
                    "match_type": match_type,
                    "lexical_score": lexical_score,
                }
            )
            if len(results) >= k:
                break
        return results

    def recent(self, limit: int = 100, where: dict | None = None) -> list[dict]:
        """Return structured Daily Corpus items for aggregation, not text matching.

        Trend discovery needs a bounded set of recent candidate records before it
        applies product-owned ranking and diversity rules. It deliberately does
        not invoke FTS or vector similarity.
        """
        rows = self.connection.execute("SELECT * FROM entries").fetchall()
        candidates = []
        for row in rows:
            metadata = json.loads(row["metadata"])
            if not metadata_matches_filter(metadata, where):
                continue
            candidates.append(
                {
                    "text": row["body"],
                    "metadata": metadata,
                    "match_type": "browse",
                    "lexical_score": 0.0,
                }
            )

        sort_field = _date_filter_field(where) or "effective_date"
        candidates.sort(
            key=lambda item: (
                str(item["metadata"].get(sort_field) or item["metadata"].get("date") or ""),
                _numeric_score(item["metadata"].get("score")),
                str(item["metadata"].get("citation_id") or ""),
            ),
            reverse=True,
        )
        return candidates[:max(0, limit)]
    @staticmethod
    def _body(document: dict) -> str:
        display = document.get("display_fields") or {}
        evidence = display.get("evidence") or []
        parts = [
            document.get("title"),
            document.get("summary"),
            display.get("recommended_topic"),
            display.get("reason"),
            "；".join(str(item) for item in evidence) if isinstance(evidence, list) else evidence,
            " ".join(str(item) for item in document.get("tags", [])),
            " ".join(str(item) for item in document.get("entities", [])),
        ]
        return "\n".join(str(part).strip() for part in parts if part)

    @staticmethod
    def _metadata(document: dict, identity: str) -> dict:
        return {
            "content_type": "topic_candidate",
            "date": str(document.get("date") or ""),
            "report_date": str(document.get("report_date") or document.get("date") or ""),
            "publication_date": str(document.get("publication_date") or ""),
            "publication_date_source": str(document.get("publication_date_source") or "unknown"),
            "source_updated_at": str(document.get("source_updated_at") or ""),
            "observed_at": str(document.get("observed_at") or document.get("date") or ""),
            "ingested_at": str(document.get("ingested_at") or ""),
            "effective_date": str(document.get("effective_date") or document.get("date") or ""),
            "effective_date_basis": str(document.get("effective_date_basis") or "report_date_fallback"),
            "source": str(document.get("source") or ""),
            "title": str(document.get("title") or ""),
            "url": str(document.get("external_url") or ""),
            "local_url": str(document.get("local_url") or ""),
            "content_id": str(document.get("content_id") or ""),
            "occurrence_id": identity,
            "citation_id": identity,
            "category": str(document.get("category") or ""),
            "score": document.get("score") or 0,
            "evidence": str(document.get("summary") or ""),
            "entity_ids": infer_entity_ids(
                document.get("entity_ids") or document.get("entities"),
                document.get("title"),
                document.get("source"),
            ),
            "content_kind": str(document.get("content_kind") or ""),
            "event_type": str(document.get("event_type") or ""),
            "subject_entity_ids": document.get("subject_entity_ids") or [],
            "mentioned_entity_ids": document.get("mentioned_entity_ids") or [],
            "temporal_confidence": str(document.get("temporal_confidence") or ""),
            "event_group_id": str(document.get("event_group_id") or ""),
        }

    def count(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS count FROM entries").fetchone()
        return int(row["count"])

    def close(self) -> None:
        self.connection.close()


def _numeric_score(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _date_filter_field(where: dict | None) -> str | None:
    if not where:
        return None
    if "$and" in where:
        for clause in where["$and"]:
            field = _date_filter_field(clause)
            if field:
                return field
    for field in ("publication_date", "source_updated_at", "report_date", "effective_date"):
        if field in where:
            return field
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a generation-local lexical search index.")
    parser.add_argument("--search-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--through-date", default="")
    args = parser.parse_args()

    payload = json.loads(args.search_index.read_text(encoding="utf-8"))
    documents = payload.get("documents", []) if isinstance(payload, dict) else []
    if args.through_date:
        documents = [
            document
            for document in documents
            if str(document.get("date") or "") <= args.through_date
        ]
    store = LexicalStore(args.output)
    try:
        count = store.rebuild(documents)
    finally:
        store.close()
    print(json.dumps({"output": str(args.output), "documents": count}, ensure_ascii=False))


if __name__ == "__main__":
    main()
