"""Registry adapter for drug synergy scoring and reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import ProvenanceMetadata, build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.results import SynergyResults


@register_module
class DrugSynergyModule(BasePipelineModule[SynergyResults]):
    """Adapter around ``drug_synergy.engine`` scoring and reporting."""

    _COVERAGE_MODULE = "synergy"

    @property
    def module_id(self) -> str:
        return "drug_synergy"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "drugs")

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> SynergyResults:
        from med_research.pipeline.drug_synergy.engine import compute_synergy

        return compute_synergy(
            progress_callback=opts.get("progress_callback"),
            disease_id=disease_id,
            save=opts.get("save", True),
        )

    def report(
        self,
        results: SynergyResults,
        disease_id: str,
        *,
        provenance: dict[str, Any] | None = None,
    ) -> Path:
        from med_research.pipeline.drug_synergy.report import generate_html_report

        report_path = generate_html_report(
            results,
            disease_id=disease_id,
            provenance=provenance,
        )
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
