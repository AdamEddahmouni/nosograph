"""Biomarker Discovery service layer."""

from med_research.web.services.shared_services import safe_serialize


def run_biomarker_analysis(top_n: int = 35, disease_id: str = "sle") -> dict:
    """Run biomarker discovery and return serializable result."""
    from med_research.pipeline.biomarker_discovery.discover import compute_biomarker_matrix

    results = compute_biomarker_matrix(disease_id=disease_id)

    scores = [r["composite_score"] for r in results]
    avg = sum(scores) / len(scores) if scores else 0.0

    tier1 = sum(1 for r in results if r["composite_score"] >= 8.0)
    tier2 = sum(1 for r in results if 6.5 <= r["composite_score"] < 8.0)

    return safe_serialize({
        "biomarkers": results[:top_n],
        "total_genes": len(results),
        "avg_score": round(avg, 2),
        "tier1_count": tier1,
        "tier2_count": tier2,
    })
