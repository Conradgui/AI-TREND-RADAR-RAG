"""Knowledge graph builder — ingests digest data into Neo4j."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rag.graphrag.driver import Neo4jDriver


def _infer_entity_type(tag: str) -> str:
    """Infer entity type from tag content. Returns company/technology/project/topic_tag."""
    tag_lower = tag.lower().strip()

    # 1. Exact match for company names (highest priority)
    companies = {
        "openai", "anthropic", "google", "meta", "microsoft", "nvidia",
        "apple", "deepseek", "baidu", "alibaba", "tencent", "百度", "阿里", "腾讯", "字节",
    }
    if tag_lower in companies:
        return "company"

    # 2. Contains technology keywords (including Chinese)
    tech_patterns = [
        "ai", "gpt", "llm", "rag", "agent", "transformer",
        "embedding", "vector", "multimodal", "大模型", "人工智能", "机器学习", "深度学习",
    ]
    if any(t in tag_lower for t in tech_patterns):
        return "technology"

    # 3. Contains project name
    projects = {"langchain", "llamaindex", "chromadb", "neo4j", "ollama", "vllm", "pytorch", "tensorflow"}
    if any(p in tag_lower for p in projects):
        return "project"

    return "topic_tag"


class KnowledgeGraphBuilder:
    """Builds and updates the Neo4j knowledge graph from digest data."""

    def __init__(self, driver: "Neo4jDriver"):
        self.driver = driver

    async def ingest_date(
        self,
        date_str: str,
        topic_pool: dict | None,
        reports: dict[str, str],
        *,
        refresh_rollups: bool = True,
    ) -> None:
        """Replace one day's graph projection and refresh topic rollups."""
        previous_rows = await self.driver.execute_query(
            "MATCH (o:Observation) WHERE o.date = $date "
            "AND coalesce(o.contentId, '') <> '' "
            "RETURN collect(DISTINCT o.contentId) AS content_ids",
            date=date_str,
        )
        previous_content_ids = set(previous_rows[0].get("content_ids", [])) if previous_rows else set()
        await self._clear_date(date_str)
        candidate_count = len(topic_pool.get("candidates", [])) if topic_pool else 0
        await self.driver.execute_write(
            "MERGE (d:DailyDigest {date: $date}) "
            "SET d.candidateCount = $count, d.generatedAt = $now",
            date=date_str, count=candidate_count, now=datetime.now(timezone.utc).isoformat(),
        )

        sources = set()
        if topic_pool:
            for c in topic_pool.get("candidates", []):
                src = c.get("source", "")
                if src:
                    sources.add(src)
        for src in sources:
            await self.driver.execute_write(
                "MERGE (s:Source {id: $id}) SET s.name = $id",
                id=src,
            )

        touched_content_ids: set[str] = set(previous_content_ids)
        if topic_pool:
            for candidate in topic_pool.get("candidates", []):
                content_id = await self._ingest_candidate(candidate, date_str)
                if content_id:
                    touched_content_ids.add(content_id)

        if touched_content_ids:
            await self._refresh_observation_chains(sorted(touched_content_ids))

        for report_type, content in reports.items():
            await self.driver.execute_write(
                "MERGE (doc:Document {id: $id}) "
                "SET doc.title = $title, doc.date = $date, doc.reportType = $type",
                id=f"{date_str}/{report_type}",
                title=report_type,
                date=date_str,
                type=report_type,
            )
            await self.driver.execute_write(
                "MATCH (doc:Document {id: $id}) "
                "MATCH (d:DailyDigest {date: $date}) "
                "MERGE (doc)-[:PART_OF]->(d)",
                id=f"{date_str}/{report_type}", date=date_str,
            )

        if refresh_rollups:
            await self.refresh_rollups()

    async def _clear_date(self, date_str: str) -> None:
        """Remove only date-scoped graph data before a deterministic replacement."""
        await self.driver.execute_write(
            "MATCH (o:Observation {date: $date}) DETACH DELETE o",
            date=date_str,
        )
        await self.driver.execute_write(
            "MATCH (doc:Document {date: $date}) DETACH DELETE doc",
            date=date_str,
        )
        await self.driver.execute_write(
            "MATCH (d:DailyDigest {date: $date}) DETACH DELETE d",
            date=date_str,
        )

    async def refresh_rollups(self) -> None:
        """Derive topic counts and date ranges from APPEARED_ON relationships."""
        await self.driver.execute_write(
            "MATCH (t:Topic) "
            "WHERE NOT (t)-[:APPEARED_ON]->(:DailyDigest) "
            "DETACH DELETE t"
        )
        await self.driver.execute_write(
            "MATCH (t:Topic)-[:APPEARED_ON]->(d:DailyDigest) "
            "WITH t, count(d) AS mentionCount, min(d.date) AS firstSeen, max(d.date) AS lastSeen "
            "SET t.mentionCount = mentionCount, t.firstSeen = firstSeen, t.lastSeen = lastSeen"
        )

    async def backfill_observation_views(self) -> None:
        """Project existing observations into the canonical graph views."""
        await self.driver.execute_write(
            "MATCH (o:Observation) WHERE coalesce(o.contentId, '') <> '' "
            "MERGE (c:Content {id: o.contentId}) "
            "ON CREATE SET c.title = o.title, c.firstSeen = coalesce(o.reportDate, o.date) "
            "SET c.title = coalesce(c.title, o.title), c.canonicalUrl = coalesce(c.canonicalUrl, o.url) "
            "MERGE (o)-[:OBSERVES]->(c)"
        )
        await self.driver.execute_write(
            "MATCH (o:Observation) WHERE coalesce(o.category, '') <> '' "
            "MERGE (cat:Category {id: o.category}) SET cat.name = o.category "
            "MERGE (o)-[:ABOUT]->(cat)"
        )
        await self.driver.execute_write(
            "MATCH (o:Observation) WHERE coalesce(o.source, '') <> '' "
            "MERGE (s:Source {id: o.source}) SET s.name = o.source "
            "MERGE (o)-[:FROM]->(s)"
        )
        await self.driver.execute_write(
            "MATCH (o:Observation) MERGE (d:DailyDigest {date: o.date}) "
            "MERGE (o)-[:PUBLISHED_IN]->(d)"
        )
        content_rows = await self.driver.execute_query(
            "MATCH (o:Observation) WHERE coalesce(o.contentId, '') <> '' "
            "RETURN collect(DISTINCT o.contentId) AS content_ids"
        )
        content_ids = content_rows[0].get("content_ids", []) if content_rows else []
        if content_ids:
            await self._refresh_observation_chains(content_ids)

    async def _refresh_observation_chains(self, content_ids: list[str]) -> None:
        """Rebuild deterministic chronological links for touched stable contents."""
        await self.driver.execute_write(
            "MATCH (o:Observation)-[r:PREVIOUS_OBSERVATION]->() "
            "WHERE o.contentId IN $content_ids DELETE r",
            content_ids=content_ids,
        )
        await self.driver.execute_write(
            "MATCH (c:Content) WHERE c.id IN $content_ids "
            "OPTIONAL MATCH (c)<-[:OBSERVES]-(o:Observation) "
            "WITH c, count(o) AS observation_count, "
            "min(coalesce(o.reportDate, o.date)) AS first_seen, "
            "max(coalesce(o.reportDate, o.date)) AS last_seen "
            "SET c.observationCount = observation_count, "
            "c.firstSeen = first_seen, c.lastSeen = last_seen",
            content_ids=content_ids,
        )
        await self.driver.execute_write(
            "MATCH (c:Content) WHERE c.id IN $content_ids "
            "AND NOT (c)<-[:OBSERVES]-(:Observation) DETACH DELETE c",
            content_ids=content_ids,
        )
        await self.driver.execute_write(
            "MATCH (o:Observation) WHERE o.contentId IN $content_ids "
            "WITH o ORDER BY o.contentId, coalesce(o.reportDate, o.date), o.id "
            "WITH o.contentId AS content_id, collect(o) AS observations "
            "FOREACH (i IN CASE WHEN size(observations) > 1 "
            "THEN range(1, size(observations) - 1) ELSE [] END | "
            "FOREACH (current IN [observations[i]] | "
            "FOREACH (previous IN [observations[i - 1]] | "
            "MERGE (current)-[:PREVIOUS_OBSERVATION]->(previous))))",
            content_ids=content_ids,
        )

    async def _ingest_candidate(self, candidate: dict, date_str: str) -> str:
        """Ingest a single topic candidate into the graph."""
        title = candidate.get("title", "") or candidate.get("topic", "")
        if not title:
            return ""

        occurrence_id = str(candidate.get("daily_item_id") or "").strip()
        if not occurrence_id:
            return ""

        topic_id = title.lower().strip()
        content_id = str(candidate.get("content_id") or "").strip()
        category = candidate.get("category", "")
        score = candidate.get("score", 0)
        action = candidate.get("action", "")
        source = candidate.get("source", "")
        summary = candidate.get("summary", "")
        url = candidate.get("url", "")
        reason = candidate.get("reason", "")
        evidence = candidate.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = [str(evidence)] if evidence else []
        report_date = str(candidate.get("report_date") or date_str)
        publication_date = str(candidate.get("publication_date") or "")
        publication_date_source = str(candidate.get("publication_date_source") or "unknown")
        source_updated_at = str(candidate.get("source_updated_at") or "")
        observed_at = str(candidate.get("observed_at") or date_str)
        ingested_at = str(candidate.get("ingested_at") or datetime.now(timezone.utc).isoformat())
        effective_date = str(candidate.get("effective_date") or report_date)
        effective_date_basis = str(candidate.get("effective_date_basis") or "report_date_fallback")

        await self.driver.execute_write(
            "MERGE (o:Observation {id: $occurrence_id}) "
            "SET o.contentId = $content_id, o.title = $name, o.date = $date, "
            "o.reportDate = $report_date, o.publicationDate = $publication_date, "
            "o.publicationDateSource = $publication_date_source, o.observedAt = $observed_at, "
            "o.sourceUpdatedAt = $source_updated_at, "
            "o.ingestedAt = $ingested_at, o.effectiveDate = $effective_date, "
            "o.effectiveDateBasis = $effective_date_basis, "
            "o.summary = $summary, o.url = $url, o.localUrl = $local_url, "
            "o.source = $source, o.category = $category, o.score = $score, "
            "o.action = $action, o.reason = $reason, o.evidence = $evidence",
            occurrence_id=occurrence_id,
            content_id=content_id,
            name=title,
            date=date_str,
            report_date=report_date,
            publication_date=publication_date,
            publication_date_source=publication_date_source,
            source_updated_at=source_updated_at,
            observed_at=observed_at,
            ingested_at=ingested_at,
            effective_date=effective_date,
            effective_date_basis=effective_date_basis,
            summary=summary,
            url=url,
            local_url=str(candidate.get("local_url") or ""),
            source=source,
            category=category,
            score=score,
            action=action,
            reason=reason,
            evidence=evidence,
        )

        await self.driver.execute_write(
            "MERGE (t:Topic {id: $id}) "
            "SET t.name = $name, t.category = $category, "
            "t.summary = $summary, t.url = $url, t.source = $source, "
            "t.reason = $reason, t.evidence = $evidence, "
            "t.totalScore = CASE WHEN t.totalScore IS NULL OR $score > t.totalScore "
            "THEN $score ELSE t.totalScore END, "
            "t.lastSeen = $date, "
            "t.firstSeen = COALESCE(t.firstSeen, $date)",
            id=topic_id,
            name=title,
            category=category,
            score=score,
            date=date_str,
            summary=summary,
            url=url,
            source=source,
            reason=reason,
            evidence=evidence,
        )

        if content_id:
            await self.driver.execute_write(
                "MATCH (o:Observation {id: $occurrence_id}) "
                "MERGE (c:Content {id: $content_id}) "
                "ON CREATE SET c.title = $title, c.firstSeen = $date "
                "SET c.title = $title, c.lastSeen = $date, c.canonicalUrl = $url "
                "MERGE (o)-[:OBSERVES]->(c)",
                occurrence_id=occurrence_id,
                content_id=content_id,
                title=title,
                date=date_str,
                url=url,
            )

        if category:
            await self.driver.execute_write(
                "MATCH (o:Observation {id: $occurrence_id}) "
                "MERGE (cat:Category {id: $category_id}) "
                "SET cat.name = $category_name "
                "MERGE (o)-[:ABOUT]->(cat)",
                occurrence_id=occurrence_id,
                category_id=category.strip(),
                category_name=category.strip(),
            )

        await self.driver.execute_write(
            "MATCH (o:Observation {id: $occurrence_id}) "
            "MATCH (d:DailyDigest {date: $date}) "
            "MERGE (o)-[:PUBLISHED_IN]->(d)",
            occurrence_id=occurrence_id,
            date=date_str,
        )

        await self.driver.execute_write(
            "MATCH (o:Observation {id: $occurrence_id}) "
            "MATCH (t:Topic {id: $topic_id}) "
            "MATCH (d:DailyDigest {date: $date}) "
            "MERGE (o)-[:INSTANCE_OF]->(t) "
            "MERGE (o)-[:OBSERVED_ON]->(d)",
            occurrence_id=occurrence_id,
            topic_id=topic_id,
            date=date_str,
        )

        await self.driver.execute_write(
            "MATCH (t:Topic {id: $topic_id}) "
            "MATCH (d:DailyDigest {date: $date}) "
            "MERGE (t)-[r:APPEARED_ON]->(d) "
            "ON CREATE SET t.mentionCount = COALESCE(t.mentionCount, 0) + 1 "
            "SET r.score = $score, r.action = $action, r.source = $source, r.url = $url, "
            "r.summary = $summary, r.reason = $reason, r.evidence = $evidence",
            topic_id=topic_id,
            date=date_str,
            score=score,
            action=action,
            source=source,
            url=url,
            summary=summary,
            reason=reason,
            evidence=evidence,
        )

        if source:
            await self.driver.execute_write(
                "MATCH (o:Observation {id: $occurrence_id}) "
                "MATCH (s:Source {id: $source}) "
                "MERGE (o)-[:DISCOVERED_VIA]->(s) "
                "MERGE (o)-[:FROM]->(s)",
                occurrence_id=occurrence_id, source=source,
            )

        for tag in candidate.get("tags", []):
            if not tag or len(tag) < 2:
                continue
            entity_id = tag.lower().strip()
            await self.driver.execute_write(
                "MERGE (e:Entity {id: $id}) SET e.name = $name, e.type = $entity_type",
                id=entity_id, name=tag, entity_type=_infer_entity_type(tag),
            )
            await self.driver.execute_write(
                "MATCH (e:Entity {id: $entity_id}) "
                "MATCH (o:Observation {id: $occurrence_id}) "
                "MERGE (e)-[:MENTIONS]->(o)",
                entity_id=entity_id, occurrence_id=occurrence_id,
            )
            # Keep the aggregate edge while existing GraphRAG tools migrate to
            # Observation-level traversal.
            await self.driver.execute_write(
                "MATCH (e:Entity {id: $entity_id}) "
                "MATCH (t:Topic {id: $topic_id}) "
                "MERGE (e)-[:MENTIONS]->(t)",
                entity_id=entity_id, topic_id=topic_id,
            )

        return content_id
