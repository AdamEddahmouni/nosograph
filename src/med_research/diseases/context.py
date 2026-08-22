"""Resolve disease module context (CURIEs, tier, gaps) for API bridge."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from med_research.biomed.legacy.manifest import LEGACY_DISEASE_MONDO_MAP
from med_research.diseases.base import Disease
from med_research.diseases.id_resolver import DiseaseIdResolver
from med_research.diseases.scaffold import load_disease_registry, sanitize_id
from med_research.diseases.tier_model import compute_tier

_STATUS_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "reports" / "disease_batch_status.json"
)


@lru_cache(maxsize=1)
def _registry_by_id() -> dict[str, dict[str, Any]]:
    return {sanitize_id(e.get("id", "")): e for e in load_disease_registry()}


@lru_cache(maxsize=1)
def _tier_from_status_report() -> dict[str, str]:
    if not _STATUS_PATH.is_file():
        return {}
    try:
        data = json.loads(_STATUS_PATH.read_text(encoding="utf-8"))
        return {
            row["disease_id"]: row.get("tier", "blocked") for row in data.get("per_disease", [])
        }
    except (json.JSONDecodeError, KeyError, OSError):
        return {}


@lru_cache(maxsize=1)
def _gaps_from_status_report() -> dict[str, list[str]]:
    if not _STATUS_PATH.is_file():
        return {}
    try:
        data = json.loads(_STATUS_PATH.read_text(encoding="utf-8"))
        return {
            row["disease_id"]: row.get("config_gaps", []) for row in data.get("per_disease", [])
        }
    except (json.JSONDecodeError, KeyError, OSError):
        return {}


@lru_cache(maxsize=1)
def _counts_from_status_report() -> dict[str, dict[str, int]]:
    if not _STATUS_PATH.is_file():
        return {}
    try:
        data = json.loads(_STATUS_PATH.read_text(encoding="utf-8"))
        counts: dict[str, dict[str, int]] = {}
        for row in data.get("per_disease", []):
            if "disease_id" in row and "counts" in row:
                counts[row["disease_id"]] = row["counts"]
        for row in data.get("harvest", {}).get("succeeded", []):
            if "disease_id" in row and "counts" in row:
                counts[row["disease_id"]] = row["counts"]
        return counts
    except (json.JSONDecodeError, KeyError, OSError):
        return {}


_resolver: DiseaseIdResolver | None = None


def _get_resolver() -> DiseaseIdResolver:
    global _resolver
    if _resolver is None:
        _resolver = DiseaseIdResolver()
    return _resolver


@lru_cache(maxsize=16384)
def resolve_disease_context(disease_id: str, *, full_validate: bool = True) -> dict[str, Any]:
    """Return mondo_curie, efo_id, readiness_tier, and config_gaps for a disease slug."""
    did = sanitize_id(disease_id)
    entry = _registry_by_id().get(did, {"id": did, "name": did})
    if not entry.get("efo_id") and not entry.get("mondo_id"):
        legacy_mondo = LEGACY_DISEASE_MONDO_MAP.get(did)
        if legacy_mondo:
            entry = {
                **entry,
                "efo_id": legacy_mondo.replace(":", "_"),
                "mondo_id": legacy_mondo,
            }

    resolver = _get_resolver()
    resolution = resolver.resolve_entry(entry)

    mondo_curie = resolution.mondo_id
    efo_id = resolution.efo_id

    tier = _tier_from_status_report().get(did)
    gaps = _gaps_from_status_report().get(did, [])
    name = str(entry.get("name", did))

    if full_validate or tier is None:
        try:
            disease = Disease(did)
            name = disease.profile.name
            if tier is None:
                checks = disease.validate()
                drug_count = len(disease.load_drugs().get("drugs", []))
                strict_pass = all(s == "ok" for s in checks.values())
                tier = compute_tier(did, checks, drug_count=drug_count, strict_pass=strict_pass)
            if not gaps:
                checks = disease.validate()
                gaps = [f for f, s in checks.items() if s != "ok"]
        except Exception as exc:
            tier = tier or "blocked"
            if not gaps:
                gaps = [str(exc)]

    return {
        "disease_id": did,
        "name": name,
        "mondo_curie": mondo_curie,
        "efo_id": efo_id,
        "readiness_tier": tier or "blocked",
        "config_gaps": gaps,
        "resolution_confidence": resolution.resolution_confidence,
        "resolution_source": resolution.resolution_source,
    }


def clear_context_cache() -> None:
    _registry_by_id.cache_clear()
    _tier_from_status_report.cache_clear()
    _gaps_from_status_report.cache_clear()
    resolve_disease_context.cache_clear()
