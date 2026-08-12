"""Parity reporting for legacy disease migration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from med_research.biomed.identifiers import snapshot_uuid
from med_research.biomed.legacy.adapter import LegacyMigrationAdapter
from med_research.biomed.legacy.manifest import resolve_mondo_curie
from med_research.biomed.legacy.projector import project_disease
from med_research.diseases.base import Disease


@dataclass(frozen=True)
class ParityCount:
    source_count: int
    imported_count: int


@dataclass(frozen=True)
class ParityException:
    code: str
    message: str
    source_record_id: str = ""


@dataclass
class ParityReport:
    disease_id: str
    mondo_curie: str
    genes: ParityCount
    drugs: ParityCount
    pathways: ParityCount
    relationships: ParityCount
    biomarkers: ParityCount
    exceptions: list[ParityException] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "disease_id": self.disease_id,
            "mondo_curie": self.mondo_curie,
            "genes": {
                "source_count": self.genes.source_count,
                "imported_count": self.genes.imported_count,
            },
            "drugs": {
                "source_count": self.drugs.source_count,
                "imported_count": self.drugs.imported_count,
            },
            "pathways": {
                "source_count": self.pathways.source_count,
                "imported_count": self.pathways.imported_count,
            },
            "relationships": {
                "source_count": self.relationships.source_count,
                "imported_count": self.relationships.imported_count,
            },
            "biomarkers": {
                "source_count": self.biomarkers.source_count,
                "imported_count": self.biomarkers.imported_count,
            },
            "exceptions": [
                {
                    "code": item.code,
                    "message": item.message,
                    "source_record_id": item.source_record_id,
                }
                for item in self.exceptions
            ],
        }


def build_parity_report(disease_id: str) -> ParityReport:
    mondo_curie = resolve_mondo_curie(disease_id)
    disease = Disease(disease_id)
    snapshot_id = snapshot_uuid("legacy-curated", "parity", disease_id)
    projection = project_disease(disease_id, snapshot_id=snapshot_id)

    source_genes = len(disease.load_genes().get("genes", []))
    source_drugs = len(disease.load_drugs().get("drugs", []))
    source_pathways = len(disease.load_pathways().get("pathways", []))
    source_relationships = len(disease.load_relationships().get("relationships", []))
    source_biomarkers = len(disease.profile.hallmark_markers)

    imported_genes = sum(1 for entity in projection.entities if entity.entity_type.value == "gene")
    imported_drugs = sum(
        1 for entity in projection.entities if entity.entity_type.value == "intervention"
    )
    imported_pathways = sum(
        1 for entity in projection.entities if entity.entity_type.value == "pathway"
    )
    imported_biomarkers = sum(
        1 for entity in projection.entities if entity.entity_type.value == "biomarker"
    )
    imported_relationships = len(projection.claims) - imported_biomarkers

    exceptions = [
        ParityException(
            code=warning.code,
            message=warning.message,
            source_record_id=warning.source_record_id,
        )
        for warning in projection.warnings
    ]

    return ParityReport(
        disease_id=disease_id,
        mondo_curie=mondo_curie,
        genes=ParityCount(source_genes, imported_genes),
        drugs=ParityCount(source_drugs, imported_drugs),
        pathways=ParityCount(source_pathways, imported_pathways),
        relationships=ParityCount(source_relationships, imported_relationships),
        biomarkers=ParityCount(source_biomarkers, imported_biomarkers),
        exceptions=exceptions,
    )


def build_bundle_parity_reports(disease_ids: list[str] | None = None) -> list[ParityReport]:
    adapter = LegacyMigrationAdapter()
    bundle = adapter.build_bundle(disease_ids)
    reports: list[ParityReport] = []
    for entry in bundle.metadata.get("diseases", []):
        disease_id = str(entry["legacy_id"])
        report = build_parity_report(disease_id)
        reports.append(report)
    return reports
