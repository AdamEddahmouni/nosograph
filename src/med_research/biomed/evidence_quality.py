"""Structured evidence quality dimensions (ADR-001).

No single opaque confidence score — dimensions default to ``unknown`` when metadata
is absent rather than implying low quality.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from med_research.biomed.models import ClaimEvidence

SpeciesContextLiteral = Literal["human", "animal", "in_vitro", "computational", "unknown"]
StudyDesignLiteral = Literal[
    "rct",
    "cohort",
    "case_control",
    "case_series",
    "review",
    "unknown",
]
ReplicationLiteral = Literal["replicated", "single_study", "unknown"]
EffectDirectionLiteral = Literal["positive", "negative", "null", "mixed", "unknown"]
StatisticalQualityLiteral = Literal["high", "medium", "low", "unknown"]
DirectnessLiteral = Literal["direct", "indirect", "unknown"]
SourceQualityLiteral = Literal["curated", "imported", "generated", "unknown"]
HumanReviewLiteral = Literal["none", "community", "expert", "unknown"]
ContradictionBurdenLiteral = Literal["none", "some", "high", "unknown"]
OriginClassLiteral = Literal[
    "SOURCE_DERIVED",
    "HUMAN_CURATED",
    "COMPUTATIONAL_INFERENCE",
    "LLM_EXTRACTED",
    "UNKNOWN_ORIGIN_CLASS",
]
SampleSizeContextLiteral = Literal["known", "unknown", "not_available"]


class EvidenceQuality(BaseModel):
    model_config = ConfigDict(frozen=True)

    species_context: SpeciesContextLiteral = "unknown"
    study_design: StudyDesignLiteral = "unknown"
    sample_size: int | None = None
    sample_size_context: SampleSizeContextLiteral = "unknown"
    replication: ReplicationLiteral = "unknown"
    effect_direction: EffectDirectionLiteral = "unknown"
    statistical_quality: StatisticalQualityLiteral = "unknown"
    directness: DirectnessLiteral = "unknown"
    source_quality: SourceQualityLiteral = "unknown"
    recency: str = ""
    human_review: HumanReviewLiteral = "unknown"
    contradiction_burden: ContradictionBurdenLiteral = "unknown"
    origin_class: OriginClassLiteral = "UNKNOWN_ORIGIN_CLASS"
    limitations: list[str] = Field(default_factory=list)


_ANIMAL_HINTS = re.compile(
    r"\b(mouse|mice|murine|rat|rats|rodent|animal|canine|porcine|zebrafish)\b",
    re.IGNORECASE,
)
_HUMAN_HINTS = re.compile(
    r"\b(human|patient|patients|clinical|cohort|pediatric|adult)\b",
    re.IGNORECASE,
)
_IN_VITRO_HINTS = re.compile(r"\b(in vitro|cell line|cell-line|culture)\b", re.IGNORECASE)
_COMPUTATIONAL_HINTS = re.compile(
    r"\b(computational|in silico|predicted|model|simulation)\b",
    re.IGNORECASE,
)


def _infer_species_context(evidence: ClaimEvidence) -> SpeciesContextLiteral:
    haystack = " ".join(
        filter(
            None,
            [
                evidence.population or "",
                evidence.evidence_type or "",
                evidence.rationale or "",
                evidence.snippet or "",
            ],
        )
    )
    if not haystack.strip():
        return "unknown"
    if _HUMAN_HINTS.search(haystack):
        return "human"
    if _ANIMAL_HINTS.search(haystack):
        return "animal"
    if _IN_VITRO_HINTS.search(haystack):
        return "in_vitro"
    if _COMPUTATIONAL_HINTS.search(haystack):
        return "computational"
    return "unknown"


def _infer_study_design(evidence: ClaimEvidence) -> StudyDesignLiteral:
    haystack = (evidence.evidence_type or "").lower()
    if not haystack:
        return "unknown"
    if "rct" in haystack or "randomized" in haystack:
        return "rct"
    if "cohort" in haystack:
        return "cohort"
    if "case-control" in haystack or "case control" in haystack:
        return "case_control"
    if "case series" in haystack or "case_series" in haystack:
        return "case_series"
    if "review" in haystack or "meta" in haystack:
        return "review"
    return "unknown"


def _infer_origin_class(evidence: ClaimEvidence) -> OriginClassLiteral:
    method = (evidence.extraction_method or "").lower()
    if evidence.curator:
        return "HUMAN_CURATED"
    if "llm" in method or "gpt" in method or "extract" in method and "llm" in method:
        return "LLM_EXTRACTED"
    if "infer" in method or "compute" in method or "predict" in method:
        return "COMPUTATIONAL_INFERENCE"
    if method or evidence.importer_version:
        return "SOURCE_DERIVED"
    return "UNKNOWN_ORIGIN_CLASS"


def _infer_source_quality(evidence: ClaimEvidence) -> SourceQualityLiteral:
    if evidence.curator:
        return "curated"
    method = (evidence.extraction_method or "").lower()
    if "llm" in method or "generate" in method or "infer" in method:
        return "generated"
    if method or evidence.importer_version:
        return "imported"
    return "unknown"


def _infer_human_review(evidence: ClaimEvidence) -> HumanReviewLiteral:
    if not evidence.curator:
        return "none"
    curator = evidence.curator.lower()
    if "expert" in curator or "curator" in curator:
        return "expert"
    return "community"


def _infer_statistical_quality(evidence: ClaimEvidence) -> StatisticalQualityLiteral:
    """Do not map confidence scores to statistical quality — they measure different things."""
    haystack = " ".join(
        filter(
            None,
            [
                evidence.evidence_type or "",
                evidence.rationale or "",
                evidence.snippet or "",
            ],
        )
    ).lower()
    if not haystack.strip():
        return "unknown"
    if re.search(r"\bp\s*[<=>]\s*0\.\d+", haystack) or "confidence interval" in haystack:
        return "high"
    if "statistically significant" in haystack or "significant association" in haystack:
        return "medium"
    return "unknown"


def derive_evidence_quality(evidence: ClaimEvidence) -> EvidenceQuality:
    """Derive structured quality from persisted evidence metadata."""
    sample_size = evidence.sample_size
    sample_size_context: SampleSizeContextLiteral
    if sample_size is not None and sample_size > 0:
        sample_size_context = "known"
    elif evidence.population and "unknown" in evidence.population.lower():
        sample_size_context = "not_available"
    else:
        sample_size_context = "unknown"

    return EvidenceQuality(
        species_context=_infer_species_context(evidence),
        study_design=_infer_study_design(evidence),
        sample_size=sample_size,
        sample_size_context=sample_size_context,
        replication="unknown",
        effect_direction="unknown",
        statistical_quality=_infer_statistical_quality(evidence),
        directness="unknown",
        source_quality=_infer_source_quality(evidence),
        recency=evidence.publication_date or "",
        human_review=_infer_human_review(evidence),
        contradiction_burden="unknown",
        origin_class=_infer_origin_class(evidence),
        limitations=list(evidence.limitations),
    )
