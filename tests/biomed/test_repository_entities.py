from med_research.biomed.models import EntityType


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
