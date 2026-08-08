"""CAR-T Response Predictor service layer."""

from med_research.diseases.coverage import module_coverage
from med_research.pipeline.car_t_predictor.predictor import last_coverage
from med_research.web.dependencies import safe_serialize
from med_research.web.services.registry_service import run_module


def run_cart_analysis(top_n: int = 35, disease_id: str = "sle") -> dict:
    """Run CAR-T suitability analysis via the car_t_predictor registry adapter."""
    coverage = module_coverage(disease_id, "car_t", ("genes", "car_t_scores"))
    if not coverage.is_runnable:
        return {
            "genes": [],
            "total_genes": 0,
            "avg_score": 0.0,
            "tier1_count": 0,
            "tier2_count": 0,
            "tier3_count": 0,
            "coverage": coverage.to_dict(),
            "status": "blocked",
        }

    results = run_module("car_t_predictor", disease_id)
    coverage_payload = last_coverage.to_dict() if last_coverage else coverage.to_dict()

    if not results and coverage_payload.get("status") == "blocked":
        return {
            "genes": [],
            "total_genes": 0,
            "avg_score": 0.0,
            "tier1_count": 0,
            "tier2_count": 0,
            "tier3_count": 0,
            "coverage": coverage_payload,
            "status": "blocked",
        }

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
        "coverage": coverage_payload,
        "status": "limited_coverage" if coverage_payload.get("level") == "partial" else "ready",
    })
