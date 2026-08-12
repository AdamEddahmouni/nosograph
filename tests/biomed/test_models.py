import uuid
from datetime import datetime, timezone

from med_research.biomed.errors import (
    BiomedicalError,
    BiomedicalValidationError,
    RunTransitionError,
    SnapshotConflictError,
)
from med_research.biomed.models import (
    Claim,
    Entity,
    EntityType,
    Predicate,
    ResearchRun,
    RunStatus,
)


def test_entity_creation_and_defaults() -> None:
    entity = Entity(
        id=uuid.uuid4(),
        primary_curie="MONDO:0007915",
        entity_type=EntityType.CONDITION,
        canonical_name="Systemic Lupus Erythematosus",
    )
    assert entity.primary_curie == "MONDO:0007915"
    assert entity.entity_type == EntityType.CONDITION
    assert entity.canonical_name == "Systemic Lupus Erythematosus"


def test_claim_model_invariants() -> None:
    claim_id = uuid.uuid4()
    claim = Claim(
        id=claim_id,
        subject_curie="MONDO:0007915",
        predicate=Predicate.HAS_PHENOTYPE,
        object_curie="HP:0001945",
        qualifiers={"negated": False},
    )
    assert claim.subject_curie == "MONDO:0007915"
    assert claim.predicate == Predicate.HAS_PHENOTYPE
    assert claim.object_curie == "HP:0001945"


def test_research_run_status_machine() -> None:
    run_id = uuid.uuid4()
    run = ResearchRun(
        id=run_id,
        name="test_run",
        fingerprint="abc123hash",
        status=RunStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    assert run.status == RunStatus.PENDING


def test_exceptions_hierarchy() -> None:
    assert issubclass(BiomedicalValidationError, BiomedicalError)
    assert issubclass(SnapshotConflictError, BiomedicalError)
    assert issubclass(RunTransitionError, BiomedicalError)
