"""Provisional expression signatures from Open Targets genetics associations (L2 tier)."""

from __future__ import annotations

from typing import Any, Optional

from med_research.diseases.bulk_store import OpenTargetsBulkStore
from med_research.diseases.id_resolver import DiseaseIdResolver
from med_research.diseases.scaffold import load_disease_registry, sanitize_id
from med_research.logging_config import get_logger

logger = get_logger(__name__)

LIMITATIONS_TEXT = (
    "Expression uses Open Targets genetics association proxy; not literature-curated GEO consensus."
)

# Dynamically registered proxy consensus signatures (disease_id -> up/down gene dicts)
PROXY_CONSENSUS_GENES: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
PROXY_CONSENSUS_DISEASES: set[str] = set()


def build_proxy_signature(
    disease_id: str,
    ot_targets: list[dict],
    top_n: int = 12,
) -> dict[str, dict[str, dict[str, float]]]:
    """Derive a provisional up/down signature from OT association scores.

    Top-scoring targets are treated as upregulated; lower-scoring associated
    targets fill the downregulated list. This is a genetics proxy, not expression data.
    """
    scored = sorted(
        [t for t in ot_targets if t.get("symbol") and t.get("score") is not None],
        key=lambda t: t["score"],
        reverse=True,
    )
    if not scored:
        return {"upregulated": {}, "downregulated": {}}

    mid = max(1, len(scored) // 2)
    up_candidates = scored[:top_n]
    down_candidates = scored[mid : mid + top_n]

    upregulated: dict[str, dict[str, float]] = {}
    for t in up_candidates:
        score = float(t["score"])
        upregulated[t["symbol"]] = {
            "fold_change": round(1.0 + score, 2),
            "confidence": round(min(0.85, score), 2),
        }

    downregulated: dict[str, dict[str, float]] = {}
    for t in down_candidates:
        score = float(t["score"])
        downregulated[t["symbol"]] = {
            "fold_change": round(1.0 + score * 0.5, 2),
            "confidence": round(min(0.75, score * 0.8), 2),
        }

    return {"upregulated": upregulated, "downregulated": downregulated}


def register_proxy_disease(disease_id: str, signature: dict[str, Any]) -> None:
    """Register a disease in the proxy consensus tier."""
    key = sanitize_id(disease_id)
    PROXY_CONSENSUS_GENES[key] = signature
    PROXY_CONSENSUS_DISEASES.add(key)


def apply_proxy_for_disease(
    disease_id: str,
    store: Optional[OpenTargetsBulkStore] = None,
    resolver: Optional[DiseaseIdResolver] = None,
) -> dict:
    """Build and register proxy expression signature for one disease."""
    store = store or OpenTargetsBulkStore()
    resolver = resolver or DiseaseIdResolver(bulk_store=store)
    disease_id = sanitize_id(disease_id)

    entry = next(
        (e for e in load_disease_registry() if sanitize_id(e.get("id", "")) == disease_id),
        {"id": disease_id, "name": disease_id},
    )
    resolution = resolver.resolve_entry(entry)
    if not resolution.efo_id or not store.is_available():
        return {
            "disease_id": disease_id,
            "status": "blocked",
            "reason": "no_efo_or_bulk_store",
        }

    targets = store.get_targets(resolution.efo_id, limit=40)
    signature = build_proxy_signature(disease_id, targets)
    register_proxy_disease(disease_id, signature)
    return {
        "disease_id": disease_id,
        "status": "registered",
        "efo_id": resolution.efo_id,
        "up_count": len(signature["upregulated"]),
        "down_count": len(signature["downregulated"]),
        "limitations": LIMITATIONS_TEXT,
        "coverage": "limited_coverage",
    }


def apply_proxy_all(
    *,
    limit: Optional[int] = None,
    skip_curated: bool = True,
) -> dict:
    """Register proxy signatures for all registry diseases."""
    from med_research.pipeline.gene_expression.geo import CURATED_CONSENSUS_DISEASES

    store = OpenTargetsBulkStore()
    resolver = DiseaseIdResolver(bulk_store=store)
    entries = load_disease_registry()
    if limit:
        entries = entries[:limit]

    results = []
    for entry in entries:
        did = sanitize_id(entry.get("id", ""))
        if skip_curated and did in CURATED_CONSENSUS_DISEASES:
            continue
        results.append(apply_proxy_for_disease(did, store, resolver))

    registered = sum(1 for r in results if r.get("status") == "registered")
    return {"total": len(results), "registered": registered, "results": results}
