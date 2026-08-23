from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

import med_research.biomed.nosograph_compare.service as compare_service_module
from med_research.biomed.identifiers import canonical_json, claim_evidence_uuid, claim_uuid
from med_research.biomed.models import Claim, ClaimEvidence, EvidenceDirection, Predicate, RunStatus
from med_research.biomed.nosograph_compare.models import EntityState
from med_research.biomed.nosograph_compare.service import (
    CompareRunIncompleteError,
    NosoGraphCompareService,
)

CONDITIONS = ("MONDO:0000001", "MONDO:0000002", "MONDO:0000003")


def _dimension(result, name: str):
    return next(item for item in result.dimension_results if item.dimension == name)


def test_compare_many_canonicalizes_inputs_dimensions_and_replays_run(
    compare_v2_repository,
) -> None:
    service = NosoGraphCompareService(compare_v2_repository)
    first = service.compare_many(
        [CONDITIONS[2].lower(), CONDITIONS[0], CONDITIONS[1], CONDITIONS[0]],
        dimensions=["treatment", "phenotype", "treatment", "gene"],
    )
    permuted = service.compare_many(
        [CONDITIONS[1], CONDITIONS[2], CONDITIONS[0]],
        dimensions=["gene", "treatment", "phenotype"],
    )

    assert first.condition_curies == list(CONDITIONS)
    assert first.dimensions == ["phenotype", "gene", "treatment"]
    assert first == permuted
    assert first.algorithm_version == "2.0.0"
    assert first.result_schema_version == "2.0"
    run = compare_v2_repository.get_research_run(first.run_id)
    assert run is not None
    assert run.run_type == "nosograph_compare_v2"
    assert run.parameters["result_schema_version"] == "2.0"
    assert run.result is not None


def test_compare_many_result_schema_version_changes_run_identity(
    compare_v2_repository,
    monkeypatch,
) -> None:
    service = NosoGraphCompareService(compare_v2_repository)
    current = service.compare_many(list(CONDITIONS), dimensions=["phenotype"])

    monkeypatch.setattr(compare_service_module, "COMPARE_RESULT_SCHEMA_VERSION", "2.1")
    evolved = service.compare_many(list(CONDITIONS), dimensions=["phenotype"])

    assert current.run_id != evolved.run_id
    assert evolved.result_schema_version == "2.1"


def test_compare_many_partitions_memberships_and_preserves_absence_semantics(
    compare_v2_repository,
) -> None:
    snapshot_id = compare_v2_repository.list_active_snapshots()[0].id
    for negated in (False, True):
        qualifiers = {"negated": negated, "context": "second assertion"}
        claim = Claim(
            id=claim_uuid(CONDITIONS[0], Predicate.HAS_PHENOTYPE, "HP:0000007", qualifiers),
            subject_curie=CONDITIONS[0],
            predicate=Predicate.HAS_PHENOTYPE,
            object_curie="HP:0000007",
            qualifiers=qualifiers,
        )
        compare_v2_repository.add_claim(claim)
        compare_v2_repository.add_claim_evidence(
            ClaimEvidence(
                id=claim_evidence_uuid(
                    claim.id,
                    snapshot_id,
                    EvidenceDirection.SUPPORTING,
                    f"second-conflict-{negated}",
                ),
                claim_id=claim.id,
                snapshot_id=snapshot_id,
                direction=EvidenceDirection.SUPPORTING,
                source_record_id=f"second-conflict-{negated}",
            )
        )
    result = NosoGraphCompareService(compare_v2_repository).compare_many(list(CONDITIONS))
    phenotype = _dimension(result, "phenotype")

    assert phenotype.shared_by_all == ["HP:0000001"]
    assert [item.model_dump() for item in phenotype.shared_by_subset] == [
        {"entity_curie": "HP:0000002", "condition_curies": list(CONDITIONS[:2])}
    ]
    assert phenotype.unique_by_condition == {
        CONDITIONS[0]: ["HP:0000003", "HP:0000007"],
        CONDITIONS[1]: ["HP:0000004"],
        CONDITIONS[2]: ["HP:0000005", "HP:0000006"],
    }
    negated = next(item for item in phenotype.entities if item.entity_curie == "HP:0000006")
    assert negated.states == {
        CONDITIONS[0]: EntityState.KNOWN_ABSENT,
        CONDITIONS[1]: EntityState.NOT_RECORDED,
        CONDITIONS[2]: EntityState.PRESENT,
    }
    conflict = next(item for item in phenotype.entities if item.entity_curie == "HP:0000007")
    assert conflict.states[CONDITIONS[0]] is EntityState.PRESENT
    conflict_claims = conflict.claim_ids_by_condition[CONDITIONS[0]]
    assert len(conflict_claims) == 4
    qualifiers = [
        compare_v2_repository.get_claim_by_id(claim_id).claim.qualifiers
        for claim_id in conflict_claims
    ]
    assert any(item.get("negated") is True for item in qualifiers)
    assert any(item.get("negated") is not True for item in qualifiers)
    conflict_warning = next(
        warning
        for warning in phenotype.warnings
        if warning.code == "CONFLICTING_ASSERTIONS" and warning.entity_curie == "HP:0000007"
    )
    assert conflict_warning.counts == {
        CONDITIONS[0]: 4,
        CONDITIONS[1]: 0,
        CONDITIONS[2]: 0,
    }


