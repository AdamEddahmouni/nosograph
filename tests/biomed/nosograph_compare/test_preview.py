from __future__ import annotations

import pytest

from med_research.biomed.identifiers import canonical_json, entity_uuid
from med_research.biomed.models import Entity, EntityType
from med_research.biomed.nosograph_compare.models import CompareV2PreviewResult
from med_research.biomed.nosograph_compare.service import NosoGraphCompareService

CONDITIONS = ("MONDO:0000001", "MONDO:0000002", "MONDO:0000003")


def _table_counts(repository) -> dict[str, int]:
    with repository.transaction() as connection:
        names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        ]
        return {
            name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]  # nosec B608
            for name in names
        }


def test_compare_preview_two_conditions_does_not_create_research_run(
    compare_v2_repository,
) -> None:
    before = compare_v2_repository.list_research_runs(limit=1).total
    counts_before = _table_counts(compare_v2_repository)

    result = NosoGraphCompareService(compare_v2_repository).compare_many_preview(
        [CONDITIONS[0], CONDITIONS[1]]
    )

    assert isinstance(result, CompareV2PreviewResult)
    assert result.run_id is None
    assert result.preview is True
    assert result.condition_curies == [CONDITIONS[0], CONDITIONS[1]]
    assert result.dimension_results
    assert compare_v2_repository.list_research_runs(limit=1).total == before
    assert _table_counts(compare_v2_repository) == counts_before


def test_compare_preview_three_to_five_conditions(compare_v2_repository) -> None:
    snapshot_id = compare_v2_repository.list_active_snapshots()[0].id
    for curie in ("MONDO:0000004", "MONDO:0000005"):
        compare_v2_repository.upsert_entity(
            Entity(
                id=entity_uuid(EntityType.CONDITION, curie),
                primary_curie=curie,
                entity_type=EntityType.CONDITION,
                created_in_snapshot_id=snapshot_id,
            )
        )
    service = NosoGraphCompareService(compare_v2_repository)
    three = service.compare_many_preview(list(CONDITIONS))
    five = service.compare_many_preview(
        [*CONDITIONS, "MONDO:0000004", "MONDO:0000005"], dimensions=["phenotype"]
    )

    assert three.run_id is None
    assert three.preview is True
    assert three.condition_curies == list(CONDITIONS)
    assert five.preview is True
    assert five.run_id is None
    assert len(five.condition_curies) == 5


def test_compare_preview_normalizes_duplicate_conditions(compare_v2_repository) -> None:
    result = NosoGraphCompareService(compare_v2_repository).compare_many_preview(
        [CONDITIONS[1].lower(), CONDITIONS[0], CONDITIONS[1], CONDITIONS[0]],
        dimensions=["treatment", "phenotype", "treatment", "gene"],
    )

    assert result.condition_curies == [CONDITIONS[0], CONDITIONS[1]]
    assert result.dimensions == ["phenotype", "gene", "treatment"]
    assert result.run_id is None
    assert result.preview is True


@pytest.mark.parametrize(
    "condition_curies, message",
    [
        ([CONDITIONS[0]], "2 to 5 unique conditions"),
        ([CONDITIONS[0], "MONDO:9999999"], "Unresolved condition CURIE"),
    ],
)
def test_compare_preview_rejects_invalid_conditions(
    compare_v2_repository, condition_curies, message
) -> None:
    with pytest.raises(ValueError, match=message):
        NosoGraphCompareService(compare_v2_repository).compare_many_preview(condition_curies)


@pytest.mark.parametrize("dimensions", [[], ["mechanism"], ["unknown"]])
def test_compare_preview_rejects_invalid_dimensions(compare_v2_repository, dimensions) -> None:
    with pytest.raises(ValueError):
        NosoGraphCompareService(compare_v2_repository).compare_many_preview(
            list(CONDITIONS[:2]), dimensions=dimensions
        )


def test_compare_preview_is_deterministic_and_matches_persisted_fields(
    compare_v2_repository,
) -> None:
    service = NosoGraphCompareService(compare_v2_repository)
    first = service.compare_many_preview(list(CONDITIONS), dimensions=["phenotype", "gene"])
    second = service.compare_many_preview(
        [CONDITIONS[2], CONDITIONS[0], CONDITIONS[1]], dimensions=["gene", "phenotype"]
    )
    persisted = service.compare_many(list(CONDITIONS), dimensions=["phenotype", "gene"])

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert canonical_json(first.model_dump(mode="json")) == canonical_json(
        second.model_dump(mode="json")
    )
    preview_fields = first.model_dump(exclude={"run_id", "preview"})
    persisted_fields = persisted.model_dump(exclude={"run_id"})
    assert preview_fields == persisted_fields
    assert persisted.run_id is not None
    assert not hasattr(persisted, "preview")
    assert compare_v2_repository.get_research_run(persisted.run_id) is not None


def test_compare_preview_never_calls_research_run_writers(
    compare_v2_repository, monkeypatch
) -> None:
    service = NosoGraphCompareService(compare_v2_repository)

    def boom(*_args, **_kwargs):
        raise AssertionError("preview must not write research runs")

    monkeypatch.setattr(compare_v2_repository, "create_research_run", boom)
    monkeypatch.setattr(compare_v2_repository, "transition_research_run", boom)

    result = service.compare_many_preview(list(CONDITIONS[:2]))
    assert result.preview is True
    assert result.run_id is None
