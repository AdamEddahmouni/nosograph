"""Adapter around ``admet.engine`` analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import ProvenanceMetadata, build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.reporting import render_report
from med_research.pipeline.results import AdmetResult


@register_module
class AdmetModule(BasePipelineModule[AdmetResult]):
    """Adapter for ADMET radar safety & toxicity profiling."""

    _COVERAGE_MODULE = "admet"

    @property
    def module_id(self) -> str:
        return "admet"

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("drugs",)

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> AdmetResult:
        from med_research.pipeline.admet.engine import analyze_admet

        return analyze_admet(
            disease_id=disease_id,
            progress_callback=opts.get("progress_callback"),
        )

    def report(
        self,
        results: AdmetResult,
        disease_id: str,
        *,
        provenance: ProvenanceMetadata | None = None,
    ) -> Path:
        output_dir = Path("dist/reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"admet_{disease_id}.html"

        prov = provenance or self.build_provenance(disease_id)

        html = render_report(
            template_name="reports/admet.html",
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
            sources=["drugs.json"],
            cache_or_live="cache",
            **extra,
        )
