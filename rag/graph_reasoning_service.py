"""Service helpers for graph-derived relationship evidence."""

from __future__ import annotations

from datetime import datetime, timezone

from rag.graph_question_planning import GraphQuestionPlan


async def build_graph_reasoning_evidence(driver, plan: GraphQuestionPlan) -> dict:
    """Query Neo4j for entity/topic/date/source relationship evidence."""
    rows = await driver.execute_query(
        "MATCH (e:Entity {id: $entity_id})-[:MENTIONS]->(t:Topic) "
        "OPTIONAL MATCH (t)-[:APPEARED_ON]->(d:DailyDigest) "
        "OPTIONAL MATCH (t)-[:DISCOVERED_VIA]->(s:Source) "
        "RETURN e.name AS entity, "
        "count(DISTINCT t) AS topic_count, "
        "count(DISTINCT d.date) AS date_count, "
        "count(DISTINCT s.id) AS source_count, "
        "collect(DISTINCT {entity: e.name, topic: t.name, date: d.date, source: s.id})[0..8] AS sample_paths",
        entity_id=plan.entity_id,
    )
    row = rows[0] if rows else {}
    sample_paths = [
        path for path in row.get("sample_paths", [])
        if path.get("topic") and path.get("date")
    ]
    return {
        "entity_id": plan.entity_id,
        "entity_label": plan.entity_label,
        "entity": row.get("entity") or plan.entity_label,
        "topic_count": row.get("topic_count", 0),
        "date_count": row.get("date_count", 0),
        "source_count": row.get("source_count", 0),
        "sample_paths": sample_paths,
        "required_paths": plan.required_paths,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_graph_reasoning_citation(evidence: dict) -> dict:
    """Build one internal citation that exposes graph relationship evidence."""
    latest_date = _latest_date(evidence.get("sample_paths", []))
    return {
        "evidence_type": "internal",
        "content_type": "graph_reasoning",
        "date": latest_date,
        "source": "Neo4j graph",
        "title": f"{evidence.get('entity_label', '')} graph relationship evidence",
        "citation_id": f"graph-reasoning/{evidence.get('entity_id', '')}",
        "excerpt": format_graph_reasoning_summary(evidence),
    }


def format_graph_reasoning_summary(evidence: dict) -> str:
    """Format graph evidence as a concise Chinese summary."""
    paths = evidence.get("sample_paths", [])
    examples = []
    for path in paths[:3]:
        examples.append(
            f"{path.get('topic', '')} / {path.get('date', '')} / {path.get('source') or 'unknown source'}"
        )
    examples_text = "；".join(examples) if examples else "暂无样例路径"
    return (
        f"{evidence.get('entity_label', evidence.get('entity_id', ''))} 在图谱中关联 "
        f"{evidence.get('topic_count', 0)} 个主题、"
        f"{evidence.get('date_count', 0)} 个日期、"
        f"{evidence.get('source_count', 0)} 个来源。"
        f"样例路径：{examples_text}。"
    )


def _latest_date(paths: list[dict]) -> str:
    dates = sorted(str(path.get("date", "")) for path in paths if path.get("date"))
    return dates[-1] if dates else ""
