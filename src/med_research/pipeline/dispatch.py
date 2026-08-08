"""Unified pipeline dispatch for CLI, web, and Celery entry points.

``execute_module()`` is the single runtime primitive: coverage gate, registry
lookup, optional progress bridging, run, and optional provenance-aware report.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

from med_research.diseases.coverage import ModuleCoverage, module_coverage
from med_research.exceptions import (
    ConfigurationError,
    DataValidationError,
    ExternalAPIError,
    ModuleNotAvailableError,
)
from med_research.pipeline.base import PipelineRunResult
from med_research.pipeline.registry import get_module

# Standard: step label, units completed, total units.
StandardProgress = Callable[[str, int, int], None]
# Legacy: percent 0-100, human-readable message (Celery / WebSocket).
LegacyProgress = Callable[[int, str], None]


def standard_to_legacy(
    step: str,
    current: int,
    total: int,
    sink: LegacyProgress | None,
) -> None:
    """Convert a standard progress tick to legacy percent/message."""
    if sink is None:
        return
    if total <= 0:
        percent = 100 if current > 0 else 0
    else:
        percent = min(100, max(0, int(current / total * 100)))
    sink(percent, step)


class ProgressReporter:
    """Standard ``(step, current, total)`` callback backed by a legacy sink."""

    def __init__(self, sink: LegacyProgress | None = None) -> None:
        self._sink = sink

    def __call__(self, step: str, current: int, total: int) -> None:
        standard_to_legacy(step, current, total, self._sink)

    def legacy(self) -> LegacyProgress:
        """Return the underlying legacy callback for engines that expect it."""
        return self._sink or (lambda _p, _m: None)


def _accepts_legacy(callback: LegacyProgress | StandardProgress) -> bool:
    """Heuristic: legacy callbacks are typed for two positional args."""
    try:
        sig = inspect.signature(callback)
        params = [
            p
            for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        return len(params) == 2
    except (TypeError, ValueError):
        return True


def _coverage_module_name(module: Any) -> str:
    """Resolve the coverage bucket name for an adapter instance."""
    bucket = getattr(module, "_COVERAGE_MODULE", None)
    if isinstance(bucket, str):
        return bucket
    return str(module.module_id)


def _blocked_error_message(module_id: str, coverage: ModuleCoverage) -> str:
    """Build a human-readable blocked message with ModuleNotAvailableError semantics."""
    if coverage.limitations:
        detail = coverage.limitations[0]
    elif coverage.missing_inputs:
        detail = (
            f"Required curated inputs are missing: {', '.join(coverage.missing_inputs)}."
        )
    else:
        detail = f"Module '{module_id}' is not available for disease '{coverage.disease_id}'."
    return str(ModuleNotAvailableError(detail))


# Run-time options that should not be forwarded to ``build_provenance``.
_RUNTIME_OPTS = frozenset({
    "use_cache",
    "progress_callback",
    "top",
    "save",
    "graph",
    "llm_client",
    "model",
    "request",
    "operation",
    "untargeted_only",
    "gene_id",
    "comparative",
    "skip_ppi",
    "max_studies",
    "max_results",
    "max_per_query",
    "signature",
    "signature_source",
    "tissue",
})


def _wire_progress_callback(
    progress_callback: LegacyProgress | StandardProgress | None,
    opts: dict[str, Any],
) -> None:
    """Bridge legacy or standard progress callbacks into engine opts."""
    if progress_callback is None:
        return
    if _accepts_legacy(progress_callback):
        legacy_cb: LegacyProgress = progress_callback  # type: ignore[assignment]
        opts["progress_callback"] = (
            lambda step, current, total: standard_to_legacy(
                step, current, total, legacy_cb
            )
        )
    else:
        opts["progress_callback"] = progress_callback


def execute_module(
    module_id: str,
    disease_id: str,
    *,
    export_html: bool = False,
    progress_callback: LegacyProgress | StandardProgress | None = None,
    **opts: Any,
) -> PipelineRunResult:
    """Run a registry module with coverage gating and optional HTML export."""
    try:
        module = get_module(module_id)
    except KeyError as exc:
        return PipelineRunResult(
            success=False,
            data=None,
            errors=[str(ModuleNotAvailableError(str(exc)))],
        )

    coverage = module_coverage(
        disease_id,
        _coverage_module_name(module),
        module.coverage_inputs(),
    )
    if not coverage.is_runnable:
        return PipelineRunResult(
            success=False,
            data=None,
            errors=[_blocked_error_message(module_id, coverage)],
        )

    run_opts = dict(opts)
    _wire_progress_callback(progress_callback, run_opts)

    try:
        data = module.run(disease_id, **run_opts)
    except ModuleNotAvailableError as exc:
        return PipelineRunResult(success=False, data=None, errors=[str(exc)])
    except (ExternalAPIError, DataValidationError, ConfigurationError) as exc:
        return PipelineRunResult(success=False, data=None, errors=[str(exc)])

    report_path: Path | None = None
    provenance: dict[str, Any] | None = None
    if export_html:
        provenance_opts = {
            key: value for key, value in opts.items() if key not in _RUNTIME_OPTS
        }
        provenance = module.build_provenance(disease_id, **provenance_opts)
        report_path = module.report(data, disease_id, provenance=provenance)

    return PipelineRunResult(
        success=True,
        data=data,
        report_path=report_path,
        provenance=provenance,
    )
