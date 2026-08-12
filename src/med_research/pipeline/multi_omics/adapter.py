"""Adapter around ``multi_omics.engine`` analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import ProvenanceMetadata, build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.reporting import render_report
from med_research.pipeline.results import MultiOmicsResult


@register_module
class MultiOmicsModule(BasePipelineModule[MultiOmicsResult]):
    """Adapter for cell-type resolution multi-omics analysis."""

    _COVERAGE_MODULE = "multi_omics"

    @property
    def module_id(self) -> str:
        return "multi_omics"

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes",)

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> MultiOmicsResult:
        from med_research.pipeline.multi_omics.engine import analyze_multi_omics

        return analyze_multi_omics(
            disease_id=disease_id,
            progress_callback=opts.get("progress_callback"),
        )

    def report(
        self,
        results: MultiOmicsResult,
        disease_id: str,
        *,
        provenance: ProvenanceMetadata | None = None,
    ) -> Path:
        output_dir = Path("dist/reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"multi_omics_{disease_id}.html"

        prov = provenance or self.build_provenance(disease_id)

        html = render_report(
            template_name="reports/multi_omics.html",
            context={
                "disease_id": disease_id,
                "results": results,
                "provenance": prov,
            },
            disease_id=disease_id,
            provenance=prov,
        )
        report_path.write_text(html, encoding="utf-8")
        return report_path

    def build_provenance(
        self, disease_id: str, **opts: Unpack[AdapterOptions]
    ) -> ProvenanceMetadata:
        extra: dict[str, Any] = {
            key: value for key, value in opts.items() if key not in {"sources", "cache_or_live"}
        }
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["genes.json"],
            cache_or_live="cache",
            **extra,
        )
