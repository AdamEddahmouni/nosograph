from __future__ import annotations

import pytest

from med_research.biomed.identifiers import (
    claim_uuid,
    entity_revision_uuid,
    entity_uuid,
    mapping_uuid,
    snapshot_uuid,
)
from med_research.biomed.models import (
    Claim,
    ClaimEvidence,
    Entity,
    EntityMapping,
    EntityRevision,
    EntityType,
    EvidenceDirection,
    MappingKind,
    Predicate,
    ResearchRunCreate,
    ResourceSnapshot,
)
from med_research.biomed.repository import BiomedicalRepository


@pytest.fixture
def repository(tmp_path) -> BiomedicalRepository:
    repo = BiomedicalRepository(tmp_path / "biomedical.sqlite3")
    repo.initialize()
    return repo


@pytest.fixture
def mondo_snapshot() -> ResourceSnapshot:
    checksum = "sha256:mondo-fixture"
    snapshot_id = snapshot_uuid("mondo", "2024-01-01", checksum)
    return ResourceSnapshot(
        id=snapshot_id,
        resource_name="mondo",
        version="2024-01-01",
        checksum=checksum,
        name="Mondo Disease Ontology",
        namespace_prefix="MONDO",
        upstream_version="2024-01-01",
    )


@pytest.fixture
def sle_entity(mondo_snapshot: ResourceSnapshot) -> Entity:
    return Entity(
        id=entity_uuid(EntityType.CONDITION, "MONDO:0007915"),
        primary_curie="MONDO:0007915",
        entity_type=EntityType.CONDITION,
        created_in_snapshot_id=mondo_snapshot.id,
    )


@pytest.fixture
def sle_revision(mondo_snapshot: ResourceSnapshot, sle_entity: Entity) -> EntityRevision:
    return EntityRevision(
        id=entity_revision_uuid(sle_entity.id, mondo_snapshot.id),
        entity_id=sle_entity.id,
        snapshot_id=mondo_snapshot.id,
        label="systemic lupus erythematosus",
        synonyms=["SLE", "lupus"],
    )


@pytest.fixture
def exact_mapping(mondo_snapshot: ResourceSnapshot) -> EntityMapping:
    return EntityMapping(
        id=mapping_uuid("MONDO:0007915", "OMIM:152700", MappingKind.EXACT, mondo_snapshot.id),
        subject_curie="MONDO:0007915",
        object_curie="OMIM:152700",
        relation=MappingKind.EXACT,
        snapshot_id=mondo_snapshot.id,
        source_record_id="xref-1",
    )


@pytest.fixture
def close_mapping(mondo_snapshot: ResourceSnapshot) -> EntityMapping:
    return EntityMapping(
        id=mapping_uuid("MONDO:0007915", "DOID:9074", MappingKind.CLOSE, mondo_snapshot.id),
        subject_curie="MONDO:0007915",
        object_curie="DOID:9074",
        relation=MappingKind.CLOSE,
        snapshot_id=mondo_snapshot.id,
        source_record_id="xref-2",
    )


@pytest.fixture
def claim(mondo_snapshot: ResourceSnapshot) -> Claim:
    return Claim(
        id=claim_uuid("MONDO:0007915", Predicate.HAS_PHENOTYPE, "HP:0001945", {"negated": False}),
        subject_curie="MONDO:0007915",
        object_curie="HP:0001945",
        predicate=Predicate.HAS_PHENOTYPE,
        qualifiers={"negated": False},
    )


@pytest.fixture
def support(mondo_snapshot: ResourceSnapshot, claim: Claim) -> ClaimEvidence:
    from med_research.biomed.identifiers import claim_evidence_uuid

    return ClaimEvidence(
        id=claim_evidence_uuid(claim.id, mondo_snapshot.id, EvidenceDirection.SUPPORTING, "hpoa-1"),
        claim_id=claim.id,
        snapshot_id=mondo_snapshot.id,
        direction=EvidenceDirection.SUPPORTING,
        source_record_id="hpoa-1",
    )


@pytest.fixture
def contradiction(mondo_snapshot: ResourceSnapshot, claim: Claim) -> ClaimEvidence:
    from med_research.biomed.identifiers import claim_evidence_uuid

    return ClaimEvidence(
        id=claim_evidence_uuid(
            claim.id, mondo_snapshot.id, EvidenceDirection.CONTRADICTORY, "hpoa-2"
        ),
        claim_id=claim.id,
        snapshot_id=mondo_snapshot.id,
        direction=EvidenceDirection.CONTRADICTORY,
        source_record_id="hpoa-2",
    )


@pytest.fixture
def run_create(mondo_snapshot: ResourceSnapshot) -> ResearchRunCreate:
    return ResearchRunCreate(
        run_type="unit-test",
        algorithm_id="test-algorithm",
        algorithm_version="1.0.0",
        software_version="2.0.0",
        parameters={"threshold": 0.5},
        snapshot_ids=[mondo_snapshot.id],
        claim_ids=[],
        input_query="MONDO:0007915",
    )
