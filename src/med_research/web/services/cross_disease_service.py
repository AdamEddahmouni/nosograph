"""Service layer for cross-disease analysis operations."""

from med_research.web.dependencies import safe_serialize  # noqa: F401 — used by callers
from med_research.web.services.registry_service import dispatch_sync_module


def run_cross_disease_analysis(disease_id: str = None):
    """Run cross-disease analysis via the cross_disease registry adapter."""
    results = dispatch_sync_module("cross_disease", disease_id or "sle")

    return {
        "shared_genes": results.get("shared_genes", {}),
        "shared_drugs": results.get("shared_drugs", {}),
        "shared_pathways": results.get("shared_pathways", {}),
        "disease_similarity": results.get("disease_similarity", []),
        "multi_disease_drugs": results.get("multi_disease_drugs", []),
        "disease_count": results.get("total_diseases", 0),
        "diseases": list(results.get("disease_summary", {}).keys()),
        "disease_summary": results.get("disease_summary", {}),
        "coverage": results.get("coverage", {}),
        "status": results.get("status", "ready"),
    }


def run_comparative_modules(top_synergy: int = 5):
    """Run biomarker/expression/synergy for every disease, stacked for comparison."""
    results = dispatch_sync_module(
        "cross_disease",
        "sle",
        comparative=True,
        top_synergy=top_synergy,
    )
    return safe_serialize(results)
