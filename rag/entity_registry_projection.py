"""Idempotent projection of the versioned entity registry into Neo4j."""

from __future__ import annotations

import json
import math
from pathlib import Path


DEFAULT_REGISTRY_PATH = Path(__file__).with_name("entity_registry.json")
RELATION_TYPES = {"developed_by", "product_of", "owned_by", "distributed_on"}


async def project_entity_registry(driver, registry_path: Path = DEFAULT_REGISTRY_PATH) -> dict:
    """Project verified entities and relations without touching corpus data."""
    payload = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    _validate_registry(payload)

    async def write_batch(transaction):
        return await _write_registry(transaction, payload)

    return await driver.execute_write_transaction(write_batch)


async def project_entity_relation_memory(driver, memory) -> dict:
    """Project only verified learned relations and remove stale learned edges."""
    records = memory.verified_records()

    async def write_batch(transaction):
        rows = [
            {
                "relation_id": record["candidate_id"],
                "source_id": record["from_entity_id"],
                "target_id": record["to_entity_id"],
                "relation": record["relation"],
                "weight": float(record.get("weight", 0.5)),
                "updated_at": str(record.get("updated_at") or ""),
            }
            for record in records
        ]
        if rows:
            await transaction.execute_write(
                "UNWIND $relations AS item "
                "MERGE (source:Entity {id: item.source_id}) "
                "ON CREATE SET source.name = item.source_id, source.type = 'learned' "
                "MERGE (target:Entity {id: item.target_id}) "
                "ON CREATE SET target.name = item.target_id, target.type = 'learned' "
                "MERGE (source)-[r:RELATED_TO {scope: 'learned_entity_memory', "
                "relation_id: item.relation_id}]->(target) "
                "SET r.relation = item.relation, r.weight = item.weight, "
                "r.updated_at = item.updated_at",
                relations=rows,
            )
        await transaction.execute_write(
            "MATCH ()-[r:RELATED_TO {scope: 'learned_entity_memory'}]->() "
            "WHERE NOT r.relation_id IN $active_relation_ids DELETE r",
            active_relation_ids=[row["relation_id"] for row in rows],
        )
        return {
            "status": "projected",
            "scope": "learned_entity_memory",
            "relation_count": len(rows),
        }

    return await driver.execute_write_transaction(write_batch)


def _validate_registry(payload: dict) -> None:
    """Fail before the transaction rather than silently projecting a partial registry."""
    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Entity registry requires a version")
    entities = payload.get("entities")
    if not isinstance(entities, list) or not entities:
        raise ValueError("Entity registry requires entities")
    entity_ids = set()
    for entity in entities:
        entity_id = entity.get("entity_id")
        if (not isinstance(entity_id, str) or not entity_id.strip()
                or entity_id != entity_id.strip() or entity_id in entity_ids):
            raise ValueError("Entity IDs must be nonempty and unique")
        entity_ids.add(entity_id)
    for relation in payload.get("relations", []):
        if relation.get("status") != "verified":
            continue
        if relation.get("from") not in entity_ids or relation.get("to") not in entity_ids:
            raise ValueError("Relation endpoint is not registered")
        if relation.get("relation") not in RELATION_TYPES:
            raise ValueError("Unsupported registry relationship")
        weight = relation.get("weight")
        if (isinstance(weight, bool) or not isinstance(weight, (int, float))
                or not math.isfinite(weight) or not 0 < weight < 1):
            raise ValueError("Relation weight must be finite and between zero and one")


async def _write_registry(driver, payload: dict) -> dict:
    version = payload["version"]
    entities = payload["entities"]
    relations = [
        relation for relation in (payload.get("relations") or [])
        if relation.get("status") == "verified"
    ]
    entity_rows = [
        {
            "entity_id": entity["entity_id"],
            "display_name": next(
                (str(alias).strip() for alias in entity.get("aliases", []) if str(alias).strip()),
                entity["entity_id"],
            ),
            "entity_type": str(entity.get("entity_type") or "unknown"),
        }
        for entity in entities
    ]
    await driver.execute_write(
        "UNWIND $entities AS item "
        "MERGE (e:Entity {id: item.entity_id}) "
        "ON CREATE SET e.name = item.display_name, e.type = item.entity_type, "
        "e.registry_version = $registry_version",
        entities=entity_rows,
        registry_version=version,
    )
    relation_rows = [
        {"source_id": item["from"], "target_id": item["to"],
         "relation": item["relation"], "weight": item["weight"]}
        for item in relations
    ]
    if relation_rows:
        await driver.execute_write(
            "UNWIND $relations AS item "
            "MATCH (source:Entity {id: item.source_id}) "
            "MATCH (target:Entity {id: item.target_id}) "
            "MERGE (source)-[r:RELATED_TO {relation: item.relation, "
            "scope: 'entity_registry', registry_version: $registry_version}]->(target) "
            "ON CREATE SET r.weight = item.weight",
            relations=relation_rows,
            registry_version=version,
        )
    return {
        "status": "projected",
        "registry_version": version,
        "entity_count": len(entities),
        "relation_count": len(relations),
    }
