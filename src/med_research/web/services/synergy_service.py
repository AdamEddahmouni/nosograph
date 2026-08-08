"""Drug Combination Synergy service."""

from med_research.diseases.coverage import module_coverage
from med_research.web.dependencies import safe_serialize
from med_research.web.services.registry_service import make_progress_reporter, run_module


def run_synergy(
    top_n: int = 20,
    progress_callback=None,
    disease_id: str = "sle",
) -> dict:
    """Run drug combination synergy prediction."""
    coverage = module_coverage(disease_id, "synergy", ("genes", "drugs"))
    if not coverage.is_runnable:
        return {
            "total_pairs": 0,
            "pairs": [],
            "tier1_count": 0,
            "tier2_count": 0,
            "tier3_count": 0,
            "avg_score": 0.0,
            "max_score": 0.0,
            "coverage": coverage.to_dict(),
            "status": "blocked",
        }

    reporter = make_progress_reporter(progress_callback)
    reporter("Synergy analysis", 0, 1)

    pairs = run_module(
        "drug_synergy",
        disease_id,
        progress_callback=progress_callback,
        save=True,
    )
    pairs = safe_serialize(pairs)

    reporter("Synergy analysis complete", 1, 1)

    scores = [p["composite_score"] for p in pairs]
    avg = sum(scores) / len(scores) if scores else 0

    return {
        "total_pairs": len(pairs),
        "pairs": pairs[:top_n],
        "tier1_count": sum(1 for p in pairs if p["composite_score"] >= 8.0),
        "tier2_count": sum(1 for p in pairs if 7.0 <= p["composite_score"] < 8.0),
        "tier3_count": sum(1 for p in pairs if 6.0 <= p["composite_score"] < 7.0),
        "avg_score": round(avg, 2),
        "max_score": round(max(scores), 2) if scores else 0,
        "coverage": coverage.to_dict(),
        "status": "limited_coverage" if coverage.level == "partial" else "ready",
    }
