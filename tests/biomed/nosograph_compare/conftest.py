from __future__ import annotations

import pytest

from med_research.biomed.identifiers import (
    claim_evidence_uuid,
    claim_uuid,
    entity_revision_uuid,
    entity_uuid,
    snapshot_uuid,
)
from med_research.biomed.imports.models import ImportBundle
from med_research.biomed.imports.service import ImportService
from med_research.biomed.models import (
    Claim,
    ClaimEvidence,
    Entity,
    EntityRevision,
    EntityType,
    EvidenceDirection,
    Predicate,
    ResourceSnapshot,
)
from med_research.biomed.repository import BiomedicalRepository

CONDITIONS = ("MONDO:0000001", "MONDO:0000002", "MONDO:0000003")


@pytest.fixture
def compare_v2_repository(tmp_path) -> BiomedicalRepository:
    repository = BiomedicalRepository(tmp_path / "compare-v2.sqlite3")
    repository.initialize()
    snapshot = ResourceSnapshot(
        id=snapshot_uuid("compare-v2-fixture", "1", "sha256:compare-v2-fixture"),
        resource_name="compare-v2-fixture",
        version="1",
        checksum="sha256:compare-v2-fixture",
        name="Compare V2 deterministic fixture",
        namespace_prefix="MONDO",
    )
    entities = [
        Entity(
            id=entity_uuid(EntityType.CONDITION, curie),
            primary_curie=curie,
            entity_type=EntityType.CONDITION,
            created_in_snapshot_id=snapshot.id,
        )
        for curie in CONDITIONS
    ]
    revisions = [
        EntityRevision(
            id=entity_revision_uuid(entity.id, snapshot.id),
            entity_id=entity.id,
            snapshot_id=snapshot.id,
            label=f"Condition {index}",
        )
        for index, entity in enumerate(entities, start=1)
    ]

    assertions: list[tuple[str, Predicate, str, bool]] = []

    def add(condition_indexes, predicate: Predicate, object_curie: str, *, negated=False):
        for index in condition_indexes:
            assertions.append((CONDITIONS[index], predicate, object_curie, negated))

    add((0, 1, 2), Predicate.HAS_PHENOTYPE, "HP:0000001")
    add((0, 1), Predicate.HAS_PHENOTYPE, "HP:0000002")
    add((0,), Predicate.HAS_PHENOTYPE, "HP:0000003")
    add((1,), Predicate.HAS_PHENOTYPE, "HP:0000004")
    add((2,), Predicate.HAS_PHENOTYPE, "HP:0000005")
    add((0,), Predicate.HAS_PHENOTYPE, "HP:0000006", negated=True)
    add((2,), Predicate.HAS_PHENOTYPE, "HP:0000006")
    add((0,), Predicate.HAS_PHENOTYPE, "HP:0000007")
    add((0,), Predicate.HAS_PHENOTYPE, "HP:0000007", negated=True)

    add((0, 1), Predicate.ASSOCIATED_WITH_GENE, "HGNC:1")
    add((0, 1), Predicate.ASSOCIATED_WITH_GENE, "HGNC:2")
    add((0, 1), Predicate.ASSOCIATED_WITH_GENE, "HGNC:3")
    add((0,), Predicate.ASSOCIATED_WITH_GENE, "HGNC:4")
    add((0,), Predicate.ASSOCIATED_WITH_GENE, "HGNC:5")
    add((0,), Predicate.ASSOCIATED_WITH_GENE, "HGNC:6")

    add((0, 1, 2), Predicate.INVOLVES_PATHWAY, "REACT:R-HSA-1")
    add((0,), Predicate.INVOLVES_PATHWAY, "REACT:R-HSA-2")
    add((0, 1, 2), Predicate.TREATED_BY, "DRUG:1")

    claims: list[Claim] = []
    evidence: list[ClaimEvidence] = []
    for number, (subject, predicate, object_curie, negated) in enumerate(assertions, start=1):
        qualifiers = {"negated": negated}
        claim = Claim(
            id=claim_uuid(subject, predicate, object_curie, qualifiers),
            subject_curie=subject,
            predicate=predicate,
            object_curie=object_curie,
            qualifiers=qualifiers,
        )
        claims.append(claim)
        evidence.append(
            ClaimEvidence(
                id=claim_evidence_uuid(
                    claim.id,
                    snapshot.id,
                    EvidenceDirection.SUPPORTING,
                    f"fixture-{number}",
                ),
                claim_id=claim.id,
                snapshot_id=snapshot.id,
                direction=EvidenceDirection.SUPPORTING,
                source_record_id=f"fixture-{number}",
            )
        )

    ImportService(repository).import_bundle(
        ImportBundle.build(
            snapshot,
            entities=entities,
            revisions=revisions,
            claims=claims,
            evidence=evidence,
        )
    )
    return repository
