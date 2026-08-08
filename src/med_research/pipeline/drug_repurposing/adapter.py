"""Registry adapter for drug repurposing scoring and reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import register_module


@register_module
class DrugRepurposingModule(BasePipelineModule):
    """Adapter around ``drug_repurposing.engine`` scoring and reporting."""

    _COVERAGE_MODULE = "repurposing"

    @property
    def module_id(self) -> str:
        return "drug_repurposing"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "drugs", "relationships")

    def run(self, disease_id: str, **opts: Any) -> list:
        from med_research.cache import disease_output_path, write_json_atomic
        from med_research.pipeline.drug_repurposing.engine import (
            DATA_DIR,
            identify_untargeted_genes,
            load_genes,
            load_json,
            load_knowledge_graph,
            score_candidates,
        )

        graph = load_knowledge_graph(disease_id)
        genes = load_genes(disease_id)
        candidates_data = load_json(DATA_DIR / "candidates.json")
        candidates = candidates_data["repurposing_candidates"]

        untargeted = identify_untargeted_genes(graph, disease_id)
        untargeted_ids = {gene["id"] for gene in untargeted}

        scored = score_candidates(
            graph,
            candidates,
            genes,
            disease_id=disease_id,
            progress_callback=opts.get("progress_callback"),
        )
        gene_id = opts.get("gene_id")
        untargeted_only = opts.get("untargeted_only", gene_id is None)
        if gene_id:
            scored = [candidate for candidate in scored if candidate["gene_id"] == gene_id]
        elif untargeted_only:
            scored = [
                candidate for candidate in scored if candidate["gene_id"] in untargeted_ids
            ]

        if opts.get("save", True):
            output_path = disease_output_path(DATA_DIR, "candidates", disease_id)
            write_json_atomic(output_path, {"repurposing_candidates": scored})

        return scored

    def report(
        self,
        results: list,
        disease_id: str,
        *,
        provenance: dict[str, Any] | None = None,
    ) -> Path:
        from med_research.pipeline.drug_repurposing.engine import (
            identify_untargeted_genes,
            load_genes,
            load_knowledge_graph,
        )
        from med_research.pipeline.drug_repurposing.report import generate_html_report

        graph = load_knowledge_graph(disease_id)
        genes = load_genes(disease_id)
        untargeted = identify_untargeted_genes(graph, disease_id)

        report_path = generate_html_report(
            results,
            untargeted,
            genes,
            graph,
            disease_id=disease_id,
            provenance=provenance,
        )
        return Path(report_path)

    def build_provenance(self, disease_id: str, **opts: Any) -> dict[str, Any]:
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["knowledge_graph"],
            cache_or_live="cache",
            scoring={"ranking": "composite_score"},
            **opts,
        )
