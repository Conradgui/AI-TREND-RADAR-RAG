"""Generation-local exact and SQLite FTS5 lexical retrieval."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

from rag.entity_identity import infer_entity_ids, query_entity_ids


def normalize_lexical_text(value: object) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(value or "").casefold()).strip()


def _is_complete_title_in_query(query: str, title: str) -> bool:
    """Return true only when a wrapped query contains one complete title.

    A raw substring check turns short titles such as ``min.`` into false exact
    matches inside entity names such as ``Gemini``.  Latin titles therefore
    require token boundaries; CJK titles retain phrase matching but must carry
    enough signal to be useful as a navigation target.
    """
    if not title or query == title:
        return query == title
    compact_title = title.replace(" ", "")
    if len(compact_title) < 4:
        return False
    if re.search(r"[\u4e00-\u9fff]", title):
        return title in query
    return re.search(
        rf"(?<![a-z0-9]){re.escape(title)}(?![a-z0-9])",
        query,
    ) is not None


_TITLE_STOPWORDS = {
    "a", "an", "the", "introducing", "improving", "more", "details",
    "on", "our", "what", "is", "about", "recent", "latest", "update",
}

_BILINGUAL_EVENT_TOKENS = frozenset({"ipo"})


def _repository_title_alias_in_query(query: str, title: str) -> bool:
    """Recognise repeated owner/repository titles without fuzzy matching."""
    title_tokens = title.split()
    midpoint = len(title_tokens) // 2
    if midpoint and len(title_tokens) % 2 == 0 and title_tokens[:midpoint] == title_tokens[midpoint:]:
        alias = " ".join(title_tokens[:midpoint])
        return len(alias) >= 4 and re.search(
            rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", query
        ) is not None
    return False


def _repository_slug_in_query(query: str, title: str) -> bool:
    """Treat the repository part of ``owner/repository`` as a named alias."""
    if "/" not in title:
        return False
    repository = normalize_lexical_text(title.rsplit("/", 1)[-1])
    if len(repository.replace(" ", "")) < 4:
        return False
    return re.search(
        rf"(?<![a-z0-9]){re.escape(repository)}(?![a-z0-9])",
        query,
    ) is not None


def _stem_token(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


_DESCRIPTOR_CONCEPTS = {
    "codebase": ("代码库", "codebase"),
    "docs": ("文档", "docs", "documents"),
    "sql_schema": ("sql schema", "sql schemas", "数据库结构"),
    "config": ("配置", "config", "configs", "configuration"),
    "knowledge_graph": ("知识图谱", "knowledge graph"),
    "vector_store": ("向量库", "vector store", "vector database"),
    "queryable": ("可查询", "queryable"),
    "automatic_mode": ("自动模式", "auto mode", "automatic mode"),
    "human_approval": ("人工审批", "人为审核", "human approval", "manual approval"),
    "dangerous_command": ("危险命令", "dangerous command", "unsafe command"),
}


def _descriptor_terms(value: str) -> set[str]:
    folded = value.casefold()
    terms = {
        _stem_token(token)
        for token in re.findall(r"[a-z0-9]+", folded)
        if len(token) >= 3 and token not in _TITLE_STOPWORDS
    }
    for concept, aliases in _DESCRIPTOR_CONCEPTS.items():
        if any(alias in folded for alias in aliases):
            terms.add(concept)
    return terms


def _descriptor_score(query: str, body: str) -> float | None:
    """Admit one strong functional description, not generic semantic fuzz."""
    query_terms = _descriptor_terms(query)
    body_terms = _descriptor_terms(body)
    overlap = query_terms & body_terms
    if len(overlap) < 3 or not query_terms:
        return None
    coverage = len(overlap) / len(query_terms)
    if coverage < 0.3:
        return None
    return 1.0 - coverage


def _query_date_hint(query: str) -> str:
    iso = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", query)
    if iso:
        return f"{iso.group(1)}-{int(iso.group(2)):02d}-{int(iso.group(3)):02d}"
    chinese = re.search(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日", query)
    if chinese:
        return f"-{int(chinese.group(1)):02d}-{int(chinese.group(2)):02d}"
    return ""


def _date_sort_key(metadata: dict, hint: str) -> tuple[int, str]:
    value = str(metadata.get("effective_date") or metadata.get("date") or "")
    matches = bool(hint and (value == hint or value.endswith(hint)))
    return (0 if matches else 1, "".join(chr(255 - ord(ch)) for ch in value))


def _title_overlap_score(query: str, title: str) -> float | None:
    """Recognise a named item when harmless title prefixes were omitted.

    This is deliberately stricter than generic fuzzy search: navigation needs
    at least two shared meaningful tokens and strong coverage on both sides.
    Descriptive questions remain research queries instead of being forced onto
    an arbitrary item.
    """
    entity_tokens = {
        token
        for entity_id in query_entity_ids(query)
        for token in entity_id.split("-")
    }
    query_tokens = {
        token for token in re.findall(r"[a-z0-9]+", query)
        if token not in _TITLE_STOPWORDS and token not in entity_tokens
    }
    title_tokens = {
        token for token in re.findall(r"[a-z0-9]+", title)
        if token not in _TITLE_STOPWORDS and token not in entity_tokens
    }
    overlap = query_tokens & title_tokens
    if len(overlap) < 2 or not query_tokens or not title_tokens:
        return None
    query_coverage = len(overlap) / len(query_tokens)
    title_coverage = len(overlap) / len(title_tokens)
    if query_coverage < 0.6 or title_coverage < 0.6:
        return None
    return 1.0 - (0.5 * query_coverage + 0.5 * title_coverage)


def _entity_event_record_score(query: str, title: str, body: str) -> float | None:
    """Admit a named entity plus a stable event token for research retrieval.

    This is intentionally narrower than fuzzy title matching: an entity alone
    cannot admit a result, and the event token must be present in both query
    and record text. It supports bilingual event rewrites such as ``上市 → IPO``.
    """
    query_tokens = set(re.findall(r"[a-z0-9]+", query))
    title_tokens = set(re.findall(r"[a-z0-9]+", title))
    record_tokens = title_tokens | set(re.findall(r"[a-z0-9]+", body))
    event_overlap = _BILINGUAL_EVENT_TOKENS & query_tokens & record_tokens
    if not event_overlap:
        return None
    entity_tokens = {
        token
        for entity_id in query_entity_ids(query)
        for token in entity_id.split("-")
        if len(token) >= 3
    }
    if not entity_tokens & title_tokens:
        return None
    return 0.25


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
        if isinstance(expected, dict):
            if "$in" in expected:
                if actual not in expected["$in"]:
                    return False
                continue

            # The metadata store uses ISO-8601 dates, so lexical comparison is
            # chronological comparison. Keep this small subset aligned with the
            # Chroma filter shape used by retrieval plans.
            actual_value = str(actual or "")
            lower_bound = expected.get("$gte")
            upper_bound = expected.get("$lte")
            if lower_bound is not None and actual_value < str(lower_bound):
                return False
            if upper_bound is not None and actual_value > str(upper_bound):
                return False
            if lower_bound is not None or upper_bound is not None:
                continue

        if actual != expected:
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
        date_hint = _query_date_hint(query)
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
                elif _is_complete_title_in_query(normalized, row["title_normalized"]):
                    # Natural-language wrappers such as "X 讲了什么" still
                    # identify one complete title and keep the navigation path.
                    match_type = "exact_title"
                    score = 0.5
                else:
                    match_type = "title_contains_query"
                    score = 1.0
                candidates[row["identity"]] = (row, match_type, score)

            # A user often omits harmless publisher prefixes (for example,
            # "Introducing") from an otherwise specific item name. The exact
            # phrase query below cannot find that case, so use FTS only to
            # obtain a bounded candidate pool and apply a strict token gate.
            ascii_terms = sorted({
                token for token in re.findall(r"[a-z0-9]+", normalized)
                if len(token) >= 3 and token not in _TITLE_STOPWORDS
            })
            if len(ascii_terms) >= 2:
                expression = " OR ".join(f'"{term}"' for term in ascii_terms)
                try:
                    overlap_rows = self.connection.execute(
                        "SELECT e.*, bm25(entries_fts, 3.0, 1.0) AS lexical_score "
                        "FROM entries_fts JOIN entries e USING(identity) "
                        "WHERE entries_fts MATCH ? ORDER BY lexical_score LIMIT ?",
                        (expression, max(k * 20, 100)),
                    ).fetchall()
                except sqlite3.OperationalError:
                    overlap_rows = []
                for row in overlap_rows:
                    if (
                        _repository_title_alias_in_query(normalized, row["title_normalized"])
                        or _repository_slug_in_query(normalized, row["title"])
                    ):
                        candidates.setdefault(
                            row["identity"], (row, "title_in_query", 0.75)
                        )
                        continue
                    overlap_score = _title_overlap_score(normalized, row["title_normalized"])
                    if overlap_score is not None:
                        candidates.setdefault(
                            row["identity"], (row, "title_in_query", overlap_score)
                        )
                        continue
                    entity_event_score = _entity_event_record_score(
                        normalized, row["title_normalized"], row["body"]
                    )
                    if entity_event_score is not None:
                        candidates.setdefault(
                            row["identity"], (row, "entity_event", entity_event_score)
                        )
                        continue
                    descriptor_score = _descriptor_score(normalized, row["body"])
                    if descriptor_score is not None:
                        candidates.setdefault(
                            row["identity"], (row, "descriptor", descriptor_score)
                        )

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
                0 if item[1] == "exact_id" else 1 if item[1] == "exact_title"
                else 2 if item[1] in {"title_in_query", "entity_event"} else 3 if item[1] == "descriptor" else 4,
                *_date_sort_key(json.loads(item[0]["metadata"]), date_hint),
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
            document.get("external_url"),
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
            "source_role": str(document.get("source_role") or ""),
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
