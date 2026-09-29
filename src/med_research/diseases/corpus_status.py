"""Corpus-wide metrics and batch status reporting."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, cast

from med_research.diseases.base import Disease
from med_research.diseases.bulk_store import OpenTargetsBulkStore, normalize_disease_id
from med_research.diseases.registry_quality import is_blocked_slug
from med_research.diseases.scaffold import load_disease_registry, sanitize_id
from med_research.diseases.symptom_harvester import (
    _hpo_symptoms_from_biomed,
    local_symptom_source_availability,
)
from med_research.diseases.tier_model import aggregate_tiers, compute_tier
from med_research.logging_config import get_logger

logger = get_logger(__name__)

SYMPTOM_COVERAGE_STATES = (
    "populated",
    "awaiting_curation",
    "no_source_annotations",
    "source_unavailable",
    "identifier_unresolved",
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STATUS_PATH = ROOT / "data" / "reports" / "disease_batch_status.json"
DEFAULT_BASELINE_PATH = ROOT / "data" / "reports" / "corpus_baseline.json"


def _entity_counts(disease_id: str) -> dict[str, int]:
    """Lightweight KG entity counts without full coverage report."""
    try:
        disease = Disease(disease_id)
        genes = disease.load_genes().get("genes", [])
        drugs = disease.load_drugs().get("drugs", [])
        pathways = disease.load_pathways().get("pathways", [])
        return {"genes": len(genes), "drugs": len(drugs), "pathways": len(pathways)}
    except Exception:
        return {"genes": 0, "drugs": 0, "pathways": 0}


def _symptom_coverage_state(
    symptoms: list[str],
    registry_entry: dict[str, Any] | None,
    source_availability: dict[str, bool],
    source_labels: dict[str, list[str]],
) -> str:
    """Classify symptom presence and whether local sources can fill an empty list."""
    if symptoms:
        return "populated"

    registry_entry = registry_entry or {}
    mondo_id = registry_entry.get("mondo_id")
    efo_id = registry_entry.get("efo_id")
    if not mondo_id and not efo_id:
        return "identifier_unresolved"

    usable_sources: list[str] = []
    if mondo_id and source_availability.get("biomed_hpoa") and "biomed_hpoa" in source_labels:
        usable_sources.append("biomed_hpoa")
    if efo_id and source_availability.get("ot_phenotype") and "ot_phenotype" in source_labels:
        usable_sources.append("ot_phenotype")

    if any(source_labels[source] for source in usable_sources):
        return "awaiting_curation"
    if usable_sources:
        return "no_source_annotations"
    return "source_unavailable"


def _normalize_registry_identifier(value: Any, *, prefix: str) -> str | None:
    """Normalize local registry identifiers for local source readers."""
    if not isinstance(value, str) or not value.strip():
        return None
    identifier = value.strip()
    if prefix == "MONDO":
        if identifier.startswith("MONDO_"):
            return "MONDO:" + identifier.split("_", 1)[1]
        return identifier if identifier.startswith("MONDO:") else None
    normalized = normalize_disease_id(identifier)
    return normalized if normalized.startswith(("EFO_", "MONDO_")) else None


def build_corpus_status(
    *,
    limit: Optional[int] = None,
    include_symptom_source: bool = False,
) -> dict[str, Any]:
    """Scan disease modules and produce tier + gap metrics."""
    disease_ids = sorted(Disease.list_all())
    if limit:
        disease_ids = disease_ids[:limit]

    per_disease: list[dict[str, Any]] = []
    symptoms_populated = 0
    symptom_coverage_counts = {state: 0 for state in SYMPTOM_COVERAGE_STATES}
    try:
        registry = {
            sanitize_id(str(entry.get("id", ""))): entry
            for entry in load_disease_registry()
            if isinstance(entry, dict) and entry.get("id")
        }
    except Exception:
        logger.debug("Could not load local disease registry for symptom coverage", exc_info=True)
        registry = {}

    source_availability: dict[str, bool] | None = None
    bulk_store: OpenTargetsBulkStore | None = None

    for did in disease_ids:
        if is_blocked_slug(did):
            per_disease.append(
                {"disease_id": did, "tier": "blocked", "config_gaps": ["non_disease_slug"]}
            )
            continue
        try:
            disease = Disease(did)
            checks = disease.validate()
            counts = _entity_counts(did)
            drug_count = counts["drugs"]
            strict_pass = all(s == "ok" for s in checks.values())
            tier = compute_tier(did, checks, drug_count=drug_count, strict_pass=strict_pass)
            symptoms = disease.config.get("SYMPTOMS", [])
            symptom_list = symptoms if isinstance(symptoms, list) else []
            symptom_count = len(symptom_list)
            if symptom_count:
                symptoms_populated += 1

            entry = registry.get(sanitize_id(did))
            normalized_entry: dict[str, Any] = {}
            if entry:
                mondo_id = _normalize_registry_identifier(entry.get("mondo_id"), prefix="MONDO")
                efo_id = _normalize_registry_identifier(entry.get("efo_id"), prefix="EFO")
                if mondo_id:
                    normalized_entry["mondo_id"] = mondo_id
                if efo_id:
                    normalized_entry["efo_id"] = efo_id

            source_labels: dict[str, list[str]] = {}
            if not symptom_count and normalized_entry:
                if source_availability is None:
                    try:
                        if bulk_store is None:
                            bulk_store = OpenTargetsBulkStore()
                        source_availability = local_symptom_source_availability(bulk_store)
                    except Exception as exc:
                        logger.debug("Local symptom source availability check failed: %s", exc)
                        source_availability = {"biomed_hpoa": False, "ot_phenotype": False}

                if source_availability.get("biomed_hpoa") and normalized_entry.get("mondo_id"):
                    try:
                        source_labels["biomed_hpoa"] = _hpo_symptoms_from_biomed(
                            normalized_entry["mondo_id"], limit=1, raise_on_error=True
                        )
                    except Exception as exc:
                        logger.debug("Local HPOA phenotype lookup failed for %s: %s", did, exc)

                if source_availability.get("ot_phenotype"):
                    efo_id = normalized_entry.get("efo_id")
                    if efo_id:
                        try:
                            if bulk_store is None:
                                bulk_store = OpenTargetsBulkStore()
                            source_labels["ot_phenotype"] = bulk_store.get_phenotypes(
                                efo_id, limit=1, raise_on_error=True
                            )
                        except Exception as exc:
                            logger.debug(
                                "Local Open Targets phenotype lookup failed for %s: %s", did, exc
                            )

            coverage = _symptom_coverage_state(
                symptom_list, normalized_entry, source_availability or {}, source_labels
            )
            row: dict[str, Any] = {
                "disease_id": did,
                "name": disease.profile.name,
                "tier": tier,
                "strict_pass": strict_pass,
                "gene_count": counts["genes"],
                "drug_count": drug_count,
                "pathway_count": counts["pathways"],
                "symptom_count": symptom_count,
                "symptom_coverage": coverage,
                "config_gaps": [f for f, status in checks.items() if status != "ok"],
            }
            if include_symptom_source and symptom_count:
                row["symptom_source"] = "config"
            elif include_symptom_source:
                row["symptom_source"] = "none"
            per_disease.append(row)
            symptom_coverage_counts[coverage] += 1
        except Exception as exc:
            per_disease.append({"disease_id": did, "tier": "blocked", "error": str(exc)})

    aggregate: dict[str, Any] = aggregate_tiers(per_disease)
    aggregate["total"] = len(per_disease)
    aggregate["symptoms_populated"] = symptoms_populated
    aggregate["symptom_coverage"] = dict(symptom_coverage_counts)
    aggregate["L3_research_ready"] = aggregate.get("L3", 0)
    aggregate["L2_pipeline_ready"] = aggregate.get("L2", 0)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aggregate": aggregate,
        "per_disease": per_disease,
    }


def write_corpus_baseline(
    path: Path = DEFAULT_BASELINE_PATH, *, limit: Optional[int] = None
) -> dict[str, Any]:
    """Write corpus baseline metrics."""
    status = build_corpus_status(limit=limit, include_symptom_source=False)
    baseline = {
        "generated_at": status["generated_at"],
        "metrics": status["aggregate"],
        "tier_counts": {
            k: v for k, v in status["aggregate"].items() if k in ("L0", "L1", "L2", "L3", "blocked")
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    return baseline


def load_status_report(path: Path = DEFAULT_STATUS_PATH) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], payload) if isinstance(payload, dict) else {}
