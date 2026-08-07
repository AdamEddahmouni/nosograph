"""Strict, serializable coverage contracts for disease-aware analyses.

Coverage describes whether a module has enough disease-specific curated inputs
for an interpretable run. It is deliberately separate from evidence provenance:
source retrieval can succeed while a module remains unsupported by curation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

CoverageLevel = Literal["full", "partial", "unsupported"]
CoverageStatus = Literal["ready", "limited_coverage", "blocked"]


@dataclass(frozen=True)
class ModuleCoverage:
    """Machine-readable coverage status shared by pipeline/API/report layers."""

    disease_id: str
    module: str
    level: CoverageLevel
    status: CoverageStatus
    curated_inputs: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)
    inferred_inputs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    @property
    def is_runnable(self) -> bool:
        return self.status != "blocked"

    def to_dict(self) -> dict:
        return asdict(self)


def _is_empty(value) -> bool:
    """Treat empty collections/text as unavailable; preserve numeric zero."""
    if value is None:
        return True
    if isinstance(value, (str, bytes, list, tuple, set, dict)):
        return not value
    return False


def _input_value(disease, name: str):
    """Resolve a named curated input through the Disease boundary."""
    accessors = {
        "symptoms": disease.get_symptoms,
        "pubmed_queries": lambda: disease.config.get("PUBMED_QUERIES", []),
        "gwas_search_terms": disease.get_gwas_search_terms,
        "trial_query": disease.get_trial_query,
        "car_t_scores": disease.get_car_t_scores,
        "safety_risk": disease.get_disease_risk_config,
        "adverse_event_profile": disease.get_adverse_event_profile,
        "screening_profile": disease.get_screening_profile,
        "pathway_keywords": disease.get_pathway_keywords,
        "genes": disease.load_genes,
        "drugs": disease.load_drugs,
        "pathways": disease.load_pathways,
        "relationships": disease.load_relationships,
    }
    if name in accessors:
        value = accessors[name]()
        if name in {"genes", "drugs", "pathways", "relationships"}:
            return value.get(name, [])
        return value
    if name in {"profile", "profile.json"}:
        return disease.profile
    if name in {"data_files", "core"}:
        return True
    return disease.config.get(name.upper(), disease.config.get(name))


def coverage_for_disease(disease_id: str) -> ModuleCoverage:
    """Validate the five standard disease data files and basic JSON shapes."""
    from med_research.diseases.base import Disease

    try:
        disease = Disease(disease_id)
    except ValueError:
        return ModuleCoverage(
            disease_id=disease_id,
            module="core",
            level="unsupported",
            status="blocked",
            missing_inputs=["disease"],
            limitations=[f"Disease '{disease_id}' is not registered; no analysis was run."],
        )
    required_files = ("profile", "genes", "drugs", "pathways", "relationships")
    missing = [
        name
        for name in required_files
        if not (disease.data_dir / f"{name}.json").is_file()
    ]
    warnings: list[str] = []
    if not missing:
        for name in ("genes", "drugs", "pathways", "relationships"):
            try:
                payload = _input_value(disease, name)
            except (OSError, ValueError, TypeError, KeyError):
                missing.append(name)
                continue
            if not isinstance(payload, list):
                missing.append(name)
        try:
            relationships = disease.load_relationships().get("relationships", [])
            if not relationships:
                warnings.append("The knowledge graph has no relationships to analyze.")
        except (OSError, ValueError, TypeError, KeyError):
            if "relationships" not in missing:
                missing.append("relationships")

    if missing:
        return ModuleCoverage(
            disease_id=disease_id,
            module="core",
            level="unsupported",
            status="blocked",
            missing_inputs=sorted(set(missing)),
            warnings=warnings,
            limitations=[
                "Core disease data is incomplete; run disease scaffolding or refresh before analysis."
            ],
        )
    level: CoverageLevel = "partial" if warnings else "full"
    status: CoverageStatus = "limited_coverage" if warnings else "ready"
    return ModuleCoverage(
        disease_id=disease_id,
        module="core",
        level=level,
        status=status,
        curated_inputs=list(required_files),
        warnings=warnings,
    )


def module_coverage(
    disease_id: str,
    module: str,
    required_inputs: tuple[str, ...] = (),
    optional_inputs: tuple[str, ...] = (),
) -> ModuleCoverage:
    """Return strict readiness metadata for one disease/module boundary."""
    from med_research.diseases.base import Disease

    try:
        disease = Disease(disease_id)
    except ValueError:
        return ModuleCoverage(
            disease_id=disease_id,
            module=module,
            level="unsupported",
            status="blocked",
            missing_inputs=["disease"],
            limitations=[f"Disease '{disease_id}' is not registered; no analysis was run."],
        )
    core = coverage_for_disease(disease_id)
    if not core.is_runnable:
        return ModuleCoverage(
            disease_id=disease_id,
            module=module,
            level="unsupported",
            status="blocked",
            missing_inputs=list(core.missing_inputs),
            warnings=list(core.warnings),
            limitations=list(core.limitations),
        )

    missing: list[str] = []
    curated: list[str] = []
    for name in required_inputs:
        try:
            value = _input_value(disease, name)
        except (OSError, ValueError, TypeError, KeyError):
            value = None
        if _is_empty(value):
            missing.append(name)
        else:
            curated.append(name)

    optional_missing: list[str] = []
    for name in optional_inputs:
        try:
            value = _input_value(disease, name)
        except (OSError, ValueError, TypeError, KeyError):
            value = None
        if _is_empty(value):
            optional_missing.append(name)
        else:
            curated.append(name)

    if "adverse_event_profile" in required_inputs and not missing:
        try:
            payload = _input_value(disease, "adverse_event_profile")
            profiles = payload.get("profiles") if isinstance(payload, dict) else None
            catalog = {
                str(item.get("id"))
                for item in disease.load_drugs().get("drugs", [])
                if item.get("id")
            }
            profile_ids = {
                str(item.get("drug_id"))
                for item in profiles
                if isinstance(item, dict) and item.get("drug_id")
            } if isinstance(profiles, list) else set()
            invalid = sorted(profile_ids - catalog)
            if not isinstance(payload, dict) or not payload.get("source"):
                raise ValueError("profile source is missing")
            if not payload.get("limitations"):
                raise ValueError("profile limitations are missing")
            required_defaults = {
                "common_ae", "severe_ae", "disease_overlap_ae",
                "severity_burden", "chronic_use_safety", "disease_specific_risk",
                "monitoring_required", "evidence_grade",
            }
            defaults = payload.get("default_profile", {})
            if not isinstance(profiles, list) or invalid:
                detail = f"unknown drugs: {', '.join(invalid)}" if invalid else "profiles must be a list"
                raise ValueError(detail)
            if disease_id != "sle" and (
                not isinstance(defaults, dict) or not required_defaults <= set(defaults)
            ):
                missing_defaults = sorted(required_defaults - set(defaults or {}))
                raise ValueError(
                    "default_profile is incomplete: " + ", ".join(missing_defaults)
                )
            if disease_id != "sle":
                if not isinstance(defaults, dict):
                    raise ValueError("default_profile must be an object")
                for field in ("severity_burden", "chronic_use_safety", "disease_specific_risk"):
                    value = defaults.get(field)
                    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 10:
                        raise ValueError(f"invalid default {field}")
            list_fields = ("common_ae", "severe_ae", "disease_overlap_ae", "black_box_warnings")
            for entry in profiles:
                if not isinstance(entry, dict) or not entry.get("drug_id"):
                    raise ValueError("profile entries require drug_id")
                merged = {**defaults, **entry}
                for field in ("severity_burden", "chronic_use_safety", "disease_specific_risk"):
                    value = merged.get(field)
                    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 10:
                        raise ValueError(f"invalid {field}")
                for field in list_fields:
                    if not isinstance(merged.get(field, []), list):
                        raise ValueError(f"invalid {field}")
                if not isinstance(merged.get("monitoring_required", ""), str):
                    raise ValueError("invalid monitoring_required")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return ModuleCoverage(
                disease_id=disease_id,
                module=module,
                level="unsupported",
                status="blocked",
                curated_inputs=curated,
                missing_inputs=["adverse_event_profile"],
                limitations=[f"Safety profile is invalid: {exc}"],
            )

    if "screening_profile" in required_inputs and not missing:
        try:
            from med_research.pipeline.virtual_screening.screening_strategy import (
                strategy_for_disease,
            )

            strategy_for_disease(disease_id)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return ModuleCoverage(
                disease_id=disease_id,
                module=module,
                level="unsupported",
                status="blocked",
                curated_inputs=curated,
                missing_inputs=["screening_profile"],
                limitations=[f"Screening strategy is invalid: {exc}"],
            )

    if missing:
        return ModuleCoverage(
            disease_id=disease_id,
            module=module,
            level="unsupported",
            status="blocked",
            curated_inputs=curated,
            missing_inputs=missing,
            limitations=[
                f"Required curated inputs are missing: {', '.join(missing)}."
            ],
        )
    if optional_missing:
        return ModuleCoverage(
            disease_id=disease_id,
            module=module,
            level="partial",
            status="limited_coverage",
            curated_inputs=curated,
            missing_inputs=optional_missing,
            warnings=[
                "Optional curated inputs are unavailable: "
                + ", ".join(optional_missing)
                + "."
            ],
        )
    return ModuleCoverage(
        disease_id=disease_id,
        module=module,
        level="full",
        status="ready",
        curated_inputs=curated,
    )
