"""Biomarker Discovery service layer."""

from med_research.diseases.coverage import module_coverage
from med_research.pipeline.biomarker_discovery.discover import last_coverage
from med_research.web.dependencies import safe_serialize
from med_research.web.services.registry_service import (
    dispatch_sync_module,
    require_runnable_coverage,
)


def run_biomarker_analysis(top_n: int = 35, disease_id: str = "sle") -> dict:
    """Run biomarker discovery via the biomarker_discovery registry adapter."""
    coverage = module_coverage(disease_id, "biomarkers", ("genes",))
    require_runnable_coverage(coverage, "biomarker_discovery")

    results = dispatch_sync_module("biomarker_discovery", disease_id)
    coverage_payload = last_coverage.to_dict() if last_coverage else coverage.to_dict()

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
        "coverage": coverage_payload,
        "status": "limited_coverage" if coverage_payload.get("level") == "partial" else "ready",
    })
