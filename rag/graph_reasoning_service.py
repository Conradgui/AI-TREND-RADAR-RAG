"""Service helpers for graph-derived relationship evidence."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from rag.graph_question_planning import GraphQuestionPlan


async def build_graph_reasoning_evidence(driver, plan: GraphQuestionPlan) -> dict:
    """Query Neo4j for observation-first relationship evidence."""
    rows_task = driver.execute_query(
        "MATCH (e:Entity {id: $entity_id})-[:MENTIONS]->(o:Observation) "
        "OPTIONAL MATCH (o)-[:OBSERVES]->(c:Content) "
        "OPTIONAL MATCH (o)-[:DISCOVERED_VIA|FROM]->(s:Source) "
        "OPTIONAL MATCH (o)-[:ABOUT]->(cat:Category) "
        "OPTIONAL MATCH (e)-[registry:RELATED_TO]->(related:Entity) "
        "WHERE registry.scope IN ['entity_registry', 'learned_entity_memory'] "
        "RETURN e.name AS entity, "
        "count(DISTINCT o) AS observation_count, "
        "count(DISTINCT coalesce(c.id, o.contentId)) AS content_count, "
        "count(DISTINCT o.date) AS date_count, "
        "min(o.date) AS first_observed_date, "
        "max(o.date) AS latest_observed_date, "
        "count(DISTINCT s.id) AS source_count, "
        "count(DISTINCT coalesce(cat.id, o.category)) AS category_count, "
        "collect(DISTINCT {entity_id: related.id, entity: related.name, "
        "relation: registry.relation, weight: registry.weight, "
        "registry_version: registry.registry_version, scope: registry.scope}) AS registry_relations, "
        "collect(DISTINCT {entity: e.name, title: o.title, "
        "content_id: coalesce(c.id, o.contentId), date: o.date, "
        "source: coalesce(s.id, o.source), category: coalesce(cat.name, o.category)})[0..8] AS sample_paths",
        entity_id=plan.entity_id,
    )
    repeat_rows_task = driver.execute_query(
        "MATCH (e:Entity {id: $entity_id})-[:MENTIONS]->(o:Observation) "
        "WHERE coalesce(o.contentId, '') <> '' "
        "WITH o.contentId AS content_id, count(DISTINCT o) AS observation_count "
        "WHERE observation_count > 1 "
        "RETURN count(*) AS repeated_content_count, "
        "sum(observation_count) AS repeated_observation_count",
        entity_id=plan.entity_id,
    )
    chain_rows_task = driver.execute_query(
        "MATCH (e:Entity {id: $entity_id})-[:MENTIONS]->(o:Observation) "
        "MATCH (o)-[r:PREVIOUS_OBSERVATION]->(previous:Observation) "
        "RETURN count(DISTINCT r) AS previous_link_count",
        entity_id=plan.entity_id,
    )
    rows, repeat_rows, chain_rows = await asyncio.gather(
        rows_task,
        repeat_rows_task,
        chain_rows_task,
    )
    row = rows[0] if rows else {}
    sample_paths = [
        path for path in row.get("sample_paths", [])
        if path.get("title") and path.get("date")
    ]
    registry_relations = [
        relation for relation in row.get("registry_relations", [])
        if relation.get("entity_id") and relation.get("relation")
    ]
    content_count = row.get("content_count", 0)
    repeat_row = repeat_rows[0] if repeat_rows else {}
    chain_row = chain_rows[0] if chain_rows else {}
    return {
        "entity_id": plan.entity_id,
        "entity_label": plan.entity_label,
        "entity": row.get("entity") or plan.entity_label,
        "observation_count": row.get("observation_count", 0),
        "content_count": content_count,
        "date_count": row.get("date_count", 0),
        "first_observed_date": row.get("first_observed_date", ""),
        "latest_observed_date": row.get("latest_observed_date", ""),
        "source_count": row.get("source_count", 0),
        "category_count": row.get("category_count", 0),
        "repeated_content_count": repeat_row.get("repeated_content_count", 0),
        "repeated_observation_count": repeat_row.get("repeated_observation_count", 0),
        "previous_link_count": chain_row.get("previous_link_count", 0),
        "sample_paths": sample_paths,
        "registry_relations": registry_relations,
        "required_paths": plan.required_paths,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def build_entity_relation_evidence(
    driver,
    left_plan: GraphQuestionPlan,
    right_plan: GraphQuestionPlan,
) -> dict:
    """Query typed, pairwise graph facts for two entities.

    Shared observations, contents and categories are kept separate because
    they express different strengths of association. None implies causality.
    """
    params = {
        "left_entity_id": left_plan.entity_id,
        "right_entity_id": right_plan.entity_id,
    }
    observation_rows_task = driver.execute_query(
        "MATCH (left:Entity {id: $left_entity_id})-[:MENTIONS]->(o:Observation) "
        "MATCH (right:Entity {id: $right_entity_id})-[:MENTIONS]->(o) "
        "OPTIONAL MATCH (o)-[:OBSERVES]->(c:Content) "
        "RETURN count(DISTINCT o) AS shared_observation_count, "
        "collect(DISTINCT {title: o.title, date: o.date, "
        "content_id: coalesce(c.id, o.contentId)})[0..8] AS sample_shared_observations",
        **params,
    )
    content_rows_task = driver.execute_query(
        "MATCH (left:Entity {id: $left_entity_id})-[:MENTIONS]->(lo:Observation)-[:OBSERVES]->(c:Content) "
        "MATCH (right:Entity {id: $right_entity_id})-[:MENTIONS]->(ro:Observation)-[:OBSERVES]->(c) "
        "RETURN count(DISTINCT c) AS shared_content_count",
        **params,
    )
    category_rows_task = driver.execute_query(
        "MATCH (left:Entity {id: $left_entity_id})-[:MENTIONS]->(lo:Observation)-[:ABOUT]->(cat:Category) "
        "MATCH (right:Entity {id: $right_entity_id})-[:MENTIONS]->(ro:Observation)-[:ABOUT]->(cat) "
        "RETURN count(DISTINCT cat) AS shared_category_count, "
        "collect(DISTINCT cat.name)[0..8] AS shared_categories",
        **params,
    )
    observation_rows, content_rows, category_rows = await asyncio.gather(
        observation_rows_task,
        content_rows_task,
        category_rows_task,
    )
    observation_row = observation_rows[0] if observation_rows else {}
    content_row = content_rows[0] if content_rows else {}
    category_row = category_rows[0] if category_rows else {}
    sample_observations = [
        row for row in observation_row.get("sample_shared_observations", [])
        if row.get("title") and row.get("date")
    ]
    return {
        "entity_ids": [left_plan.entity_id, right_plan.entity_id],
        "entity_labels": [left_plan.entity_label, right_plan.entity_label],
        "shared_observation_count": observation_row.get("shared_observation_count", 0),
        "shared_content_count": content_row.get("shared_content_count", 0),
        "shared_category_count": category_row.get("shared_category_count", 0),
        "shared_categories": [
            item for item in category_row.get("shared_categories", []) if item
        ],
        "sample_shared_observations": sample_observations,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_entity_relation_citation(evidence: dict) -> dict:
    """Expose pairwise graph facts as one auditable relation citation."""
    entity_ids = evidence.get("entity_ids", ["", ""])
    labels = evidence.get("entity_labels", entity_ids)
    return {
        "evidence_type": "internal",
        "content_type": "graph_relation",
        "date": _latest_date(evidence.get("sample_shared_observations", [])),
        "source": "Neo4j graph",
        "title": f"{labels[0]} 与 {labels[1]} 的图谱关联证据",
        "citation_id": f"graph-relation/{entity_ids[0]}/{entity_ids[1]}",
        "excerpt": format_entity_relation_summary(evidence),
    }


def format_entity_relation_summary(evidence: dict) -> str:
    """Describe pairwise graph facts without upgrading association to causality."""
    labels = evidence.get("entity_labels", evidence.get("entity_ids", ["", ""]))
    categories = "、".join(evidence.get("shared_categories", [])[:5]) or "无"
    examples = "；".join(
        f"{row.get('title')} / {row.get('date')}"
        for row in evidence.get("sample_shared_observations", [])[:3]
    ) or "无"
    return (
        f"{labels[0]} 与 {labels[1]} 在图谱中有 "
        f"{evidence.get('shared_observation_count', 0)} 条直接共现观察、"
        f"{evidence.get('shared_content_count', 0)} 个共享稳定内容、"
        f"{evidence.get('shared_category_count', 0)} 个共享分类。"
        f"共享分类：{categories}；共现样例：{examples}。"
        "这些路径只能证明图谱中的共现或共享上下文，不能单独证明因果。"
    )


def build_graph_reasoning_citation(evidence: dict) -> dict:
    """Build one internal citation that exposes graph relationship evidence."""
    latest_date = evidence.get("latest_observed_date") or _latest_date(evidence.get("sample_paths", []))
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
            f"{path.get('title', '')} / {path.get('date', '')} / {path.get('source') or 'unknown source'}"
        )
    examples_text = "；".join(examples) if examples else "暂无样例路径"
    registry_text = "；".join(
        f"{item.get('relation')} → {item.get('entity')}（权重 {item.get('weight')}）"
        for item in evidence.get("registry_relations", [])[:5]
    ) or "无"
    return (
        f"{evidence.get('entity_label', evidence.get('entity_id', ''))} 在图谱中关联 "
        f"{evidence.get('content_count', 0)} 个稳定内容、"
        f"{evidence.get('observation_count', 0)} 条每日观察、"
        f"{evidence.get('date_count', 0)} 个日期、"
        f"{evidence.get('source_count', 0)} 个来源、"
        f"{evidence.get('category_count', 0)} 个分类。"
        f"在带有该实体标记的观察中，{evidence.get('repeated_content_count', 0)} 个内容跨日重复出现，"
        f"涉及 {evidence.get('repeated_observation_count', 0)} 条观察和 "
        f"{evidence.get('previous_link_count', 0)} 条相邻时间链。"
        f"样例路径：{examples_text}。注册表主体关系：{registry_text}。"
    )


def _latest_date(paths: list[dict]) -> str:
    dates = sorted(str(path.get("date", "")) for path in paths if path.get("date"))
    return dates[-1] if dates else ""
