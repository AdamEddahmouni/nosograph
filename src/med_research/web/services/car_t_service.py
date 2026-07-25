"""CAR-T Response Predictor service layer."""

from med_research.web.services.shared_services import safe_serialize


def run_cart_analysis(top_n: int = 35) -> dict:
    """Run CAR-T suitability analysis and return serializable result."""
    from med_research.pipeline.car_t_predictor.predictor import compute_all_scores

    results = compute_all_scores()

    scores = [r["composite_score"] for r in results]
    avg = sum(scores) / len(scores) if scores else 0.0

    tier1 = sum(1 for r in results if r["composite_score"] >= 8.0)
    tier2 = sum(1 for r in results if 7.0 <= r["composite_score"] < 8.0)
    tier3 = sum(1 for r in results if 5.0 <= r["composite_score"] < 7.0)

    return safe_serialize({
        "genes": results[:top_n],
        "total_genes": len(results),
        "avg_score": round(avg, 2),
        "tier1_count": tier1,
        "tier2_count": tier2,
        "tier3_count": tier3,
    })
