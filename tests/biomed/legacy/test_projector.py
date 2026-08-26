from __future__ import annotations

from uuid import uuid4

import pytest

from med_research.biomed.legacy.projector import project_disease
from med_research.biomed.models import EntityType, Predicate


def test_sle_projection_emits_genes_drugs_and_target_claims() -> None:
    bundle = project_disease("sle", snapshot_id=uuid4())
    types = {entity.entity_type for entity in bundle.entities}
    assert EntityType.GENE in types
    assert EntityType.INTERVENTION in types
    predicates = {claim.predicate for claim in bundle.claims}
    assert Predicate.TREATED_BY in predicates or Predicate.HAS_BIOMARKER in predicates


def test_projection_emits_typed_condition_entity() -> None:
    projection = project_disease("ra", snapshot_id=uuid4())
    condition = next(
        entity for entity in projection.entities if entity.primary_curie == projection.mondo_curie
    )
    assert condition.entity_type is EntityType.CONDITION


def test_ra_projection_does_not_emit_sle_identifiers() -> None:
    bundle = project_disease("ra", snapshot_id=uuid4())
    serialized = "|".join(
        [
            bundle.mondo_curie,
            *[entity.primary_curie for entity in bundle.entities],
            *[claim.subject_curie for claim in bundle.claims],
            *[claim.object_curie for claim in bundle.claims],
            *[revision.label for revision in bundle.revisions],
        ]
    )
    assert "MONDO:0007915" not in serialized
    assert "Lupus (SLE)" not in serialized


@pytest.mark.parametrize("disease_id", ["sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"])
def test_each_disease_projects_entities_and_claims(disease_id: str) -> None:
    bundle = project_disease(disease_id, snapshot_id=uuid4())
    assert bundle.entities
    assert bundle.claims
    assert bundle.mondo_curie.startswith("MONDO:")
