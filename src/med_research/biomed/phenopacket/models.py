"""Models for the experimental disease-level phenotype evidence export.

NosoGraph records **disease-level evidence**: an association such as
``MONDO:0007915 HAS_PHENOTYPE HP:0001250`` asserted by some upstream source. It
does not record observations of an individual person, so this package
deliberately does *not* emit a patient Phenopacket. The bundle below describes
disease-level phenotype evidence and keeps provenance and evidence direction
attached to every annotation.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from med_research.biomed.models import EvidenceDirection

NOT_RECORDED = "NOT_RECORDED"
"""Explicit encoding for data NosoGraph does not hold.

``NOT_RECORDED`` means "no assertion exists in the input", never "known to be
absent". It is a string rather than ``null`` or ``0`` so that a missing value
can never be mistaken for an empty measurement or a negative finding.
"""

BUNDLE_SCHEMA_VERSION = "0.1.0"
"""Version of the NosoGraph bundle layout, independent of Phenopacket Schema."""

PHENOPACKET_ALIGNMENT = (
    "aligned to Phenopacket Schema 2.x concepts; not a conformant Phenopacket, "
    "and not derived from an individual"
)
"""Honest statement of the relationship to the Phenopacket Schema.

This is an alignment note, never a compliance claim.
"""

DISCLAIMER = (
    "Experimental disease-level phenotype evidence summary for research use. "
    "Not a patient Phenopacket: it contains no observations of an individual, "
    "no demographics, no biospecimens and no clinical findings. Not for "
    "clinical decision-making."
)


class ExportScope(str, Enum):
    """What the exported evidence actually describes."""

    DISEASE_EVIDENCE = "disease_evidence"


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------


class EvidenceSourceInput(BaseModel):
    """One upstream source reference supporting a phenotype assertion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str = ""
    source_record_id: str = ""
    source_url: str | None = None
    version: str = ""
    checksum: str = ""
    attribution: str = ""


class PhenotypeEvidenceInput(BaseModel):
    """One disease-level phenotype assertion supplied by the caller."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hpo_id: str = ""
    hpo_label: str | None = None
    direction: EvidenceDirection | None = None
    frequency: str | None = None
    notes: str | None = None
    sources: list[EvidenceSourceInput] = Field(default_factory=list)


class PhenotypeEvidenceBundleInput(BaseModel):
    """Complete input for one export: a disease and its phenotype evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    disease_curie: str = ""
    disease_label: str | None = None
    phenotypes: list[PhenotypeEvidenceInput] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class DiseaseReference(BaseModel):
    """The disease the evidence is scoped to."""

    model_config = ConfigDict(frozen=True)

    curie: str
    label: str = NOT_RECORDED


class EvidenceSourceRef(BaseModel):
    """A source reference serialized into the bundle."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    source_record_id: str = NOT_RECORDED
    source_url: str | None = None
    version: str = NOT_RECORDED
    checksum: str = NOT_RECORDED
    attribution: str = NOT_RECORDED


class PhenotypeAnnotation(BaseModel):
    """One disease-level phenotype annotation with its evidence.

    ``direction`` is carried verbatim. Contradictory evidence is *not* mapped
    onto the Phenopacket ``excluded`` flag, because "a source argues against
    this disease-phenotype association" and "the phenotype was excluded in this
    individual" are different statements.
    """

    model_config = ConfigDict(frozen=True)

    hpo_id: str
    hpo_label: str = NOT_RECORDED
    direction: EvidenceDirection
    frequency: str = NOT_RECORDED
    provenance: list[EvidenceSourceRef] = Field(default_factory=list)
    notes: str | None = None


class ProvenanceSummary(BaseModel):
    """Non-identifying summary of the sources used by one bundle."""

    model_config = ConfigDict(frozen=True)

    source_count: int
    source_ids: list[str] = Field(default_factory=list)
    annotated_feature_count: int = 0


class PhenotypeEvidenceBundle(BaseModel):
    """Deterministically serializable disease-level evidence export.

    The bundle intentionally carries no wall-clock timestamp: identical inputs
    must serialize to identical bytes. Packaging layers that need an export
    time should record it outside this payload.
    """

    model_config = ConfigDict(frozen=True)

    bundle_schema_version: str = BUNDLE_SCHEMA_VERSION
    phenopacket_alignment: str = PHENOPACKET_ALIGNMENT
    export_scope: ExportScope = ExportScope.DISEASE_EVIDENCE
    disease: DiseaseReference
    phenotypic_features: list[PhenotypeAnnotation] = Field(default_factory=list)
    provenance_summary: ProvenanceSummary
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER
