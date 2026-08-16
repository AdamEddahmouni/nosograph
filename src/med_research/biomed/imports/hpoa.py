"""HPO disease-phenotype annotation import adapter."""

from __future__ import annotations

import csv
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
)


class HpoAnnotationAdapter:
    resource_name = "hpoa"
    supported_formats = ("tsv",)

    def parse(
        self,
        path: Path,
        policy: ResourcePolicy,
        *,
        mondo_mappings: Mapping[str, str] | None = None,
        **kwargs: object,
    ) -> ImportBundle:
        mapping_table = dict(mondo_mappings or {})
        bundle = ImportBundle.from_artifact(
            policy=policy,
            artifact_path=path,
            upstream_version=_upstream_version(path),
            artifact_format="tsv",
            namespace_prefix="HPOA",
            name="HPO Disease Annotations",
        )
        return self._populate(bundle, path, mapping_table)

    def _populate(
        self,
        bundle: ImportBundle,
        path: Path,
        mondo_mappings: Mapping[str, str],
    ) -> ImportBundle:
        snapshot_id = bundle.snapshot.id
        claims: list[Claim] = []
        evidence: list[ClaimEvidence] = []
        warnings: list[ImportWarning] = []

        with path.open(encoding="utf-8", newline="") as handle:
            data_lines = (line for line in handle if not line.startswith("#"))
            reader = csv.DictReader(data_lines, delimiter="\t")
            if reader.fieldnames is None:
                raise BiomedicalValidationError("HPOA artifact is missing a header row")
            for index, row in enumerate(reader, start=2):
                raw_disease_id = str(row.get("disease_id") or row.get("database_id") or "").strip()
                raw_hp_id = str(row.get("hp_id") or row.get("hpo_id") or "").strip()
                if not raw_disease_id or not raw_hp_id:
                    warnings.append(
                        ImportWarning(
                            code="skipped_row",
                            message=f"Row {index} is missing disease_id or hp_id",
                            source_record_id=str(index),
                        )
                    )
                    continue
                disease_id = normalize_curie(raw_disease_id)
                hp_id = normalize_curie(raw_hp_id)
                subject_curie = mondo_mappings.get(disease_id)
                if subject_curie is None:
                    warnings.append(
                        ImportWarning(
                            code="unresolved_disease_mapping",
                            message=f"{disease_id} has no exact Mondo join",
                            source_record_id=disease_id,
                        )
                    )
                    continue
                negated = str(row.get("qualifier", "")).strip().upper() == "NOT"
                qualifiers = {
                    "frequency": str(row.get("frequency", "")).strip(),
                    "onset": str(row.get("onset", "")).strip(),
                    "modifier": str(row.get("modifier", "")).strip(),
                    "sex": str(row.get("sex", "")).strip(),
                    "negated": negated,
                }
                claim = Claim(
                    id=claim_uuid(subject_curie, Predicate.HAS_PHENOTYPE, hp_id, qualifiers),
                    subject_curie=subject_curie,
                    object_curie=hp_id,
                    predicate=Predicate.HAS_PHENOTYPE,
                    qualifiers=qualifiers,
                )
                claims.append(claim)
                source_record_id = f"{disease_id}|{hp_id}|{index}"
                direction = (
                    EvidenceDirection.CONTRADICTORY if negated else EvidenceDirection.SUPPORTING
                )
                evidence.append(
                    ClaimEvidence(
                        id=claim_evidence_uuid(claim.id, snapshot_id, direction, source_record_id),
                        claim_id=claim.id,
                        snapshot_id=snapshot_id,
                        direction=direction,
                        source_record_id=source_record_id,
                        source_evidence_code=str(row.get("evidence", "")).strip(),
                        curator=str(row.get("biocuration", "")).strip(),
                        extraction_method="hpoa-import",
                    )
                )

        return ImportBundle.build(
            bundle.snapshot,
            claims=claims,
            evidence=evidence,
            warnings=warnings,
        )


def _upstream_version(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_mtime_ns}"
