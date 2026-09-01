"""Small persistent lifecycle for learned entity relationships.

The store is intentionally separate from the curated registry. AI observations
enter as candidates and become retrievable only after traceable evidence is
recorded. The public interface does not expose the on-disk JSON shape.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from rag.entity_identity import canonical_entity_id, normalize_entity_name


DEFAULT_MEMORY_PATH = Path(__file__).parent / "data" / "entity-relation-memory.json"
RELATION_TYPES = {"developed_by", "product_of", "owned_by", "distributed_on"}
DECISION_STATES = {"verified", "rejected", "revoked"}


class EntityRelationMemory:
    """Persist candidate decisions and expose only verified expansions."""

    def __init__(
        self,
        path: Path = DEFAULT_MEMORY_PATH,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()

    def observe(
        self,
        from_entity_id: object,
        to_entity_id: object,
        relation: str,
        *,
        evidence: list[dict] | None = None,
        parser_version: str = "",
    ) -> dict:
        source = canonical_entity_id(from_entity_id)
        target = canonical_entity_id(to_entity_id)
        relation = str(relation or "").strip()
        if not source or not target or source == target:
            raise ValueError("Entity relation requires two distinct entities")
        if relation not in RELATION_TYPES:
            raise ValueError("Unsupported entity relation")
        candidate_id = _candidate_id(source, target, relation)
        now = self._timestamp()
        with self._lock:
            payload = self._read()
            records = payload["records"]
            record = next(
                (item for item in records if item["candidate_id"] == candidate_id),
                None,
            )
            if record is None:
                record = {
                    "candidate_id": candidate_id,
                    "from_entity_id": source,
                    "to_entity_id": target,
                    "relation": relation,
                    "status": "candidate",
                    "weight": 0.5,
                    "evidence": [],
                    "parser_versions": [],
                    "observation_count": 0,
                    "created_at": now,
                    "updated_at": now,
                    "decision_reason": "",
                }
                records.append(record)
            record["observation_count"] += 1
            record["updated_at"] = now
            if parser_version and parser_version not in record["parser_versions"]:
                record["parser_versions"].append(parser_version)
            record["evidence"] = _merge_evidence(record["evidence"], evidence or [])
            self._write(payload)
            return dict(record)

    def decide(
        self,
        candidate_id: str,
        status: str,
        *,
        evidence: list[dict] | None = None,
        reason: str = "",
    ) -> dict:
        status = str(status or "").strip()
        if status not in DECISION_STATES:
            raise ValueError("Unsupported relation decision")
        if status in {"rejected", "revoked"} and not str(reason or "").strip():
            raise ValueError("Rejected or revoked relation requires a reason")
        with self._lock:
            payload = self._read()
            record = next(
                (item for item in payload["records"] if item["candidate_id"] == candidate_id),
                None,
            )
            if record is None:
                raise KeyError(candidate_id)
            record["evidence"] = _merge_evidence(record["evidence"], evidence or [])
            if status == "verified" and not _has_supporting_evidence(record["evidence"]):
                raise ValueError("Verified relation requires traceable supporting evidence")
            record["status"] = status
            record["decision_reason"] = str(reason or "").strip()
            record["updated_at"] = self._timestamp()
            self._write(payload)
            return dict(record)

    def verified_expansions(self, values: object) -> list[dict]:
        if isinstance(values, (str, bytes)):
            raw_values = [values]
        elif isinstance(values, (list, tuple, set)):
            raw_values = list(values)
        else:
            raw_values = [values]
        sources = {canonical_entity_id(value) for value in raw_values}
        sources.discard("")
        with self._lock:
            records = self._read()["records"]
        result = []
        for record in records:
            if record["status"] != "verified" or record["from_entity_id"] not in sources:
                continue
            result.append({
                "from_entity_id": record["from_entity_id"],
                "entity_id": record["to_entity_id"],
                "relation": record["relation"],
                "weight": float(record.get("weight", 0.5)),
                "provenance": "learned_verified",
            })
        return result

    def query_entity_ids(self, text: str) -> list[str]:
        """Match only entities from verified learned relationships."""
        normalized = normalize_entity_name(text)
        if not normalized:
            return []
        with self._lock:
            records = self._read()["records"]
        candidates = {
            entity_id
            for record in records
            if record["status"] == "verified"
            for entity_id in (record["from_entity_id"], record["to_entity_id"])
        }
        matches = []
        for entity_id in sorted(candidates, key=len, reverse=True):
            alias = normalize_entity_name(entity_id.replace("-", " "))
            if alias and re.search(
                r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])",
                normalized,
            ):
                matches.append(entity_id)
        return matches

    def verified_records(self) -> list[dict]:
        """Return projection-safe copies of the currently verified records."""
        with self._lock:
            records = self._read()["records"]
        return [dict(record) for record in records if record["status"] == "verified"]

    def _read(self) -> dict:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"schema_version": "1.0", "records": []}
        if payload.get("schema_version") != "1.0" or not isinstance(payload.get("records"), list):
            raise ValueError("Unsupported entity relation memory format")
        return payload

    def _write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=self.path.parent,
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def _timestamp(self) -> str:
        return self._clock().astimezone(timezone.utc).isoformat()


def _candidate_id(source: str, target: str, relation: str) -> str:
    digest = hashlib.sha256(f"{source}\0{relation}\0{target}".encode()).hexdigest()[:16]
    return f"REL-{digest.upper()}"


def _merge_evidence(existing: list[dict], new: list[dict]) -> list[dict]:
    result = [dict(item) for item in existing]
    seen = {json.dumps(item, ensure_ascii=False, sort_keys=True) for item in result}
    for item in new:
        normalized = dict(item)
        key = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            result.append(normalized)
            seen.add(key)
    return result


def _has_supporting_evidence(evidence: list[dict]) -> bool:
    return any(
        item.get("supports") is True
        and bool(str(item.get("url") or item.get("atr_id") or "").strip())
        for item in evidence
    )
