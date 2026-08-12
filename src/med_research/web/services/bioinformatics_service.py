"""Bioinformatics service — wraps GWAS, enrichment, PPI via module registry."""

from typing import Any

from med_research.web.config import USE_CACHE
from med_research.web.dependencies import get_kg_genes
from med_research.web.services.registry_service import (
    dispatch_sync_module,
    make_progress_reporter,
)


def run_gwas(
    max_studies: int = 30,
    no_cache: bool = False,
    progress_callback: Any = None,
    disease_id: str = "sle",
) -> dict:
    """Run GWAS catalog annotation for a disease."""
    reporter = make_progress_reporter(progress_callback)
    reporter("GWAS analysis", 0, 4)

    raw = dispatch_sync_module(
        "gwas",
        disease_id,
        max_studies=max_studies,
        use_cache=not no_cache and USE_CACHE,
        progress_callback=progress_callback,
    )

    reporter("Formatting GWAS response", 3, 4)
    genes = get_kg_genes(disease_id)
    response = _format_gwas_response(
        raw.get("gwas_results", {}),
        raw.get("crossref", {}),
        genes,
    )
    response["coverage"] = raw.get("coverage", {})
    response["status"] = raw.get("status", "ready")
    reporter("GWAS analysis complete", 4, 4)
    return response


def _format_gwas_response(gwas_results: dict, crossref: dict, genes: dict) -> dict:
    """Format GWAS results for API response."""
    gene_associations = gwas_results.get("gene_associations", {})
    top_hits = sorted(
        [
            {
                "gene": gene,
                "n_studies": info["n_studies"],
                "best_p_value": info["best_p_value"],
                "studies": info.get("studies", [])[:5],
            }
            for gene, info in gene_associations.items()
        ],
        key=lambda x: x["n_studies"],
        reverse=True,
    )[:20]

    return {
        "total_studies": gwas_results.get("total_studies_analyzed", 0),
        "total_associations": gwas_results.get("total_associations", 0),
        "unique_genes": len(gene_associations),
        "gene_associations": gene_associations,
        "crossref": crossref,
        "top_hits": top_hits,
    }


def run_enrichment(
    untargeted_only: bool = False,
    no_cache: bool = False,
    progress_callback: Any = None,
    disease_id: str = "sle",
) -> dict:
    """Run pathway enrichment analysis for a disease."""
    reporter = make_progress_reporter(progress_callback)
    reporter("Enrichment analysis", 0, 3)

    raw = dispatch_sync_module(
        "enrichment",
        disease_id,
        untargeted_only=untargeted_only,
        use_cache=not no_cache and USE_CACHE,
        progress_callback=progress_callback,
    )

    reporter("Formatting enrichment response", 2, 3)
    gene_list = raw.get("gene_list", [])
    enrichment_results = raw.get("enrichment_results", {})
    kg_matches = raw.get("kg_pathway_matches", {})
    coverage = raw.get("coverage", {})

    libraries = []
    for lib_name, result in enrichment_results.items():
        terms = []
        for t in result.get("terms", []):
            terms.append(
                {
                    "term": t["term"],
                    "p_value": t["p_value"],
                    "adj_p_value": t["adj_p_value"],
                    "odds_ratio": t["odds_ratio"],
                    "combined_score": t["combined_score"],
                    "genes": t.get("genes", []),
                    "overlap": t.get("overlap", ""),
                }
            )
        libraries.append(
            {
                "library": result.get("library", lib_name),
                "terms": terms,
                "total_significant": result.get("total_significant", 0),
            }
        )

    reporter("Enrichment analysis complete", 3, 3)
    return {
        "genes_analyzed": len(gene_list),
        "gene_list": [g["symbol"] for g in gene_list],
        "libraries": libraries,
        "kg_pathway_matches": {k: v for k, v in kg_matches.items()},
        "coverage": coverage,
        "status": "limited_coverage" if coverage.get("level") == "partial" else "ready",
    }


def run_ppi(
    confidence: float = 0.4,
    no_cache: bool = False,
    progress_callback: Any = None,
    disease_id: str = "sle",
) -> dict:
    """Build PPI network and compute hub scores for a disease."""
    reporter = make_progress_reporter(progress_callback)
    reporter("PPI analysis", 0, 3)

    raw = dispatch_sync_module(
        "ppi",
        disease_id,
        confidence=confidence,
        use_cache=not no_cache and USE_CACHE,
        progress_callback=progress_callback,
    )

    coverage = raw.get("coverage", {})
    hub_scores = raw.get("hub_scores", [])
    crossref = raw.get("crossref", {})
    graph = raw.get("graph", {})
    seed_genes = sum(1 for node in graph.get("nodes", []) if node.get("is_seed"))

    if raw.get("status") == "blocked" or not hub_scores:
        reporter("PPI analysis complete", 3, 3)
        return {
            "nodes": len(graph.get("nodes", [])),
            "edges": len(graph.get("edges", [])),
            "seed_genes": seed_genes,
            "confidence": confidence,
            "top_hubs": [],
            "hub_candidates": [],
            "hub_untargeted": [],
            "coverage": coverage,
            "status": raw.get("status", "limited_coverage"),
        }

    reporter("Formatting PPI response", 2, 3)
    top_hubs = []
    for h in hub_scores[:20]:
        top_hubs.append(
            {
                "symbol": h["symbol"],
                "gene_id": h.get("gene_id"),
                "hub_score": h["hub_score"],
                "degree": h["degree"],
                "degree_centrality": h["degree_centrality"],
                "betweenness_centrality": h["betweenness_centrality"],
                "is_disease_gene": h["is_lupus_gene"],
                "is_lupus_gene": h["is_lupus_gene"],
                "is_seed": h["is_seed"],
            }
        )

    reporter("PPI analysis complete", 3, 3)
    return {
        "nodes": len(graph.get("nodes", [])),
        "edges": len(graph.get("edges", [])),
        "seed_genes": seed_genes or len(hub_scores),
        "confidence": confidence,
        "top_hubs": top_hubs,
        "hub_candidates": crossref.get("hub_candidate_matches", []),
        "hub_untargeted": crossref.get("hub_untargeted", []),
        "coverage": coverage,
        "status": "limited_coverage" if coverage.get("level") == "partial" else "ready",
    }
