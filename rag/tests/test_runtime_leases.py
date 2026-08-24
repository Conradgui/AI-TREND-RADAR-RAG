"""Concurrency tests for draining in-flight runtime snapshots."""

import asyncio

import pytest

from rag.runtime_leases import RuntimeLeaseRegistry


@pytest.mark.asyncio
async def test_wait_for_generation_blocks_until_inflight_request_finishes():
    leases = RuntimeLeaseRegistry()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def request():
        async with leases.lease("gen-old", "hybrid"):
            entered.set()
            await release.wait()

    task = asyncio.create_task(request())
    await entered.wait()
    waiter = asyncio.create_task(leases.wait_for_generation("gen-old", timeout=1))
    await asyncio.sleep(0)
    assert not waiter.done()

    release.set()

    await task
    await waiter


@pytest.mark.asyncio
async def test_new_generation_does_not_block_old_generation_drain():
    leases = RuntimeLeaseRegistry()

    async with leases.lease("gen-new", "vector-only"):
        await leases.wait_for_generation("gen-old", timeout=0.1)


@pytest.mark.asyncio
async def test_wait_for_generation_times_out_truthfully():
    leases = RuntimeLeaseRegistry()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def request():
        async with leases.lease("gen-old", "hybrid"):
            entered.set()
            await release.wait()

    task = asyncio.create_task(request())
    await entered.wait()
    with pytest.raises(asyncio.TimeoutError):
        await leases.wait_for_generation("gen-old", timeout=0.01)

    release.set()
    await task
