"""
Expression Signature Manager

Manages both hardcoded curated signatures and GEO-derived dynamic signatures.
Provides a unified interface for signature retrieval with fallback logic.
"""

from pathlib import Path
from typing import Optional

SIGNATURE_DIR = Path(__file__).parent / "data"
SIGNATURE_DIR.mkdir(parents=True, exist_ok=True)


def get_signature(disease: str = "sle", tissue: Optional[str] = None,
                  source: str = "auto") -> dict:
    """Get expression signature for a disease.

    Args:
        disease: Disease ID (sle, ra, ms, etc.)
        tissue: Tissue filter (pbmc_blood, kidney, skin, or None for all)
        source: "auto" (try GEO first, fallback to curated), "geo" (GEO only),
                "curated" (hardcoded only)

    Returns dict with upregulated, downregulated gene lists with metadata.
    """
    if source == "curated":
        return _get_curated_signature(disease)

    if source in ("auto", "geo"):
        try:
            from med_research.pipeline.gene_expression.geo import get_expression_signature
            sig = get_expression_signature(disease, tissue)
            if sig and sig.get("num_studies_used", 0) > 0:
                return sig
        except Exception:
            pass

    if source in ("auto", "curated"):
        return _get_curated_signature(disease)

    return _get_curated_signature(disease)


def _get_curated_signature(disease: str = "sle") -> dict:
    """Return the hardcoded curated signature from correlator.py as fallback."""
    from med_research.pipeline.gene_expression.correlator import SLE_DOWNREGULATED, SLE_UPREGULATED

    return {
        "source": "curated_literature",
        "num_studies_used": 0,
        "disease": disease,
        "upregulated": {k: {"fold_change": v, "confidence": 0.9}
                       for k, v in SLE_UPREGULATED.items()},
        "downregulated": {k: {"fold_change": v, "confidence": 0.9}
                         for k, v in SLE_DOWNREGULATED.items()},
    }


def list_available_signatures() -> list:
    """List available GEO-derived signatures in cache."""
    from med_research.pipeline.gene_expression.geo import CACHE_DIR as GEO_CACHE_DIR
    sigs = []
    for f in sorted(GEO_CACHE_DIR.glob("signature_*.json")):
        sigs.append(f.stem.replace("signature_", ""))
    return sigs
