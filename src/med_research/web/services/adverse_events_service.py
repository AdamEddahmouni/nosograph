"""Adverse Event Profiling service."""

from typing import Any, cast

from med_research.diseases.coverage import module_coverage
from med_research.pipeline.adverse_events.profiler import get_drug_profile, get_safety_summary
from med_research.web.dependencies import safe_serialize
from med_research.web.services.registry_service import (
    dispatch_sync_module,
    make_progress_reporter,
    require_runnable_coverage,
)


def run_safety_profiling(
    drug_id: str | None = None,
    disease_id: str = "sle",
    progress_callback: Any = None,
) -> dict:
    """Run adverse event safety profiling."""
    reporter = make_progress_reporter(progress_callback)

    coverage = module_coverage(
        disease_id,
        "safety",
        ("symptoms", "adverse_event_profile", "safety_risk"),
    )
    require_runnable_coverage(coverage, "adverse_events")

    if drug_id:
        reporter(f"Loading safety profile for {drug_id}", 0, 1)
        profile = get_drug_profile(drug_id, disease_id=disease_id)
        reporter("Profile loaded", 1, 1)
        if not profile:
            return {"error": f"Drug '{drug_id}' not found"}
        return cast(dict[str, Any], safe_serialize(profile))

    reporter("Scoring drugs for adverse events", 0, 2)
    results = dispatch_sync_module(
        "adverse_events",
        disease_id,
        progress_callback=progress_callback,
    )
    summary = get_safety_summary(disease_id=disease_id, results=results)

    reporter("Formatting safety results", 2, 2)
    return {
        "total_drugs": summary["total_drugs"],
        "avg_safety_score": summary["avg_safety_score"],
        "safest_drug": summary["safest_drug"],
        "safest_score": summary["safest_score"],
        "riskiest_drug": summary["riskiest_drug"],
        "riskiest_score": summary["riskiest_score"],
        "drugs_with_bbw": summary["drugs_with_bbw"],
        "drugs_with_disease_specific_risk": summary["drugs_with_disease_specific_risk"],
        "drugs_with_dil_risk": summary["drugs_with_disease_specific_risk"],
        "profiles": safe_serialize(results),
        "coverage": coverage.to_dict(),
        "status": "limited_coverage" if coverage.level == "partial" else "ready",
        "disease_id": disease_id,
        "profile_source": summary.get("profile_source", ""),
        "profile_curated_inputs": summary.get("profile_curated_inputs", []),
        "profile_inferred_inputs": summary.get("profile_inferred_inputs", []),
        "limitations": summary.get("limitations", []),
    }
