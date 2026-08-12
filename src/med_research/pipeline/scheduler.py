"""DAG scheduler for parallel ``run-all`` pipeline execution.

Topological levels are derived from registry adapter ``depends_on`` metadata.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from med_research.exceptions import MedResearchError, PipelineExecutionError
from med_research.pipeline.registry import get_module, list_modules

logger = logging.getLogger(__name__)


def resolve_depends_on(module_id: str) -> tuple[str, ...]:
    """Return dependency module IDs declared on the registry adapter."""

    return get_module(module_id).depends_on


def topological_levels(module_ids: list[str]) -> list[list[str]]:
    """Group ``module_ids`` into dependency levels for parallel execution."""

    modules = list(dict.fromkeys(module_ids))
    module_set = set(modules)
    in_degree = dict.fromkeys(modules, 0)
    dependents: dict[str, list[str]] = {module_id: [] for module_id in modules}

    for module_id in modules:
        for dep in resolve_depends_on(module_id):
            if dep not in module_set:
                continue
            in_degree[module_id] += 1
            dependents[dep].append(module_id)

    levels: list[list[str]] = []
    ready = sorted(module_id for module_id in modules if in_degree[module_id] == 0)

    while ready:
        level = ready
        levels.append(level)
        next_ready: list[str] = []
        for module_id in level:
            for dependent in dependents[module_id]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_ready.append(dependent)
        ready = sorted(next_ready)

    scheduled = {module_id for level in levels for module_id in level}
    if scheduled != module_set:
        remaining = sorted(module_set - scheduled)
        raise ValueError(f"Cycle or unresolved dependencies for pipeline modules: {remaining}")

    return levels


def validate_dag(module_ids: list[str]) -> list[list[str]]:
    """Validate ``module_ids`` against the registry and return DAG levels."""

    registered = set(list_modules())
    unknown = sorted(set(module_ids) - registered)
    if unknown:
        raise KeyError(
            f"Unknown pipeline module(s): {', '.join(unknown)}. "
            f"Registered: {', '.join(sorted(registered))}"
        )
    return topological_levels(module_ids)


def run_levels(
    levels: list[list[str]],
    runner: Callable[[str], None],
    *,
    parallel: bool,
    max_workers: int | None = None,
) -> int:
    """Execute DAG levels with optional per-level parallelism.

    Returns the number of module runs that raised exceptions.
    """

    errors = 0
    for level in levels:
        if parallel and len(level) > 1:
            workers = max_workers or min(len(level), 8)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(runner, module_id): module_id for module_id in level}
                for future in as_completed(futures):
                    module_id = futures[future]
                    try:
                        future.result()
                    except (PipelineExecutionError, MedResearchError, RuntimeError, OSError) as exc:
                        errors += 1
                        logger.error("  %s: %s", module_id, exc)
        else:
            for module_id in level:
                try:
                    runner(module_id)
                except (PipelineExecutionError, MedResearchError, RuntimeError, OSError) as exc:
                    errors += 1
                    logger.error("  %s: %s", module_id, exc)
    return errors


async def run_levels_async(
    levels: list[list[str]],
    async_runner: Callable[[str], Any],
    *,
    parallel: bool = True,
) -> int:
    """Execute DAG levels using native asyncio concurrency.

    Returns the number of module runs that raised exceptions.
    """
    import asyncio

    errors = 0
    for level in levels:
        if parallel and len(level) > 1:
            results = await asyncio.gather(
                *(async_runner(mod_id) for mod_id in level),
                return_exceptions=True,
            )
            for module_id, res in zip(level, results):
                if isinstance(res, Exception):
                    errors += 1
                    logger.error("  %s (async): %s", module_id, res)
        else:
            for module_id in level:
                try:
                    await async_runner(module_id)
                except Exception as exc:
                    errors += 1
                    logger.error("  %s (async): %s", module_id, exc)
    return errors