def test_compare_many_persists_labels_and_exact_claim_links(compare_v2_repository) -> None:
    result = NosoGraphCompareService(compare_v2_repository).compare_many(
        list(CONDITIONS), dimensions=["phenotype"]
    )
    phenotype = _dimension(result, "phenotype")
    shared = next(item for item in phenotype.entities if item.entity_curie == "HP:0000001")
    missing = next(item for item in phenotype.entities if item.entity_curie == "HP:0000006")

    assert result.condition_labels == {
        CONDITIONS[0]: "Condition 1",
        CONDITIONS[1]: "Condition 2",
        CONDITIONS[2]: "Condition 3",
    }
    assert shared.entity_label == "HP:0000001"
    assert set(shared.claim_ids_by_condition) == set(CONDITIONS)
    assert all(shared.claim_ids_by_condition[curie] for curie in CONDITIONS)
    assert missing.claim_ids_by_condition[CONDITIONS[0]]
    assert missing.claim_ids_by_condition[CONDITIONS[1]] == []
    assert missing.claim_ids_by_condition[CONDITIONS[2]]
    for claim_ids in shared.claim_ids_by_condition.values():
        assert claim_ids == sorted(claim_ids, key=str)


def test_compare_many_reports_coverage_and_curation_thresholds(compare_v2_repository) -> None:
    result = NosoGraphCompareService(compare_v2_repository).compare_many(list(CONDITIONS))
    gene = _dimension(result, "gene")
    pathway = _dimension(result, "pathway")
    coverage = _dimension(result, "evidence_coverage")

    assert gene.coverage_by_condition[CONDITIONS[0]].positive_claim_count == 6
    assert gene.coverage_by_condition[CONDITIONS[1]].positive_claim_count == 3
    assert gene.coverage_by_condition[CONDITIONS[2]].positive_claim_count == 0
    assert {warning.code for warning in gene.warnings} == {
        "MISSING_CURATION",
        "ASYMMETRIC_CURATION",
    }
    assert not {
        "MISSING_CURATION",
        "ASYMMETRIC_CURATION",
    } & {warning.code for warning in pathway.warnings}
    assert coverage.coverage_by_condition[CONDITIONS[0]].claim_count > 0
    assert coverage.coverage_by_condition[CONDITIONS[0]].evidence_count > 0
    assert coverage.coverage_by_condition[CONDITIONS[0]].source_count == 1
    assert coverage.coverage_by_condition[CONDITIONS[0]].snapshot_count == 1
    assert result.status == "comparable"


