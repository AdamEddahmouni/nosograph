"""Drug Repurposing service — wraps engine.py functions."""

import sys
from pathlib import Path

# Ensure the parent is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from med_research.web.dependencies import get_candidates, get_kg_genes, get_knowledge_graph


def run_repurposing(top_n: int = 15, gene_id: str | None = None, disease_id: str = "sle") -> dict:
    """Score drug repurposing candidates and return results."""
    from med_research.pipeline.drug_repurposing.engine import (
        identify_untargeted_genes,
        score_candidates,
    )

    G = get_knowledge_graph(disease_id)
    genes = get_kg_genes(disease_id)
    candidates = get_candidates()

    untargeted = identify_untargeted_genes(G, disease_id)
    untargeted_ids = {g["id"] for g in untargeted}

    scored = score_candidates(G, candidates, genes, disease_id=disease_id)
    scored = [c for c in scored if c["gene_id"] in untargeted_ids]

    # Filter by gene if requested
    if gene_id and gene_id in genes:
        scored = [c for c in scored if c["gene_id"] == gene_id]

    # Sort by composite score
    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    scored = scored[:top_n]

    # Add rank
    for i, c in enumerate(scored, 1):
        c["rank"] = i

    # Summary stats
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
    }


def get_gene_repurposing(gene_id: str, disease_id: str = "sle") -> dict | None:
    """Get all repurposing candidates for a specific gene."""
    genes = get_kg_genes(disease_id)
    if gene_id not in genes:
        return None

    G = get_knowledge_graph(disease_id)
    candidates = get_candidates()

    from med_research.pipeline.drug_repurposing.engine import score_candidates

    scored = score_candidates(G, candidates, genes, disease_id=disease_id)
    gene_candidates = [c for c in scored if c["gene_id"] == gene_id]
    gene_candidates.sort(key=lambda x: x["composite_score"], reverse=True)

    for i, c in enumerate(gene_candidates, 1):
        c["rank"] = i

    gene = genes[gene_id]
    return {
        "gene_id": gene_id,
        "gene_name": gene.get("name", gene_id),
        "gene_category": gene.get("category", ""),
        "gene_function": gene.get("function", ""),
        "disease_evidence": gene.get(
            "disease_evidence", gene.get("lupus_evidence", "")
        ),
        "disease_id": disease_id,
        "odds_ratio": gene.get("odds_ratio"),
        "candidates": gene_candidates,
        "best_score": gene_candidates[0]["composite_score"] if gene_candidates else 0,
        "count": len(gene_candidates),
    }
