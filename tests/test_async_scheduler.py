"""Unit tests for native asyncio scheduler execution."""

from __future__ import annotations

import asyncio

import pytest

from med_research.pipeline.scheduler import run_levels_async, topological_levels


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_levels_async_success() -> None:
    executed = []

    async def mock_runner(module_id: str) -> None:
        await asyncio.sleep(0.01)
        executed.append(module_id)

    levels = topological_levels(["gwas", "enrichment", "ppi"])
    errors = await run_levels_async(levels, mock_runner, parallel=True)

    assert errors == 0
    assert set(executed) == {"gwas", "enrichment", "ppi"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_levels_async_handles_exception() -> None:
    async def mock_runner(module_id: str) -> None:
        if module_id == "enrichment":
            raise ValueError("Simulation failure")

    levels = topological_levels(["gwas", "enrichment"])
    errors = await run_levels_async(levels, mock_runner, parallel=True)

    assert errors == 1
