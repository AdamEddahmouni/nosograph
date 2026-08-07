"""Adverse Event Profiling service."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from med_research.web.dependencies import safe_serialize


def run_safety_profiling(
    drug_id: str | None = None,
    disease_id: str = "sle",
    progress_callback=None,
) -> dict:
    """Run adverse event safety profiling.

    Args:
        drug_id: Optional specific drug ID. If None, profiles all drugs.
        disease_id: Disease ID to profile against.
        progress_callback: Optional callable(percent, message) for progress.

    Returns:
        Dict with safety profiles or single drug profile.
    """
    from med_research.pipeline.adverse_events.profiler import (
        get_drug_profile,
        get_safety_summary,
        score_all_drugs,
    )

    cb = progress_callback or (lambda p, m: None)

    from med_research.diseases.coverage import module_coverage
    coverage = module_coverage(
        disease_id,
        "safety",
        ("symptoms", "adverse_event_profile", "safety_risk"),
    )
    if not coverage.is_runnable:
        cb(100, "Safety analysis blocked by incomplete disease coverage")
        return {
            "total_drugs": 0,
            "profiles": [],
            "coverage": coverage.to_dict(),
            "status": "blocked",
        }

    if drug_id:
        cb(50, f"Loading safety profile for {drug_id}...")
        profile = get_drug_profile(drug_id, disease_id=disease_id)
        cb(100, "Profile loaded")
        if not profile:
            return {"error": f"Drug '{drug_id}' not found"}
        return safe_serialize(profile)

    cb(10, "Scoring all drugs for adverse event safety...")
    results = score_all_drugs(progress_callback=cb, disease_id=disease_id)
    summary = get_safety_summary(disease_id=disease_id, results=results)

    cb(90, "Formatting results...")
    return {
        "total_drugs": summary["total_drugs"],
        "avg_safety_score": summary["avg_safety_score"],
        "safest_drug": summary["safest_drug"],
        "safest_score": summary["safest_score"],
        "riskiest_drug": summary["riskiest_drug"],
        "riskiest_score": summary["riskiest_score"],
        "drugs_with_bbw": summary["drugs_with_bbw"],
        "drugs_with_disease_specific_risk": summary["drugs_with_disease_specific_risk"],
        # Compatibility alias for clients that still consume the old key.
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
