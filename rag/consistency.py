"""Data consistency verification between Neo4j graph and ChromaDB vector store.

问题G-4修复：提供图数据与向量数据的一致性校验机制。
- ingest_consistency_check: 在 ingestion 流程后验证两者数据量是否一致
- get_consistency_report: 用于 /health 端点报告数据差异
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rag.graphrag.driver import Neo4jDriver
    from rag.retriever.vector_store import VectorStore

logger = logging.getLogger(__name__)

# 一致性阈值：允许的最大差异百分比（向量数 vs 图节点数）
# 由于 ChromaDB 存储的是 chunk 级别（文档分块），而 Neo4j 存储的是 topic/document 级别，
# 两者数量天然不等。这里比较的是"日期覆盖"而非绝对数量。
CONSISTENCY_THRESHOLD_PERCENT = 20


@dataclass(frozen=True)
class ConsistencyReport:
    """不可变的一致性校验报告。"""
    neo4j_dates: list[str]
    chroma_dates: list[str]
    neo4j_date_count: int
    chroma_date_count: int
    missing_in_chroma: list[str]  # 在 Neo4j 中有但 ChromaDB 中缺失的日期
    missing_in_neo4j: list[str]   # 在 ChromaDB 中有但 Neo4j 中缺失的日期
    is_consistent: bool
    checked_at: str

    def to_dict(self) -> dict:
        return {
            "neo4j_date_count": self.neo4j_date_count,
            "chroma_date_count": self.chroma_date_count,
            "missing_in_chroma": self.missing_in_chroma,
            "missing_in_neo4j": self.missing_in_neo4j,
            "is_consistent": self.is_consistent,
            "checked_at": self.checked_at,
        }


async def get_neo4j_dates(driver: "Neo4jDriver") -> list[str]:
    """从 Neo4j 获取所有已 ingest 的日期列表。"""
    try:
        rows = await driver.execute_query(
            "MATCH (d:DailyDigest) RETURN d.date AS date ORDER BY d.date"
        )
        return [r["date"] for r in rows]
    except Exception as e:
        logger.error("Failed to query Neo4j dates: %s", e)
        return []


def get_chroma_dates(vector_store: "VectorStore") -> list[str]:
    """从 ChromaDB 获取所有已 ingest 的日期列表。

    注意：ChromaDB 没有原生的 distinct values 查询，
    所以通过 get_all 获取所有 metadata 再提取 date 字段。
    """
    try:
        # 使用 where 过滤获取所有有 date 字段的记录
        # ChromaDB 的 get 方法支持 include 参数控制返回内容
        results = vector_store.collection.get(
            include=["metadatas"],
        )
        if not results or not results.get("metadatas"):
            return []
        dates = set()
        for meta in results["metadatas"]:
            if meta and meta.get("date"):
                dates.add(meta["date"])
        return sorted(dates)
    except Exception as e:
        logger.error("Failed to query ChromaDB dates: %s", e)
        return []


async def check_consistency(
    driver: "Neo4jDriver",
    vector_store: "VectorStore",
) -> ConsistencyReport:
    """校验 Neo4j 与 ChromaDB 的数据一致性。

    校验逻辑：
    1. 分别从两边获取已 ingest 的日期集合
    2. 计算差集，找出不一致的日期
    3. 根据差集大小判断是否一致
    """
    neo4j_dates = await get_neo4j_dates(driver)
    chroma_dates = get_chroma_dates(vector_store)

    neo4j_set = set(neo4j_dates)
    chroma_set = set(chroma_dates)

    missing_in_chroma = sorted(neo4j_set - chroma_set)
    missing_in_neo4j = sorted(chroma_set - neo4j_set)

    # 判断一致性：只要任一方向有缺失日期，就标记为不一致
    is_consistent = len(missing_in_chroma) == 0 and len(missing_in_neo4j) == 0

    report = ConsistencyReport(
        neo4j_dates=neo4j_dates,
        chroma_dates=chroma_dates,
        neo4j_date_count=len(neo4j_dates),
        chroma_date_count=len(chroma_dates),
        missing_in_chroma=missing_in_chroma,
        missing_in_neo4j=missing_in_neo4j,
        is_consistent=is_consistent,
        checked_at=datetime.now().isoformat(),
    )

    if not is_consistent:
        logger.warning(
            "Data consistency issue detected: "
            "missing_in_chroma=%s, missing_in_neo4j=%s",
            missing_in_chroma, missing_in_neo4j,
        )

    return report


async def post_ingestion_verify(
    driver: "Neo4jDriver",
    vector_store: "VectorStore",
    ingested_dates: list[str],
) -> ConsistencyReport:
    """Ingestion 后的快速校验：只检查本次 ingest 的日期是否在两边都存在。"""
    neo4j_dates = await get_neo4j_dates(driver)
    chroma_dates = get_chroma_dates(vector_store)

    neo4j_set = set(neo4j_dates)
    chroma_set = set(chroma_dates)
    ingested_set = set(ingested_dates)

    # 只检查本次 ingest 的日期
    missing_in_chroma = sorted(ingested_set - chroma_set)
    missing_in_neo4j = sorted(ingested_set - neo4j_set)

    is_consistent = len(missing_in_chroma) == 0 and len(missing_in_neo4j) == 0

    report = ConsistencyReport(
        neo4j_dates=neo4j_dates,
        chroma_dates=chroma_dates,
        neo4j_date_count=len(neo4j_dates),
        chroma_date_count=len(chroma_dates),
        missing_in_chroma=missing_in_chroma,
        missing_in_neo4j=missing_in_neo4j,
        is_consistent=is_consistent,
        checked_at=datetime.now().isoformat(),
    )

    if is_consistent:
        logger.info("Post-ingestion consistency check passed for %d dates", len(ingested_dates))
    else:
        logger.warning(
            "Post-ingestion consistency check FAILED: "
            "missing_in_chroma=%s, missing_in_neo4j=%s",
            missing_in_chroma, missing_in_neo4j,
        )

    return report
