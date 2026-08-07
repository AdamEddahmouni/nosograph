"""Service layer for cross-disease analysis operations."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from med_research.pipeline.cross_disease.analyzer import (  # noqa: E402
    compute_cross_disease_analysis,  # noqa: E402
)


def run_cross_disease_analysis(disease_id: str = None):
    """Run cross-disease analysis. Returns all results."""
    results = compute_cross_disease_analysis()

    result = {
        "shared_genes": results.get("shared_genes", {}),
        "shared_drugs": results.get("shared_drugs", {}),
        "shared_pathways": results.get("shared_pathways", {}),
        "disease_similarity": results.get("disease_similarity", []),
        "multi_disease_drugs": results.get("multi_disease_drugs", []),
        "disease_count": results.get("total_diseases", 0),
        "diseases": list(results.get("disease_summary", {}).keys()),
        "disease_summary": results.get("disease_summary", {}),
    }

    return result


def run_comparative_modules(top_synergy: int = 5):
    """Run biomarker/expression/synergy for every disease, stacked for comparison."""
    from med_research.pipeline.cross_disease.analyzer import compute_comparative_modules
    from med_research.web.services.shared_services import safe_serialize

    results = compute_comparative_modules(top_synergy=top_synergy)
    return safe_serialize(results)
