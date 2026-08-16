"""Service layer for cross-disease analysis operations."""

from typing import Any, cast

from med_research.web.dependencies import safe_serialize  # noqa: F401 — used by callers
from med_research.web.services.registry_service import dispatch_sync_module


def run_cross_disease_analysis(disease_id: str | None = None) -> dict[str, Any]:
    """Run cross-disease analysis via the cross_disease registry adapter."""
    results = dispatch_sync_module("cross_disease", disease_id or "sle")

    shared_genes = results.get("shared_genes", {})
    if not isinstance(shared_genes, dict):
        shared_genes = {
            "matrix": {},
            "shared_genes": shared_genes if isinstance(shared_genes, list) else [],
        }

    shared_drugs = results.get("shared_drugs", {})
    if not isinstance(shared_drugs, dict):
        shared_drugs = {
            "matrix": {},
            "shared_drugs": shared_drugs if isinstance(shared_drugs, list) else [],
        }

    shared_pathways = results.get("shared_pathways", {})
    if not isinstance(shared_pathways, dict):
        shared_pathways = {
            "matrix": {},
            "shared_pathways": shared_pathways if isinstance(shared_pathways, list) else [],
        }

    disease_sim = results.get("disease_similarity", [])
    if isinstance(disease_sim, dict):
        disease_sim = disease_sim.get("ranked_pairs", [])
    elif not isinstance(disease_sim, list):
        disease_sim = []

    return {
        "shared_genes": shared_genes,
        "shared_drugs": shared_drugs,
        "shared_pathways": shared_pathways,
        "disease_similarity": disease_sim,
        "multi_disease_drugs": results.get("multi_disease_drugs", []),
        "disease_count": results.get("total_diseases", 0),
        "diseases": list(results.get("disease_summary", {}).keys()),
        "disease_summary": results.get("disease_summary", {}),
        "coverage": results.get("coverage", {}),
        "status": results.get("status", "ready"),
    }


def run_comparative_modules(top_synergy: int = 5) -> dict[str, Any]:
    """Run biomarker/expression/synergy for every disease, stacked for comparison."""
    results = dispatch_sync_module(
        "cross_disease",
        "sle",
        comparative=True,
        top_synergy=top_synergy,
    )
    return cast(dict[str, Any], safe_serialize(results))
