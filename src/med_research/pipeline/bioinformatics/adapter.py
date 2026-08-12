"""BasePipelineModule adapters for bioinformatics engines (GWAS, enrichment, PPI)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import ProvenanceMetadata, build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.results import EnrichmentResult, GwasResult, PpiResult


@register_module
class GwasModule(BasePipelineModule[GwasResult]):
    """Adapter around ``bioinformatics.gwas`` GWAS Catalog annotation."""

    _COVERAGE_MODULE = "gwas"

    @property
    def module_id(self) -> str:
        return "gwas"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "gwas_search_terms")

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> GwasResult:
        from med_research.pipeline.bioinformatics.gwas import run_gwas_analysis

        return run_gwas_analysis(
            disease_id=disease_id,
            max_studies=opts.get("max_studies", 30),
            use_cache=opts.get("use_cache", True),
            resolve_snps=opts.get("resolve_snps", True),
            progress_callback=opts.get("progress_callback"),
        )

    def report(
        self,
        results: GwasResult,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report

        gwas_results = results.get("gwas_results")
        gwas_crossref = results.get("crossref")
        report_path = generate_bioinformatics_report(
            gwas_results=gwas_results if isinstance(gwas_results, dict) else {},
            gwas_crossref=gwas_crossref if isinstance(gwas_crossref, dict) else {},
            disease_id=disease_id,
            provenance=provenance,
        )
        return Path(report_path)

    def build_provenance(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> ProvenanceMetadata:
        extra: dict[str, Any] = {
            key: value
            for key, value in opts.items()
            if key not in {"sources", "cache_or_live", "scoring"}
        }
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["gwas_catalog"],
            cache_or_live="cache",
            scoring={"analysis": "gwas_crossref"},
            **extra,
        )


@register_module
class EnrichmentModule(BasePipelineModule[EnrichmentResult]):
    """Adapter around ``bioinformatics.enrichment`` pathway enrichment."""

    _COVERAGE_MODULE = "enrichment"

    @property
    def module_id(self) -> str:
        return "enrichment"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "pathways")

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> EnrichmentResult:
        from med_research.pipeline.bioinformatics.enrichment import run_enrichment_analysis

        return run_enrichment_analysis(
            disease_id=disease_id,
            untargeted_only=opts.get("untargeted_only", False),
            use_cache=opts.get("use_cache", True),
            progress_callback=opts.get("progress_callback"),
        )

    def report(
        self,
        results: EnrichmentResult,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report

        enrichment_results = results.get("enrichment_results")
        gene_list = results.get("gene_list")
        kg_matches = results.get("kg_pathway_matches")
        report_path = generate_bioinformatics_report(
            enrichment_results=(enrichment_results if isinstance(enrichment_results, dict) else {}),
            gene_list=gene_list if isinstance(gene_list, list) else [],
            kg_matches=kg_matches if isinstance(kg_matches, dict) else {},
            disease_id=disease_id,
            provenance=provenance,
        )
        return Path(report_path)

    def build_provenance(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> ProvenanceMetadata:
        extra: dict[str, Any] = {
            key: value
            for key, value in opts.items()
            if key not in {"sources", "cache_or_live", "scoring"}
        }
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["enrichr"],
            cache_or_live="cache",
            scoring={"analysis": "pathway_enrichment"},
            **extra,
        )


@register_module
class PpiModule(BasePipelineModule[PpiResult]):
    """Adapter around ``bioinformatics.ppi`` STRING PPI hub analysis."""

    _COVERAGE_MODULE = "ppi"

    @property
    def module_id(self) -> str:
        return "ppi"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph", "drug_repurposing")

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes",)

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> PpiResult:
        from med_research.pipeline.bioinformatics.ppi import (
            DEFAULT_CONFIDENCE,
            run_ppi_analysis,
        )

        return run_ppi_analysis(
            disease_id=disease_id,
            confidence=opts.get("confidence", DEFAULT_CONFIDENCE),
            expand_neighbors=opts.get("expand_neighbors", 0),
            use_cache=opts.get("use_cache", True),
            progress_callback=opts.get("progress_callback"),
        )

    def report(
        self,
        results: PpiResult,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report

        hub_scores = results.get("hub_scores")
        ppi_crossref = results.get("crossref")
        ppi_graph = results.get("graph")
        report_path = generate_bioinformatics_report(
            hub_scores=hub_scores if isinstance(hub_scores, list) else [],
            ppi_crossref=ppi_crossref if isinstance(ppi_crossref, dict) else {},
            ppi_graph=ppi_graph if isinstance(ppi_graph, dict) else {},
            disease_id=disease_id,
            provenance=provenance,
        )
        return Path(report_path)

    def build_provenance(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> ProvenanceMetadata:
        extra: dict[str, Any] = {
            key: value
            for key, value in opts.items()
            if key not in {"sources", "cache_or_live", "scoring"}
        }
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["string"],
            cache_or_live="cache",
            scoring={"analysis": "ppi_hub"},
            **extra,
        )
