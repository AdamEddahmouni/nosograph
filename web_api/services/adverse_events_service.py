"""Adverse Event Profiling service."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from web_api.dependencies import safe_serialize


def run_safety_profiling(
    drug_id: str | None = None,
    progress_callback=None,
) -> dict:
    """Run adverse event safety profiling.

    Args:
        drug_id: Optional specific drug ID. If None, profiles all drugs.
        progress_callback: Optional callable(percent, message) for progress.

    Returns:
        Dict with safety profiles or single drug profile.
    """
    from adverse_events.profiler import (
        get_drug_profile,
        get_safety_summary,
        score_all_drugs,
    )

    cb = progress_callback or (lambda p, m: None)

    if drug_id:
        cb(50, f"Loading safety profile for {drug_id}...")
        profile = get_drug_profile(drug_id)
        cb(100, "Profile loaded")
        return safe_serialize(profile) if profile else {"error": f"Drug '{drug_id}' not found"}

    cb(10, "Scoring all drugs for adverse event safety...")
    results = score_all_drugs(progress_callback=cb)
    summary = get_safety_summary()

    cb(90, "Formatting results...")
    return {
        "total_drugs": summary["total_drugs"],
        "avg_safety_score": summary["avg_safety_score"],
        "safest_drug": summary["safest_drug"],
        "safest_score": summary["safest_score"],
        "riskiest_drug": summary["riskiest_drug"],
        "riskiest_score": summary["riskiest_score"],
        "drugs_with_bbw": summary["drugs_with_bbw"],
        "drugs_with_dil_risk": summary["drugs_with_dil_risk"],
        "profiles": safe_serialize(results),
    }
