"""Small async lease registry for immutable RAG runtime snapshots."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager


class RuntimeLeaseRegistry:
    """Track in-flight requests so graph mutation can wait for old Hybrid readers."""

    def __init__(self):
        self._condition = asyncio.Condition()
        self._counts: dict[tuple[str, str], int] = defaultdict(int)

    @asynccontextmanager
    async def lease(self, generation_id: str, mode: str):
        key = (str(generation_id or "legacy"), str(mode or "unknown"))
        async with self._condition:
            self._counts[key] += 1
        try:
            yield
        finally:
            async with self._condition:
                self._counts[key] -= 1
                if self._counts[key] <= 0:
                    self._counts.pop(key, None)
                self._condition.notify_all()

    async def wait_for_generation(self, generation_id: str, *, timeout: float) -> None:
        generation = str(generation_id or "legacy")

        async def wait_until_drained() -> None:
            async with self._condition:
                await self._condition.wait_for(
                    lambda: not any(
                        count > 0 and key_generation == generation
                        for (key_generation, _), count in self._counts.items()
                    )
                )

        await asyncio.wait_for(wait_until_drained(), timeout=timeout)

    async def snapshot(self) -> dict[str, int]:
        async with self._condition:
            return {
                f"{generation}:{mode}": count
                for (generation, mode), count in self._counts.items()
                if count > 0
            }
