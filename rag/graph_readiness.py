"""Active, cached Neo4j readiness checks for routing and operations."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace


REQUIRED_SEARCH_INDEXES = frozenset({"entity_search", "topic_search"})
REQUIRED_CORE_LABELS = ("Observation", "Content")


@dataclass(frozen=True)
class GraphReadiness:
    status: str
    level: str
    checked_at: float
    latency_ms: float
    error_code: str = ""
    details: dict = field(default_factory=dict)
    cached: bool = False


class GraphReadinessProbe:
    """Hide connectivity, index checks and TTL caching behind one interface."""

    def __init__(self, driver, *, ttl_seconds: float = 15.0, clock=time.monotonic):
        self.driver = driver
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._cache: dict[str, GraphReadiness] = {}

    async def probe(self, level: str = "runtime", *, force: bool = False) -> GraphReadiness:
        if level not in {"runtime", "startup"}:
            raise ValueError(f"unsupported graph readiness level: {level}")
        now = self.clock()
        cached = self._cache.get(level)
        if not force and cached and now - cached.checked_at <= self.ttl_seconds:
            return replace(cached, cached=True)

        started = self.clock()
        try:
            rows = await self.driver.execute_query("RETURN 1 AS ok", timeout=2.0)
            if not rows or rows[0].get("ok") != 1:
                raise RuntimeError("minimal graph query returned no readiness marker")
        except Exception as exc:
            result = GraphReadiness(
                status="unavailable",
                level=level,
                checked_at=now,
                latency_ms=(self.clock() - started) * 1000,
                error_code="graph_connectivity_failed",
                details={"error_type": type(exc).__name__},
            )
            self._cache[level] = result
            return result

        if level == "startup":
            try:
                indexes = await self.driver.execute_query(
                    "SHOW INDEXES YIELD name, state RETURN name, state",
                    timeout=3.0,
                )
            except Exception as exc:
                result = GraphReadiness(
                    status="degraded",
                    level=level,
                    checked_at=now,
                    latency_ms=(self.clock() - started) * 1000,
                    error_code="graph_index_check_failed",
                    details={"error_type": type(exc).__name__},
                )
                self._cache[level] = result
                return result
            online = {
                str(row.get("name"))
                for row in indexes
                if str(row.get("state", "")).upper() == "ONLINE"
            }
            missing = sorted(REQUIRED_SEARCH_INDEXES - online)
            if missing:
                result = GraphReadiness(
                    status="degraded",
                    level=level,
                    checked_at=now,
                    latency_ms=(self.clock() - started) * 1000,
                    error_code="graph_indexes_not_ready",
                    details={"missing_or_offline_indexes": missing},
                )
                self._cache[level] = result
                return result
            try:
                label_rows = await self.driver.execute_query(
                    "UNWIND $required_labels AS required_label "
                    "OPTIONAL MATCH (node) WHERE required_label IN labels(node) "
                    "RETURN required_label, count(node) AS node_count",
                    required_labels=list(REQUIRED_CORE_LABELS),
                    timeout=3.0,
                )
            except Exception as exc:
                result = GraphReadiness(
                    status="degraded",
                    level=level,
                    checked_at=now,
                    latency_ms=(self.clock() - started) * 1000,
                    error_code="graph_core_label_check_failed",
                    details={"error_type": type(exc).__name__},
                )
                self._cache[level] = result
                return result
            counts = {
                str(row.get("required_label")): int(row.get("node_count") or 0)
                for row in label_rows
            }
            empty_labels = [label for label in REQUIRED_CORE_LABELS if counts.get(label, 0) <= 0]
            if empty_labels:
                result = GraphReadiness(
                    status="degraded",
                    level=level,
                    checked_at=now,
                    latency_ms=(self.clock() - started) * 1000,
                    error_code="graph_core_labels_empty",
                    details={"empty_labels": empty_labels},
                )
                self._cache[level] = result
                return result

        result = GraphReadiness(
            status="ready",
            level=level,
            checked_at=now,
            latency_ms=(self.clock() - started) * 1000,
        )
        self._cache[level] = result
        return result
