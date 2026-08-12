"""Typed facade for all registry-backed pipeline operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from med_research.diseases.coverage import ModuleCoverage
from med_research.pipeline.provenance import ProvenanceMetadata
from med_research.pipeline.base import PipelineRunResult
from med_research.pipeline.dispatch import LegacyProgress, StandardProgress


class PipelineGateway:
    """Single typed entry point for pipeline execution and report boundaries.

    The gateway deliberately delegates the implementation to
    :mod:`med_research.pipeline.dispatch`. This keeps registry lookup, coverage
    gating, provenance generation, result validation, progress wiring, and
    report rendering in one runtime boundary while giving CLI, web, and Celery
    callers one stable API.
    """

    def execute(
        self,
        module_id: str,
        disease_id: str,
        *,
        export_html: bool = False,
        progress_callback: LegacyProgress | StandardProgress | None = None,
        **opts: Any,
    ) -> PipelineRunResult[Any]:
        """Execute a registered module through the unified dispatch path."""
        from med_research.pipeline.dispatch import execute_module

        return execute_module(
            module_id,
            disease_id,
            export_html=export_html,
            progress_callback=progress_callback,
            **opts,
        )

    def catalog(self) -> list[dict[str, Any]]:
        """Return the registry-generated catalog for system/API consumers."""
        from med_research.pipeline.registry import module_catalog

        return module_catalog()

    def coverage(self, module_id: str, disease_id: str) -> ModuleCoverage:
        """Return coverage metadata for a registered module and disease."""
        from med_research.pipeline.dispatch import module_coverage_for

        return module_coverage_for(module_id, disease_id)

    def provenance(
        self,
        module_id: str,
        disease_id: str,
        **opts: Any,
    ) -> ProvenanceMetadata:
        """Build provenance through the centralized registry boundary."""
        from med_research.pipeline.dispatch import build_module_provenance

        return build_module_provenance(module_id, disease_id, **opts)

    def report(
        self,
        module_id: str,
        results: Any,
        disease_id: str,
        **provenance_opts: Any,
    ) -> Path:
        """Render a precomputed result through the centralized report path."""
        from med_research.pipeline.dispatch import render_module_report

        return render_module_report(
            module_id,
            results,
            disease_id,
            **provenance_opts,
        )


pipeline_gateway = PipelineGateway()

__all__ = ["PipelineGateway", "pipeline_gateway"]
