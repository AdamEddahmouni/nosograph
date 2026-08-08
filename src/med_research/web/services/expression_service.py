"""Gene Expression Correlation service layer."""

from med_research.diseases.coverage import module_coverage
from med_research.pipeline.gene_expression.correlator import last_coverage
from med_research.web.dependencies import safe_serialize
from med_research.web.services.registry_service import run_module


def run_correlation_analysis(top_n: int = 26, disease_id: str = "sle") -> dict:
    """Run gene expression correlation via the gene_expression registry adapter."""
    coverage = module_coverage(disease_id, "expression", ("genes", "drugs"))
    if not coverage.is_runnable:
        return {
            "drugs": [],
            "total_drugs": 0,
            "avg_score": 0.0,
            "tier1_count": 0,
            "tier2_count": 0,
            "tier3_count": 0,
            "coverage": coverage.to_dict(),
            "status": "blocked",
        }

    results = run_module("gene_expression", disease_id)
    coverage_payload = last_coverage.to_dict() if last_coverage else coverage.to_dict()

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
        "coverage": coverage_payload,
        "status": "limited_coverage" if coverage_payload.get("level") == "partial" else "ready",
    })
