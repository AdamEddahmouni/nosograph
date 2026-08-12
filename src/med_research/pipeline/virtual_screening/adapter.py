"""Registry adapter for the virtual screening engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import ProvenanceMetadata, build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.results import ScreeningResult, UntargetedGenesResult


@register_module
class VirtualScreeningModule(BasePipelineModule[ScreeningResult | UntargetedGenesResult]):
    """Adapter around ``virtual_screening.screening`` scoring and reporting."""

    _COVERAGE_MODULE = "screening"

    @property
    def module_id(self) -> str:
        return "virtual_screening"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "drugs", "pathways", "screening_profile")

    def run(
        self, disease_id: str, **opts: Unpack[AdapterOptions]
    ) -> ScreeningResult | UntargetedGenesResult:
        if opts.get("operation") == "untargeted_genes":
            from med_research.pipeline.virtual_screening.screening import get_untargeted_genes

            return {"untargeted_genes": get_untargeted_genes(disease_id)}

        from med_research.pipeline.virtual_screening.screening import (
            build_compound_library,
            screen_compounds,
        )

        target_genes = opts.get("target_genes")
        if target_genes is None and opts.get("gene"):
            target_genes = [opts["gene"]]
        if not isinstance(target_genes, list):
            target_genes = []

        compound_library = opts.get("compound_library")
        if compound_library is None:
            compound_library = build_compound_library(disease_id)

        return screen_compounds(
            target_genes=target_genes,
            compound_library=compound_library,
            top_n=opts.get("top_n", opts.get("top", 15)),
            use_vina=opts.get("use_vina", False),
            disease_id=disease_id,
            progress_callback=opts.get("progress_callback"),
        )

    def report(
        self,
        results: ScreeningResult | UntargetedGenesResult,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.virtual_screening.report import generate_screening_report

        report_path = generate_screening_report(
            results,
            disease_id=disease_id,
            provenance=provenance,
        )
        return Path(report_path)

    def build_provenance(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> ProvenanceMetadata:
        scoring = opts.get("scoring")
        if scoring is None:
            from med_research.pipeline.virtual_screening.screening_strategy import (
                strategy_fingerprint,
                strategy_for_disease,
            )

            strategy = strategy_for_disease(disease_id)
            scoring = {
                "strategy_id": strategy.strategy_id,
                "strategy_fingerprint": strategy_fingerprint(strategy),
            }

        extra: dict[str, Any] = {
            key: value
            for key, value in opts.items()
            if key not in {"sources", "scoring", "cache_or_live"}
        }
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["knowledge_graph"],
            cache_or_live=opts.get("cache_or_live", "cache"),
            scoring=scoring,
            **extra,
        )
