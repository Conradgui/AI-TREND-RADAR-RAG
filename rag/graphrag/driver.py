"""Neo4j async driver wrapper."""

from __future__ import annotations

from neo4j import AsyncGraphDatabase, AsyncDriver

from rag.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# G-5 修复：默认查询超时（秒），防止慢查询阻塞整个 pipeline
DEFAULT_QUERY_TIMEOUT_S = 30


class Neo4jDriver:
    """Thin wrapper around Neo4j async driver with lifecycle management."""

    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        self._driver: AsyncDriver | None = None
        self._uri = uri
        self._auth = (user, password)

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(self._uri, auth=self._auth)
        await self._driver.verify_connectivity()

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None

    @property
    def driver(self) -> AsyncDriver:
        if not self._driver:
            raise RuntimeError("Driver not connected. Call connect() first.")
        return self._driver

    async def execute_query(self, cypher: str, timeout: float = DEFAULT_QUERY_TIMEOUT_S, **params):
        """执行只读 Cypher 查询，带超时保护。
        G-5 修复：通过 tx.run(timeout=...) 设置单次查询超时，
        防止慢查询或全表扫描阻塞 pipeline。
        """
        async with self.driver.session() as session:
            async def run_read(tx):
                result = await tx.run(cypher, parameters=params, timeout=timeout)
                return [record.data() async for record in result]

            return await session.execute_read(run_read)

    async def execute_write(self, cypher: str, timeout: float = DEFAULT_QUERY_TIMEOUT_S, **params):
        """执行写入 Cypher 查询，带超时保护。
        G-5 修复：同 execute_query，在 transaction 级别设置 timeout。
        """
        async with self.driver.session() as session:
            async def run_write(tx):
                result = await tx.run(cypher, parameters=params, timeout=timeout)
                await result.consume()

            await session.execute_write(run_write)

    async def execute_write_transaction(self, work):
        """Run a multi-statement async callback in one Neo4j transaction."""
        async with self.driver.session() as session:
            async def run_write(tx):
                return await work(_TransactionDriver(tx))

            return await session.execute_write(run_write)


class _TransactionDriver:
    """KnowledgeGraphBuilder-compatible writer bound to one open transaction."""

    def __init__(self, transaction):
        self._transaction = transaction

    async def execute_write(self, cypher: str, timeout: float = DEFAULT_QUERY_TIMEOUT_S, **params):
        result = await self._transaction.run(cypher, parameters=params, timeout=timeout)
        await result.consume()

    async def execute_query(self, cypher: str, timeout: float = DEFAULT_QUERY_TIMEOUT_S, **params):
        """Read through the same open transaction used by the date rebuild."""
        result = await self._transaction.run(cypher, parameters=params, timeout=timeout)
        return [record.data() async for record in result]
