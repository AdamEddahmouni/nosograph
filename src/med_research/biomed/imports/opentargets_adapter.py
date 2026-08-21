"""Open Targets bulk parquet → canonical ImportBundle adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from med_research.biomed.errors import BiomedicalValidationError
from med_research.biomed.identifiers import claim_evidence_uuid, claim_uuid, normalize_curie
from med_research.biomed.imports.models import ImportBundle, ImportWarning
from med_research.biomed.models import (
    Claim,
    ClaimEvidence,
    EvidenceDirection,
    Predicate,
    ResourcePolicy,
    ResourceSnapshot,
)
from med_research.diseases.bulk_store import OpenTargetsBulkStore, normalize_disease_id


class OpenTargetsImportAdapter:
    """Normalize Open Targets bulk parquet into gene/phenotype/intervention claims."""

    resource_name = "open_targets"
    supported_formats = ("parquet",)

    def parse_bulk(
        self,
        bulk_root: Path,
        policy: ResourcePolicy,
        *,
        version: str,
        mondo_mappings: Mapping[str, str] | None = None,
        min_association_score: float = 0.5,
    ) -> ImportBundle:
        store = OpenTargetsBulkStore(bulk_root=bulk_root, version=version)
        if not store.is_available():
            raise BiomedicalValidationError(
                f"Open Targets bulk data unavailable under {bulk_root / version}"
            )
        manifest_path = bulk_root.parent / "manifest.json"
        checksum = _bulk_checksum(manifest_path, bulk_root / version)
        snapshot = ResourceSnapshot(
            id=_snapshot_id(policy.resource_name, version, checksum),
            resource_name=policy.resource_name,
            version=version,
            checksum=checksum,
            name="Open Targets Platform",
            namespace_prefix="OT",
            source_url="https://platform.opentargets.org/",
            artifact_format="parquet",
            upstream_version=version,
            license_id=policy.license_id,
            license_url=policy.license_url,
            redistribution_policy=policy.redistribution_policy,
            importer_name="OpenTargetsImportAdapter",
            importer_version="1.0.0",
        )
        efo_to_mondo = _invert_mondo_efo_mappings(mondo_mappings or {})
        claims: list[Claim] = []
        evidence: list[ClaimEvidence] = []
        warnings: list[ImportWarning] = []

        for row in store._read_table("association_overall_direct"):
            disease_efo = normalize_disease_id(str(row.get("diseaseId") or ""))
            subject_curie = efo_to_mondo.get(disease_efo)
            if subject_curie is None:
                warnings.append(
                    ImportWarning(
                        code="unresolved_disease_mapping",
                        message=f"{disease_efo} has no exact MONDO join",
                        source_record_id=disease_efo,
                    )
                )
                continue
            score = float(row.get("score") or 0.0)
            if score < min_association_score:
                continue
            symbol = str(row.get("approvedSymbol") or row.get("targetId") or "").strip()
            if not symbol:
                continue
            object_curie = (
                normalize_curie(f"HGNC:{symbol}") if ":" not in symbol else normalize_curie(symbol)
            )
            qualifiers = {"association_score": score, "source": "open_targets"}
            claim = Claim(
                id=claim_uuid(
                    subject_curie, Predicate.ASSOCIATED_WITH_GENE, object_curie, qualifiers
                ),
                subject_curie=subject_curie,
                object_curie=object_curie,
                predicate=Predicate.ASSOCIATED_WITH_GENE,
                qualifiers=qualifiers,
            )
            claims.append(claim)
            source_record_id = f"{disease_efo}|{object_curie}|assoc"
            evidence.append(
                ClaimEvidence(
                    id=claim_evidence_uuid(
                        claim.id, snapshot.id, EvidenceDirection.SUPPORTING, source_record_id
                    ),
                    claim_id=claim.id,
                    snapshot_id=snapshot.id,
                    direction=EvidenceDirection.SUPPORTING,
                    source_record_id=source_record_id,
                    source_url=f"https://platform.opentargets.org/disease/{disease_efo}/associations",
                    evidence_type="association_score",
                    confidence=score,
                    confidence_score=score,
                    rationale=f"Open Targets association score {score:.3f}",
                    extraction_method="open_targets_bulk",
                    importer_version="1.0.0",
                    attributes={"score": score, "biotype": row.get("biotype")},
                )
            )

        for row in store._read_table("disease_phenotype"):
            disease_efo = normalize_disease_id(str(row.get("diseaseId") or ""))
            subject_curie = efo_to_mondo.get(disease_efo)
            if subject_curie is None:
                continue
            hp_id = normalize_curie(str(row.get("phenotypeId") or ""))
            frequency = row.get("frequency")
            qualifiers = {
                "frequency": float(frequency) if frequency is not None else None,
                "source": "open_targets",
            }
            claim = Claim(
                id=claim_uuid(subject_curie, Predicate.HAS_PHENOTYPE, hp_id, qualifiers),
                subject_curie=subject_curie,
                object_curie=hp_id,
                predicate=Predicate.HAS_PHENOTYPE,
                qualifiers=qualifiers,
            )
            claims.append(claim)
            source_record_id = f"{disease_efo}|{hp_id}|phenotype"
            evidence.append(
                ClaimEvidence(
                    id=claim_evidence_uuid(
                        claim.id, snapshot.id, EvidenceDirection.SUPPORTING, source_record_id
                    ),
                    claim_id=claim.id,
                    snapshot_id=snapshot.id,
                    direction=EvidenceDirection.SUPPORTING,
                    source_record_id=source_record_id,
                    source_url=f"https://platform.opentargets.org/disease/{disease_efo}",
                    evidence_type="disease_phenotype",
                    rationale="Open Targets disease-phenotype association",
                    extraction_method="open_targets_bulk",
                    importer_version="1.0.0",
                )
            )

        for row in store._read_table("known_drug"):
            disease_efo = normalize_disease_id(str(row.get("diseaseId") or ""))
            subject_curie = efo_to_mondo.get(disease_efo)
            if subject_curie is None:
                continue
            drug_name = str(row.get("drugName") or row.get("drugId") or "").strip()
            if not drug_name:
                continue
            object_curie = (
                normalize_curie(f"CHEMBL:{row.get('drugId')}")
                if row.get("drugId")
                else normalize_curie(f"DRUG:{drug_name}")
            )
            qualifiers = {
                "phase": int(row.get("phase")) if row.get("phase") is not None else None,
                "status": str(row.get("status") or ""),
                "mechanism": str(row.get("mechanism") or ""),
                "source": "open_targets",
            }
            claim = Claim(
                id=claim_uuid(subject_curie, Predicate.TREATED_BY, object_curie, qualifiers),
                subject_curie=subject_curie,
                object_curie=object_curie,
                predicate=Predicate.TREATED_BY,
                qualifiers=qualifiers,
            )
            claims.append(claim)
            source_record_id = f"{disease_efo}|{object_curie}|drug"
            evidence.append(
                ClaimEvidence(
                    id=claim_evidence_uuid(
                        claim.id, snapshot.id, EvidenceDirection.SUPPORTING, source_record_id
                    ),
                    claim_id=claim.id,
                    snapshot_id=snapshot.id,
                    direction=EvidenceDirection.SUPPORTING,
                    source_record_id=source_record_id,
                    source_url=f"https://platform.opentargets.org/disease/{disease_efo}/known-drugs",
                    evidence_type="known_drug",
                    rationale=str(row.get("mechanism") or "Open Targets known drug"),
                    extraction_method="open_targets_bulk",
                    importer_version="1.0.0",
                )
            )

        return ImportBundle.build(
            snapshot,
            claims=claims,
            evidence=evidence,
            warnings=warnings,
            metadata={"efo_mappings_used": len(efo_to_mondo), "version": version},
        )


def _invert_mondo_efo_mappings(mondo_mappings: Mapping[str, str]) -> dict[str, str]:
    """Map normalized EFO ids (EFO_0001370) to MONDO CURIEs."""
    inverted: dict[str, str] = {}
    for external, mondo in mondo_mappings.items():
        normalized_external = normalize_disease_id(external)
        inverted[normalized_external] = normalize_curie(mondo)
        if external.upper().startswith("EFO:"):
            inverted[normalize_disease_id(external.replace(":", "_"))] = normalize_curie(mondo)
    return inverted


def _bulk_checksum(manifest_path: Path, data_dir: Path) -> str:
    from med_research.biomed.imports.models import _artifact_checksum

    if manifest_path.is_file():
        return _artifact_checksum(manifest_path)
    digest_parts = sorted(str(path.relative_to(data_dir)) for path in data_dir.rglob("*.parquet"))
    from med_research.biomed.identifiers import fingerprint_json

    return f"sha256:{fingerprint_json({'files': digest_parts})}"


def _snapshot_id(resource_name: str, version: str, checksum: str) -> object:
    from med_research.biomed.identifiers import snapshot_uuid

    return snapshot_uuid(resource_name, version, checksum)
