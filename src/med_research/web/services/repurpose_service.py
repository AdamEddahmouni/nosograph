"""Drug Repurposing service — wraps engine via module registry."""

from med_research.diseases.coverage import module_coverage
from med_research.pipeline.results import GeneRepurposingResponse, RepurposingAnalysisResponse
from med_research.web.dependencies import get_kg_genes
from med_research.web.services.registry_service import (
    dispatch_sync_module,
    require_runnable_coverage,
)


def run_repurposing(top_n: int = 15, gene_id: str | None = None, disease_id: str = "sle") -> RepurposingAnalysisResponse:
    """Score drug repurposing candidates and return results."""
    coverage = module_coverage(disease_id, "repurposing", ("genes", "drugs", "relationships"))
    require_runnable_coverage(coverage, "drug_repurposing")

    scored = dispatch_sync_module("drug_repurposing", disease_id)
    genes = get_kg_genes(disease_id)

    if gene_id and gene_id in genes:
        scored = [c for c in scored if c["gene_id"] == gene_id]

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    scored = scored[:top_n]

    for i, c in enumerate(scored, 1):
        c["rank"] = i

    n_tier1 = sum(1 for c in scored if c["composite_score"] >= 8.0)
    n_tier2 = sum(1 for c in scored if 7.0 <= c["composite_score"] < 8.0)
    avg_score = sum(c["composite_score"] for c in scored) / len(scored) if scored else 0

    return {
        "candidates": scored,
        "total": len(scored),
        "tier1_count": n_tier1,
        "tier2_count": n_tier2,
        "avg_score": round(avg_score, 2),
        "top_n": top_n,
        "coverage": coverage.to_dict(),
        "status": "limited_coverage" if coverage.level == "partial" else "ready",
    }


def get_gene_repurposing(gene_id: str, disease_id: str = "sle") -> GeneRepurposingResponse | None:
    """Get all repurposing candidates for a specific gene."""
    genes = get_kg_genes(disease_id)
    if gene_id not in genes:
        return None

    scored = dispatch_sync_module(
        "drug_repurposing",
        disease_id,
        gene_id=gene_id,
        untargeted_only=False,
    )
    gene_candidates = list(scored)
    gene_candidates.sort(key=lambda x: x["composite_score"], reverse=True)

    for i, c in enumerate(gene_candidates, 1):
        c["rank"] = i

    gene = genes[gene_id]
    return {
        "gene_id": gene_id,
        "gene_name": gene.get("name", gene_id),
        "gene_category": gene.get("category", ""),
        "gene_function": gene.get("function", ""),
        "disease_evidence": gene.get("disease_evidence", gene.get("lupus_evidence", "")),
        "disease_id": disease_id,
        "odds_ratio": gene.get("odds_ratio"),
        "candidates": gene_candidates,
        "best_score": gene_candidates[0]["composite_score"] if gene_candidates else 0,
        "count": len(gene_candidates),
    }
