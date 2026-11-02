from med_research.biomed.identifiers import entity_revision_uuid, snapshot_uuid
from med_research.biomed.models import EntityRevision, EntityType, ResourceSnapshot


def test_entity_writes_are_idempotent(repository, mondo_snapshot, sle_entity, sle_revision) -> None:
    repository.upsert_snapshot(mondo_snapshot)
    repository.upsert_snapshot(mondo_snapshot)
    repository.upsert_entity(sle_entity)
    repository.upsert_entity(sle_entity)
    repository.add_entity_revision(sle_revision)
    repository.activate_snapshot("mondo", mondo_snapshot.id)
    active = repository.get_active_snapshot("mondo")
    assert active is not None
    assert active.id == mondo_snapshot.id
    assert active.resource_name == mondo_snapshot.resource_name
    assert active.version == mondo_snapshot.version
    assert active.checksum == mondo_snapshot.checksum
    assert repository.get_entity("MONDO:0007915").entity == sle_entity


def test_non_exact_mapping_never_resolves(
    repository, mondo_snapshot, exact_mapping, close_mapping
) -> None:
    repository.upsert_snapshot(mondo_snapshot)
    repository.add_entity_mapping(exact_mapping)
    repository.add_entity_mapping(close_mapping)
    assert repository.resolve_exact_curie(exact_mapping.object_curie) == exact_mapping.subject_curie
    assert repository.resolve_exact_curie(close_mapping.object_curie) is None


def test_search_entities_finds_synonym(
    repository, mondo_snapshot, sle_entity, sle_revision
) -> None:
    repository.upsert_snapshot(mondo_snapshot)
    repository.upsert_entity(sle_entity)
    repository.add_entity_revision(sle_revision)
    page = repository.search_entities("lupus", entity_type=EntityType.CONDITION, limit=10, offset=0)
    assert page.total >= 1
    assert any(item.entity.primary_curie == "MONDO:0007915" for item in page.items)


def test_search_entities_returns_one_row_per_entity(
    repository, mondo_snapshot, sle_entity, sle_revision
) -> None:
    """Search must not fan out over historical revision labels.

    Demo snapshots import MONDO and the legacy profile for the same CURIE, so an
    entity can carry several labels. The condition explorer renders every row,
    which would show the same condition twice and made the demo browser flow
    ambiguous.
    """
    legacy_snapshot = ResourceSnapshot(
        id=snapshot_uuid("legacy", "1", "sha256:legacy-fixture"),
        resource_name="legacy",
        version="1",
        checksum="sha256:legacy-fixture",
        name="Legacy disease profile",
        namespace_prefix="MONDO",
    )
    legacy_revision = EntityRevision(
        id=entity_revision_uuid(sle_entity.id, legacy_snapshot.id),
        entity_id=sle_entity.id,
        snapshot_id=legacy_snapshot.id,
        label="Systemic Lupus Erythematosus",
        synonyms=["lupus"],
    )
    repository.upsert_snapshot(mondo_snapshot)
    repository.upsert_snapshot(legacy_snapshot)
    repository.upsert_entity(sle_entity)
    repository.add_entity_revision(sle_revision)
    repository.add_entity_revision(legacy_revision)

    page = repository.search_entities("lupus", entity_type=EntityType.CONDITION, limit=10, offset=0)

    assert page.total == 1
    assert len(page.items) == 1
    assert page.items[0].entity.id == sle_entity.id
    assert page.items[0].label in {sle_revision.label, legacy_revision.label}
