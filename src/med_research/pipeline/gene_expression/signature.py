"""
Expression Signature Manager

Manages both hardcoded curated signatures and GEO-derived dynamic signatures.
Provides a unified interface for signature retrieval with fallback logic.
"""

import logging
from pathlib import Path
from typing import Optional

from med_research.exceptions import ExternalAPIError

SIGNATURE_DIR = Path(__file__).parent / "data"
SIGNATURE_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


def get_signature(disease: str = "sle", tissue: Optional[str] = None, source: str = "auto") -> dict:
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
        sig = _try_geo_signature(disease, tissue)
        if sig is not None:
            return sig

    if source in ("auto", "curated"):
        return _get_curated_signature(disease)

    return _get_curated_signature(disease)


def _try_geo_signature(disease: str, tissue: Optional[str]) -> dict | None:
    """Load a GEO-derived signature, logging and returning None on failure."""
    try:
        from med_research.pipeline.gene_expression.geo import get_expression_signature

        sig = get_expression_signature(disease, tissue)
        if sig and sig.get("num_studies_used", 0) > 0:
            return sig
    except ExternalAPIError as exc:
        logger.warning("GEO signature unavailable for %s, using curated fallback: %s", disease, exc)
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        logger.warning("GEO signature unavailable for %s, using curated fallback: %s", disease, exc)
    return None


def _get_curated_signature(disease: str = "sle") -> dict:
    """Return the hand-curated consensus signature for a disease."""
    from med_research.pipeline.gene_expression.geo import (
        CURATED_CONSENSUS_DISEASES,
        build_consensus_signature,
    )

    disease_key = disease.strip().lower()
    if disease_key not in CURATED_CONSENSUS_DISEASES:
        return {
            "source": "curated_consensus",
            "num_studies_used": 0,
            "disease": disease_key,
            "coverage": "not_curated",
            "upregulated": {},
            "downregulated": {},
        }

    sig = build_consensus_signature(
        [{"accession": "CURATED_LITERATURE"}],
        disease=disease_key,
        min_occurrence=1,
    )
    sig["source"] = "curated_consensus"
    sig["num_studies_used"] = 0
    return sig


def list_available_signatures() -> list:
    """List available GEO-derived signatures in cache."""
    from med_research.cache import NS_GEO, get_cache_manager

    mgr = get_cache_manager()
    stats = mgr.stats()
    ns = stats.get("namespaces", {}).get(NS_GEO, {})
    if ns.get("entries", 0) > 0:
        ns_dir = mgr._dir / NS_GEO
        sigs = []
        for cache_file in sorted(ns_dir.glob("signature_*.json")):
            # Filename is sanitized key + .json wrapper from CacheManager
            stem = cache_file.stem
            if stem.startswith("signature_"):
                sigs.append(stem.replace("signature_", "", 1))
        if sigs:
            return sigs

    from med_research.pipeline.gene_expression.geo import CACHE_DIR as GEO_CACHE_DIR

    sigs = []
    for f in sorted(GEO_CACHE_DIR.glob("signature_*.json")):
        sigs.append(f.stem.replace("signature_", ""))
    return sigs