@pytest.mark.parametrize(
    ("condition_curies", "message"),
    [
        ([CONDITIONS[0]], "2 to 5 unique conditions"),
        (
            [*CONDITIONS, "MONDO:0000004", "MONDO:0000005", "MONDO:0000006"],
            "2 to 5 unique conditions",
        ),
        ([CONDITIONS[0], "MONDO:9999999"], "Unresolved condition CURIE"),
    ],
)
def test_compare_many_rejects_invalid_cohorts(
    compare_v2_repository, condition_curies, message
) -> None:
    with pytest.raises(ValueError, match=message):
        NosoGraphCompareService(compare_v2_repository).compare_many(condition_curies)


@pytest.mark.parametrize("dimensions", [[], ["mechanism"], ["unknown"]])
def test_compare_many_rejects_invalid_dimensions(compare_v2_repository, dimensions) -> None:
    with pytest.raises(ValueError):
        NosoGraphCompareService(compare_v2_repository).compare_many(
            list(CONDITIONS[:2]), dimensions=dimensions
        )


def test_compare_many_rejects_orphan_current_claim_subject(compare_v2_repository) -> None:
    snapshot_id = compare_v2_repository.list_active_snapshots()[0].id
    claim = Claim(
        id=claim_uuid("MONDO:9999998", Predicate.HAS_PHENOTYPE, "HP:9999998", {}),
        subject_curie="MONDO:9999998",
        predicate=Predicate.HAS_PHENOTYPE,
        object_curie="HP:9999998",
    )
    compare_v2_repository.add_claim(claim)
    compare_v2_repository.add_claim_evidence(
        ClaimEvidence(
            id=claim_evidence_uuid(
                claim.id, snapshot_id, EvidenceDirection.SUPPORTING, "orphan-current"
            ),
            claim_id=claim.id,
            snapshot_id=snapshot_id,
            direction=EvidenceDirection.SUPPORTING,
            source_record_id="orphan-current",
        )
    )

    with pytest.raises(ValueError, match="Unresolved condition CURIE"):
        NosoGraphCompareService(compare_v2_repository).compare_many(
            [CONDITIONS[0], "MONDO:9999998"]
        )


def test_compare_many_recovers_deterministic_running_run(compare_v2_repository) -> None:
    service = NosoGraphCompareService(compare_v2_repository)
    completed = service.compare_many(list(CONDITIONS[:2]), dimensions=["phenotype"])
    with compare_v2_repository.transaction() as connection:
        connection.execute(
            "UPDATE research_runs SET status = ?, result_json = NULL WHERE id = ?",
            (RunStatus.RUNNING.value, str(completed.run_id)),
        )

    recovered = service.compare_many(list(reversed(CONDITIONS[:2])), dimensions=["phenotype"])
    assert recovered.run_id == completed.run_id
    assert recovered == completed


def test_compare_many_rejects_replay_of_failed_run(compare_v2_repository) -> None:
    service = NosoGraphCompareService(compare_v2_repository)
    completed = service.compare_many(list(CONDITIONS[:2]), dimensions=["gene"])
    with compare_v2_repository.transaction() as connection:
        connection.execute(
            "UPDATE research_runs SET status = ?, result_json = NULL, warnings_json = ? WHERE id = ?",
            (RunStatus.FAILED.value, '["fixture failure"]', str(completed.run_id)),
        )

    with pytest.raises(RuntimeError, match="failed"):
        service.compare_many(list(CONDITIONS[:2]), dimensions=["gene"])


def test_compare_many_concurrent_identical_requests_replay_one_completed_run(
    compare_v2_repository, monkeypatch
) -> None:
    service = NosoGraphCompareService(compare_v2_repository)
    original_create = compare_v2_repository.create_research_run
    barrier = Barrier(2)

    def synchronized_create(spec):
        barrier.wait(timeout=5)
        return original_create(spec)

    monkeypatch.setattr(compare_v2_repository, "create_research_run", synchronized_create)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                service.compare_many,
                list(CONDITIONS[:2]),
                dimensions=["treatment", "phenotype"],
            )
            for _ in range(2)
        ]
    results = [future.result() for future in futures]

    assert results[0] == results[1]
    run = compare_v2_repository.get_research_run(results[0].run_id)
    assert run is not None
    assert run.status is RunStatus.COMPLETED
    assert run.result is not None


