"""Registry adapter for cross-disease repurposing analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import ProvenanceMetadata, build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.results import ComparativeModulesResult, CrossDiseaseResult


@register_module
class CrossDiseaseModule(BasePipelineModule[CrossDiseaseResult | ComparativeModulesResult]):
    """Adapter around ``cross_disease.analyzer`` scoring and reporting."""

    _COVERAGE_MODULE = "cross_disease"

    @property
    def module_id(self) -> str:
        return "cross_disease"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ()

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "drugs", "pathways")

    def run(
        self, disease_id: str, **opts: Unpack[AdapterOptions]
    ) -> CrossDiseaseResult | ComparativeModulesResult:
        if opts.get("comparative"):
            from med_research.pipeline.cross_disease.analyzer import (
                compute_comparative_modules,
            )

            return cast(
                ComparativeModulesResult,
                compute_comparative_modules(
                    progress_callback=opts.get("progress_callback"),
                    top_synergy=opts.get("top_synergy", 5),
                ),
            )

        from med_research.pipeline.cross_disease.analyzer import (
            compute_cross_disease_analysis,
        )

        return cast(
            CrossDiseaseResult,
            compute_cross_disease_analysis(
                progress_callback=opts.get("progress_callback"),
            ),
        )

    def report(
        self,
        results: CrossDiseaseResult | ComparativeModulesResult,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.cross_disease.report import generate_html_report

        report_path = generate_html_report(cast(dict, results), provenance=provenance)
        return Path(report_path)

    def build_provenance(
        self, disease_id: str, **opts: Unpack[AdapterOptions]
    ) -> ProvenanceMetadata:
        extra: dict[str, Any] = {
            key: value
            for key, value in opts.items()
            if key not in {"sources", "cache_or_live", "scoring"}
        }
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["knowledge_graph"],
            cache_or_live="cache",
            scoring={"ranking": "composite_score"},
            **extra,
        )
