"""Canonical deterministic N-way comparison engine."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from med_research.biomed.identifiers import fingerprint_json
from med_research.biomed.models import ClaimEvidence, Predicate, ResourceSnapshot
from med_research.biomed.nosograph_compare.models import (
    CompareWarning,
    ConditionCoverage,
    DimensionComparison,
    EntityState,
    EntityStateRow,
    SubsetMembership,
)
from med_research.biomed.repository import BiomedicalRepository, ClaimView

DIMENSION_PREDICATES = {
    "phenotype": Predicate.HAS_PHENOTYPE,
    "gene": Predicate.ASSOCIATED_WITH_GENE,
    "pathway": Predicate.INVOLVES_PATHWAY,
    "treatment": Predicate.TREATED_BY,
}


@dataclass(frozen=True)
class ConditionFingerprint:
    condition_curie: str
    positive: dict[str, frozenset[str]]
    negated: dict[str, frozenset[str]]
    positive_counts: dict[str, dict[str, int]]
    negated_counts: dict[str, dict[str, int]]
    coverage: dict[str, ConditionCoverage]
    positive_claim_ids_by_entity: dict[str, dict[str, tuple[UUID, ...]]]
    negated_claim_ids_by_entity: dict[str, dict[str, tuple[UUID, ...]]]
    claim_ids: tuple[UUID, ...]
    fingerprint: str


@dataclass(frozen=True)
class CohortContext:
    condition_curies: tuple[str, ...]
    fingerprints: dict[str, ConditionFingerprint]
    condition_labels: dict[str, str]
    entity_labels: dict[str, str]
    snapshot_ids: tuple[UUID, ...]

    @property
    def claim_ids(self) -> list[UUID]:
        return sorted(
            {claim_id for item in self.fingerprints.values() for claim_id in item.claim_ids},
            key=str,
        )


def build_cohort_context(
    repository: BiomedicalRepository, condition_curies: list[str]
) -> CohortContext:
    snapshots = sorted(repository.list_active_snapshots(), key=lambda item: str(item.id))
    snapshot_by_id = {item.id: item for item in snapshots}
    active_ids = set(snapshot_by_id)
    fingerprints = {
        curie: _build_condition_fingerprint(repository, curie, active_ids, snapshot_by_id)
        for curie in condition_curies
    }
    entity_curies = {
        entity
        for fingerprint in fingerprints.values()
        for values in (*fingerprint.positive.values(), *fingerprint.negated.values())
        for entity in values
    }
    return CohortContext(
        condition_curies=tuple(condition_curies),
        fingerprints=fingerprints,
        condition_labels={
            curie: _display_label(repository, curie, active_ids) for curie in condition_curies
        },
        entity_labels={
            curie: _display_label(repository, curie, active_ids) for curie in sorted(entity_curies)
        },
        snapshot_ids=tuple(item.id for item in snapshots),
    )


def compare_dimension(context: CohortContext, dimension: str) -> DimensionComparison:
    if dimension == "evidence_coverage":
        coverage = {
            curie: context.fingerprints[curie].coverage[dimension]
            for curie in context.condition_curies
        }
        warnings = _curation_warnings(dimension, coverage)
        return DimensionComparison(
            dimension=dimension,
            unique_by_condition={curie: [] for curie in context.condition_curies},
            coverage_by_condition=coverage,
            warnings=warnings,
        )

    all_entities = sorted(
        {
            entity
            for fingerprint in context.fingerprints.values()
            for entity in (*fingerprint.positive[dimension], *fingerprint.negated[dimension])
        }
    )
    shared_all: list[str] = []
    subsets: list[SubsetMembership] = []
    unique = {curie: [] for curie in context.condition_curies}
    rows: list[EntityStateRow] = []
    conflict_warnings: list[CompareWarning] = []

    for entity in all_entities:
        states: dict[str, EntityState] = {}
        present_in: list[str] = []
        for curie in context.condition_curies:
            fingerprint = context.fingerprints[curie]
            positive = entity in fingerprint.positive[dimension]
            negated = entity in fingerprint.negated[dimension]
            if positive:
                states[curie] = EntityState.PRESENT
                present_in.append(curie)
                if negated:
                    conflict_warnings.append(
                        CompareWarning(
                            code="CONFLICTING_ASSERTIONS",
                            dimension=dimension,
                            entity_curie=entity,
                            condition_curies=[curie],
                            counts={
                                item: (
                                    context.fingerprints[item]
                                    .positive_counts[dimension]
                                    .get(entity, 0)
                                    + context.fingerprints[item]
                                    .negated_counts[dimension]
                                    .get(entity, 0)
                                )
                                for item in context.condition_curies
                            },
                            message=(
                                f"{curie} has positive and negated assertions for {entity} in "
                                f"{dimension}; PRESENT takes precedence."
                            ),
                        )
                    )
            elif negated:
                states[curie] = EntityState.KNOWN_ABSENT
            else:
                states[curie] = EntityState.NOT_RECORDED
        rows.append(
            EntityStateRow(
                entity_curie=entity,
                entity_label=context.entity_labels.get(entity, entity),
                states=states,
                claim_ids_by_condition={
                    curie: _claim_ids_for_state(
                        context.fingerprints[curie],
                        dimension,
                        entity,
                        states[curie],
                    )
                    for curie in context.condition_curies
                },
            )
        )
        if len(present_in) == len(context.condition_curies):
            shared_all.append(entity)
        elif len(present_in) >= 2:
            subsets.append(SubsetMembership(entity_curie=entity, condition_curies=present_in))
        elif len(present_in) == 1:
            unique[present_in[0]].append(entity)

    coverage = {
        curie: context.fingerprints[curie].coverage[dimension] for curie in context.condition_curies
    }
    warnings = sorted(
        [*_curation_warnings(dimension, coverage), *conflict_warnings],
        key=lambda item: (
            item.code,
            item.dimension,
            item.entity_curie or "",
            tuple(item.condition_curies),
        ),
    )
    return DimensionComparison(
        dimension=dimension,
        shared_by_all=shared_all,
        shared_by_subset=subsets,
        unique_by_condition=unique,
        entities=rows,
        coverage_by_condition=coverage,
        warnings=warnings,
    )


def _claim_ids_for_state(
    fingerprint: ConditionFingerprint,
    dimension: str,
    entity: str,
    state: EntityState,
) -> list[UUID]:
    positive = fingerprint.positive_claim_ids_by_entity[dimension].get(entity, ())
    negated = fingerprint.negated_claim_ids_by_entity[dimension].get(entity, ())
    if state is EntityState.PRESENT:
        selected = (*positive, *negated) if negated else positive
    elif state is EntityState.KNOWN_ABSENT:
        selected = negated
    else:
        selected = ()
    return sorted(set(selected), key=str)


def dimension_has_comparable_data(result: DimensionComparison) -> bool:
    return sum(item.claim_count > 0 for item in result.coverage_by_condition.values()) >= 2


def _build_condition_fingerprint(
    repository: BiomedicalRepository,
    condition_curie: str,
    active_ids: set[UUID],
    snapshots: dict[UUID, ResourceSnapshot],
) -> ConditionFingerprint:
    current: list[tuple[ClaimView, list[ClaimEvidence]]] = []
    for view in repository.list_claims(condition_curie):
        active_evidence = [item for item in view.evidence if item.snapshot_id in active_ids]
        if active_evidence and repository.claim_is_current(view.claim.id):
            current.append((view, active_evidence))

    positive: dict[str, frozenset[str]] = {}
    negated: dict[str, frozenset[str]] = {}
    positive_counts: dict[str, dict[str, int]] = {}
    negated_counts: dict[str, dict[str, int]] = {}
    coverage: dict[str, ConditionCoverage] = {}
    positive_claim_ids_by_entity: dict[str, dict[str, tuple[UUID, ...]]] = {}
    negated_claim_ids_by_entity: dict[str, dict[str, tuple[UUID, ...]]] = {}
    for dimension, predicate in DIMENSION_PREDICATES.items():
        selected = [
            (view, evidence) for view, evidence in current if view.claim.predicate == predicate
        ]
        positive[dimension] = frozenset(
            view.object_curie for view, _ in selected if not _is_negated(view)
        )
        negated[dimension] = frozenset(
            view.object_curie for view, _ in selected if _is_negated(view)
        )
        positive_counts[dimension] = dict(
            sorted(
                Counter(view.object_curie for view, _ in selected if not _is_negated(view)).items()
            )
        )
        negated_counts[dimension] = dict(
            sorted(Counter(view.object_curie for view, _ in selected if _is_negated(view)).items())
        )
        grouped_positive: dict[str, list[UUID]] = {}
        grouped_negated: dict[str, list[UUID]] = {}
        for view, _ in selected:
            grouped = grouped_negated if _is_negated(view) else grouped_positive
            grouped.setdefault(view.object_curie, []).append(view.claim.id)
        positive_claim_ids_by_entity[dimension] = {
            entity: tuple(sorted(ids, key=str)) for entity, ids in sorted(grouped_positive.items())
        }
        negated_claim_ids_by_entity[dimension] = {
            entity: tuple(sorted(ids, key=str)) for entity, ids in sorted(grouped_negated.items())
        }
        coverage[dimension] = _coverage(selected, snapshots)
    coverage["evidence_coverage"] = _coverage(current, snapshots)

    claim_ids = tuple(sorted((view.claim.id for view, _ in current), key=str))
    payload = {
        "condition_curie": condition_curie,
        "positive": {key: sorted(value) for key, value in positive.items()},
        "negated": {key: sorted(value) for key, value in negated.items()},
        "positive_counts": positive_counts,
        "negated_counts": negated_counts,
        "coverage": {key: value.model_dump(mode="json") for key, value in sorted(coverage.items())},
        "claim_ids": [str(item) for item in claim_ids],
    }
    return ConditionFingerprint(
        condition_curie=condition_curie,
        positive=positive,
        negated=negated,
        positive_counts=positive_counts,
        negated_counts=negated_counts,
        coverage=coverage,
        positive_claim_ids_by_entity=positive_claim_ids_by_entity,
        negated_claim_ids_by_entity=negated_claim_ids_by_entity,
        claim_ids=claim_ids,
        fingerprint=fingerprint_json(payload),
    )


def _display_label(repository: BiomedicalRepository, curie: str, active_ids: set[UUID]) -> str:
    view = repository.get_entity(curie)
    if view is None:
        return curie
    if (
        view.revision is not None
        and view.revision.snapshot_id in active_ids
        and view.revision.label
    ):
        return view.revision.label
    return view.entity.canonical_name or curie


def _coverage(
    claims: list[tuple[ClaimView, list[ClaimEvidence]]],
    snapshots: dict[UUID, ResourceSnapshot],
) -> ConditionCoverage:
    evidence = [item for _, items in claims for item in items]
    snapshot_ids = sorted({item.snapshot_id for item in evidence}, key=str)
    source_names = sorted({snapshots[item].resource_name for item in snapshot_ids})
    positive_count = sum(not _is_negated(view) for view, _ in claims)
    negated_count = len(claims) - positive_count
    return ConditionCoverage(
        positive_claim_count=positive_count,
        negated_claim_count=negated_count,
        claim_count=len(claims),
        evidence_count=len(evidence),
        source_count=len(source_names),
        snapshot_count=len(snapshot_ids),
        snapshot_ids=snapshot_ids,
        source_names=source_names,
    )


def _is_negated(view: ClaimView) -> bool:
    return view.claim.qualifiers.get("negated") is True


def _curation_warnings(
    dimension: str, coverage: dict[str, ConditionCoverage]
) -> list[CompareWarning]:
    counts = {curie: item.positive_claim_count for curie, item in coverage.items()}
    positive = [value for value in counts.values() if value > 0]
    warnings: list[CompareWarning] = []
    if positive and len(positive) != len(counts):
        missing = [curie for curie, value in counts.items() if value == 0]
        warnings.append(
            CompareWarning(
                code="MISSING_CURATION",
                dimension=dimension,
                condition_curies=missing,
                counts=counts,
                message=f"No positive {dimension} claims are recorded for: {', '.join(missing)}.",
            )
        )
    if (
        len(positive) >= 2
        and max(positive) >= 2 * min(positive)
        and max(positive) - min(positive) >= 3
    ):
        affected = [
            curie for curie, value in counts.items() if value in {min(positive), max(positive)}
        ]
        warnings.append(
            CompareWarning(
                code="ASYMMETRIC_CURATION",
                dimension=dimension,
                condition_curies=affected,
                counts=counts,
                message=(
                    f"Positive {dimension} claim counts differ by at least 2x and by at least 3 claims."
                ),
            )
        )
    return warnings