def test_compare_many_accepts_five_conditions_and_marks_sparse_data_insufficient(
    compare_v2_repository,
) -> None:
    from med_research.biomed.identifiers import entity_uuid
    from med_research.biomed.models import Entity, EntityType

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
    sparse = NosoGraphCompareService(compare_v2_repository).compare_many(
        [CONDITIONS[0], "MONDO:0000004", "MONDO:0000005"], dimensions=["gene"]
    )
    bounded = NosoGraphCompareService(compare_v2_repository).compare_many(
        [*CONDITIONS, "MONDO:0000004", "MONDO:0000005"], dimensions=["phenotype"]
    )

    assert sparse.status == "insufficient_data"
    assert len(bounded.condition_curies) == 5


def _corrupt_persisted_result(repository, run_id, mutation) -> None:
    run = repository.get_research_run(run_id)
    assert run is not None and run.result is not None
    payload = dict(run.result)
    mutation(payload)
    with repository.transaction() as connection:
        connection.execute(
            "UPDATE research_runs SET result_json = ? WHERE id = ?",
            (canonical_json(payload), str(run_id)),
        )


def test_get_comparison_round_trips_valid_persisted_statuses(compare_v2_repository) -> None:
    from med_research.biomed.identifiers import entity_uuid
    from med_research.biomed.models import Entity, EntityType

    service = NosoGraphCompareService(compare_v2_repository)
    comparable = service.compare_many(list(CONDITIONS[:2]), dimensions=["phenotype"])
    assert comparable.status == "comparable"

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
    sparse = service.compare_many(["MONDO:0000004", "MONDO:0000005"], dimensions=["gene"])
    assert sparse.status == "insufficient_data"

    for created in (comparable, sparse):
        replayed = service.get_comparison(created.run_id)
        assert replayed.status == created.status
        assert replayed == created


def test_get_comparison_rejects_unknown_persisted_status(compare_v2_repository) -> None:
    service = NosoGraphCompareService(compare_v2_repository)
    created = service.compare_many(list(CONDITIONS[:2]), dimensions=["phenotype"])
    _corrupt_persisted_result(
        compare_v2_repository, created.run_id, lambda payload: payload.update(status="bogus")
    )

    with pytest.raises(CompareRunIncompleteError, match="invalid persisted status"):
        service.get_comparison(created.run_id)


def test_get_comparison_defaults_labels_and_claim_links_for_older_runs(
    compare_v2_repository,
) -> None:
    service = NosoGraphCompareService(compare_v2_repository)
    created = service.compare_many(list(CONDITIONS), dimensions=["phenotype"])
    run = compare_v2_repository.get_research_run(created.run_id)
    assert run is not None and run.result is not None
    payload = dict(run.result)
    payload.pop("condition_labels", None)
    for dimension in payload["dimension_results"]:
        for row in dimension["entities"]:
            row.pop("entity_label", None)
            row.pop("claim_ids_by_condition", None)
    with compare_v2_repository.transaction() as connection:
        connection.execute(
            "UPDATE research_runs SET result_json = ? WHERE id = ?",
            (canonical_json(payload), str(created.run_id)),
        )

    replayed = service.get_comparison(created.run_id)
    phenotype = _dimension(replayed, "phenotype")

    assert replayed.condition_labels == {curie: curie for curie in CONDITIONS}
    assert all(row.entity_label == row.entity_curie for row in phenotype.entities)
    assert all(
        row.claim_ids_by_condition == {curie: [] for curie in CONDITIONS}
        for row in phenotype.entities
    )


def test_compare_many_matches_complete_three_condition_golden_response(
    compare_v2_repository,
) -> None:
    service = NosoGraphCompareService(compare_v2_repository)
    canonical = service.compare_many(list(CONDITIONS))
    permuted = service.compare_many([CONDITIONS[2], CONDITIONS[0], CONDITIONS[1]])
    golden_path = Path("tests/fixtures/golden/nosograph_compare_v2.json")
    expected = json.loads(golden_path.read_text(encoding="utf-8"))

    assert canonical.model_dump(mode="json") == expected
    assert permuted.model_dump(mode="json") == expected
