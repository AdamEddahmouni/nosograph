"""Drug Combination Synergy service."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from med_research.web.dependencies import safe_serialize


def run_synergy(
    top_n: int = 20,
    progress_callback=None,
    disease_id: str = "sle",
) -> dict:
    """Run drug combination synergy prediction.

    Args:
        top_n: Number of top pairs to return.
        progress_callback: Optional callable(percent, message) for progress.
        disease_id: Disease whose drug library is used.

    Returns:
        Dict with synergy results.
    """
    from med_research.pipeline.drug_synergy.engine import compute_synergy

    cb = progress_callback or (lambda p, m: None)

    pairs = compute_synergy(progress_callback=cb, disease_id=disease_id)

    pairs = safe_serialize(pairs)

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
    }
