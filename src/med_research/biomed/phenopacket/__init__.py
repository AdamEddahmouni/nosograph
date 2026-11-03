"""Experimental disease-level phenotype evidence export.

This package maps NosoGraph's disease-level phenotype evidence onto a
Phenopacket-*aligned* JSON bundle. It is deliberately not a patient
Phenopacket: NosoGraph holds no individual observations, and the export never
invents demographics, measurements, biospecimens or clinical findings.

Public API::

    build_bundle(payload)          -> PhenotypeEvidenceBundle
    dumps_bundle(bundle)           -> canonical JSON string
    write_bundle(path, bundle)     -> Path
    export_bundle(payload, path=)  -> canonical JSON string

Status: EXPERIMENTAL. See ``docs/using/phenopacket-export.md``.
"""

from __future__ import annotations

from med_research.biomed.phenopacket.export import (
    PhenopacketExportError,
    build_bundle,
    dumps_bundle,
    export_bundle,
    write_bundle,
)
from med_research.biomed.phenopacket.models import (
    BUNDLE_SCHEMA_VERSION,
    DISCLAIMER,
    NOT_RECORDED,
    PHENOPACKET_ALIGNMENT,
    DiseaseReference,
    EvidenceSourceInput,
    EvidenceSourceRef,
    ExportScope,
    PhenotypeAnnotation,
    PhenotypeEvidenceBundle,
    PhenotypeEvidenceBundleInput,
    PhenotypeEvidenceInput,
    ProvenanceSummary,
)

__all__ = [
    "BUNDLE_SCHEMA_VERSION",
    "DISCLAIMER",
    "NOT_RECORDED",
    "PHENOPACKET_ALIGNMENT",
    "DiseaseReference",
    "EvidenceSourceInput",
    "EvidenceSourceRef",
    "ExportScope",
    "PhenopacketExportError",
    "PhenotypeAnnotation",
    "PhenotypeEvidenceBundle",
    "PhenotypeEvidenceBundleInput",
    "PhenotypeEvidenceInput",
    "ProvenanceSummary",
    "build_bundle",
    "dumps_bundle",
    "export_bundle",
    "write_bundle",
]
