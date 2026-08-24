"""Atomic activation command for Observation-first graph views."""

from __future__ import annotations

import argparse
import asyncio
import json

from rag.graphrag.builder import KnowledgeGraphBuilder
from rag.graphrag.driver import Neo4jDriver
from rag.graphrag.schema import init_schema


INVARIANT_QUERY = (
    "MATCH (o:Observation) "
    "RETURN count(o) AS observations, "
    "sum(CASE WHEN coalesce(o.contentId, '') <> '' THEN 1 ELSE 0 END) AS content_eligible, "
    "sum(CASE WHEN coalesce(o.source, '') <> '' THEN 1 ELSE 0 END) AS source_eligible, "
    "sum(CASE WHEN coalesce(o.category, '') <> '' THEN 1 ELSE 0 END) AS category_eligible, "
    "sum(CASE WHEN (o)-[:OBSERVES]->(:Content) THEN 1 ELSE 0 END) AS observes, "
    "sum(CASE WHEN (o)-[:FROM]->(:Source) THEN 1 ELSE 0 END) AS from_links, "
    "sum(CASE WHEN (o)-[:ABOUT]->(:Category) THEN 1 ELSE 0 END) AS about, "
    "sum(CASE WHEN (o)-[:PUBLISHED_IN]->(:DailyDigest) THEN 1 ELSE 0 END) AS published_in"
)

EXPECTED_CHAIN_QUERY = (
    "MATCH (o:Observation) WHERE coalesce(o.contentId, '') <> '' "
    "WITH o.contentId AS content_id, count(o) AS n "
    "RETURN sum(CASE WHEN n > 1 THEN n - 1 ELSE 0 END) AS expected_previous_links"
)

ACTUAL_CHAIN_QUERY = "MATCH ()-[r:PREVIOUS_OBSERVATION]->() RETURN count(r) AS previous_links"
ORPHAN_QUERY = (
    "MATCH (c:Content) WHERE NOT (c)<-[:OBSERVES]-(:Observation) "
    "RETURN count(c) AS orphan_contents"
)


def validate_observation_graph(stats: dict) -> list[str]:
    """Return invariant failures; an empty list means activation is safe."""
    checks = {
        "observes_mismatch": stats.get("observes") == stats.get("content_eligible"),
        "from_mismatch": stats.get("from_links") == stats.get("source_eligible"),
        "about_mismatch": stats.get("about") == stats.get("category_eligible"),
        "published_in_mismatch": stats.get("published_in") == stats.get("observations"),
        "previous_chain_mismatch": stats.get("previous_links") == stats.get("expected_previous_links"),
        "orphan_content": stats.get("orphan_contents") == 0,
    }
    return [name for name, passed in checks.items() if not passed]


async def inspect_observation_graph(driver) -> dict:
    rows = await driver.execute_query(INVARIANT_QUERY)
    expected_rows = await driver.execute_query(EXPECTED_CHAIN_QUERY)
    actual_rows = await driver.execute_query(ACTUAL_CHAIN_QUERY)
    orphan_rows = await driver.execute_query(ORPHAN_QUERY)
    stats = dict(rows[0]) if rows else {}
    stats["expected_previous_links"] = (
        expected_rows[0].get("expected_previous_links") or 0 if expected_rows else 0
    )
    stats["previous_links"] = actual_rows[0].get("previous_links", 0) if actual_rows else 0
    stats["orphan_contents"] = orphan_rows[0].get("orphan_contents", 0) if orphan_rows else 0
    stats["failures"] = validate_observation_graph(stats)
    stats["valid"] = not stats["failures"]
    return stats


async def apply_observation_graph_migration(driver) -> dict:
    """Build and validate all views in one transaction; failures roll back."""
    await init_schema(driver)

    async def migrate(transaction_driver):
        await KnowledgeGraphBuilder(transaction_driver).backfill_observation_views()
        stats = await inspect_observation_graph(transaction_driver)
        if not stats["valid"]:
            raise RuntimeError(f"Observation graph invariants failed: {stats['failures']}")
        return stats

    return await driver.execute_write_transaction(migrate)


async def _run(apply: bool) -> dict:
    driver = Neo4jDriver()
    await driver.connect()
    try:
        if apply:
            return await apply_observation_graph_migration(driver)
        return await inspect_observation_graph(driver)
    finally:
        await driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate or atomically activate Observation Graph views.")
    parser.add_argument("--apply", action="store_true", help="Apply in one transaction; default is read-only validation.")
    args = parser.parse_args()
    result = asyncio.run(_run(args.apply))
    print(json.dumps({"mode": "apply" if args.apply else "check", **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
