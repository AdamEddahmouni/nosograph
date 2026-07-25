"""Gene Expression Correlation service layer."""

from med_research.web.services.shared_services import safe_serialize


def run_correlation_analysis(top_n: int = 26) -> dict:
    """Run gene expression correlation analysis and return serializable result.

    Args:
        top_n: Number of top results to return (default: all 26).

    Returns:
        Dict with drugs, total_drugs, avg_score, and tier counts.
    """
    from med_research.pipeline.gene_expression.correlator import compute_all_correlations

    results = compute_all_correlations()

    scores = [r["composite_score"] for r in results]
    avg = sum(scores) / len(scores) if scores else 0.0

    tier1 = sum(1 for r in results if r["composite_score"] >= 7.5)
    tier2 = sum(1 for r in results if 6.0 <= r["composite_score"] < 7.5)
    tier3 = sum(1 for r in results if 4.5 <= r["composite_score"] < 6.0)

    return safe_serialize({
        "drugs": results[:top_n],
        "total_drugs": len(results),
        "avg_score": round(avg, 2),
        "tier1_count": tier1,
        "tier2_count": tier2,
        "tier3_count": tier3,
    })
