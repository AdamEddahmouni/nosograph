"""Registry adapter for gene expression correlation analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.results import ExpressionResults


@register_module
class GeneExpressionModule(BasePipelineModule[ExpressionResults]):
    """Adapter around ``gene_expression.correlator`` scoring and reporting."""

    _COVERAGE_MODULE = "expression"

    @property
    def module_id(self) -> str:
        return "gene_expression"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "drugs")

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> ExpressionResults:
        from med_research.pipeline.gene_expression.correlator import (
            compute_all_correlations,
        )

        return compute_all_correlations(
            progress_callback=opts.get("progress_callback"),
            signature=opts.get("signature"),
            signature_source=opts.get("signature_source", "auto"),
            tissue=opts.get("tissue"),
            disease_id=disease_id,
            save=opts.get("save", True),
        )

    def report(
        self,
        results: ExpressionResults,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.gene_expression.correlator import (
            _normalize_signature,
        )
        from med_research.pipeline.gene_expression.report import generate_html_report

        _, _, sig_source, num_studies = _normalize_signature(None, disease_id)
        report_path = generate_html_report(
            results,
            signature_source=sig_source,
            num_studies=num_studies,
            tissue="broad",
            disease_id=disease_id,
            provenance=provenance,
        )
        return Path(report_path)

    def build_provenance(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> dict:
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
