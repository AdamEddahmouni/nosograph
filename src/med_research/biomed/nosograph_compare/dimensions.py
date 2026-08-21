"""Modular comparison dimensions for NosoGraph Compare."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from med_research.biomed.comparison.fingerprint import build_fingerprint
from med_research.biomed.comparison.models import ConditionFingerprint
from med_research.biomed.models import Predicate
from med_research.biomed.nosograph_compare.models import (
    DimensionMissingData,
    DimensionOverlap,
    MissingDataReason,
)
from med_research.biomed.repository import BiomedicalRepository, ClaimView


@dataclass(frozen=True)
class DimensionContext:
    repository: BiomedicalRepository
    left_fp: ConditionFingerprint
    right_fp: ConditionFingerprint


class ComparisonDimension(Protocol):
    @property
    def name(self) -> str: ...

    def compare(self, context: DimensionContext) -> DimensionOverlap: ...


def _missing_reason(present: bool, count: int, *, negated_only: bool = False) -> MissingDataReason:
    if negated_only:
        return MissingDataReason.KNOWN_ABSENT
    if present and count == 0:
        return MissingDataReason.NOT_RECORDED
    if not present:
        return MissingDataReason.UNKNOWN
    return MissingDataReason.NOT_APPLICABLE


def _evidence_count(claims: list[ClaimView]) -> int:
    return sum(len(item.evidence) for item in claims)


class PhenotypeDimension:
    name = "phenotype"

    def compare(self, context: DimensionContext) -> DimensionOverlap:
        left = set(context.left_fp.positive_phenotypes)
        right = set(context.right_fp.positive_phenotypes)
        left_neg = set(context.left_fp.negative_phenotypes)
        right_neg = set(context.right_fp.negative_phenotypes)
        warnings: list[str] = []
        if left_neg or right_neg:
            warnings.append(
                "Negative phenotypes recorded separately; not included in shared overlap."
            )
        left_cov = context.left_fp.coverage.get("phenotype")
        right_cov = context.right_fp.coverage.get("phenotype")
        missing = DimensionMissingData(
            left=_missing_reason(
                bool(left_cov and left_cov.present),
                len(left),
                negated_only=bool(left_neg and not left),
            ),
            right=_missing_reason(
                bool(right_cov and right_cov.present),
                len(right),
                negated_only=bool(right_neg and not right),
            ),
        )
        left_claims = context.repository.list_claims(
            context.left_fp.condition_curie, predicate=Predicate.HAS_PHENOTYPE
        )
        right_claims = context.repository.list_claims(
            context.right_fp.condition_curie, predicate=Predicate.HAS_PHENOTYPE
        )
        return DimensionOverlap(
            dimension=self.name,
            shared=sorted(left & right),
            unique_to_left=sorted(left - right),
            unique_to_right=sorted(right - left),
            missing_data=missing,
            left_evidence_count=_evidence_count(left_claims),
            right_evidence_count=_evidence_count(right_claims),
            warnings=warnings,
        )


class GeneDimension:
    name = "gene"

    def compare(self, context: DimensionContext) -> DimensionOverlap:
        left = set(context.left_fp.genes)
        right = set(context.right_fp.genes)
        left_cov = context.left_fp.coverage.get("gene")
        right_cov = context.right_fp.coverage.get("gene")
        missing = DimensionMissingData(
            left=_missing_reason(bool(left_cov and left_cov.present), len(left)),
            right=_missing_reason(bool(right_cov and right_cov.present), len(right)),
        )
        left_claims = context.repository.list_claims(
            context.left_fp.condition_curie, predicate=Predicate.ASSOCIATED_WITH_GENE
        )
        right_claims = context.repository.list_claims(
            context.right_fp.condition_curie, predicate=Predicate.ASSOCIATED_WITH_GENE
        )
        return DimensionOverlap(
            dimension=self.name,
            shared=sorted(left & right),
            unique_to_left=sorted(left - right),
            unique_to_right=sorted(right - left),
            missing_data=missing,
            left_evidence_count=_evidence_count(left_claims),
            right_evidence_count=_evidence_count(right_claims),
        )


class MechanismDimension:
    name = "mechanism"

    def compare(self, context: DimensionContext) -> DimensionOverlap:
        left = set(context.left_fp.pathways)
        right = set(context.right_fp.pathways)
        left_cov = context.left_fp.coverage.get("pathway")
        right_cov = context.right_fp.coverage.get("pathway")
        missing = DimensionMissingData(
            left=_missing_reason(bool(left_cov and left_cov.present), len(left)),
            right=_missing_reason(bool(right_cov and right_cov.present), len(right)),
        )
        left_claims = context.repository.list_claims(
            context.left_fp.condition_curie, predicate=Predicate.INVOLVES_PATHWAY
        )
        right_claims = context.repository.list_claims(
            context.right_fp.condition_curie, predicate=Predicate.INVOLVES_PATHWAY
        )
        return DimensionOverlap(
            dimension=self.name,
            shared=sorted(left & right),
            unique_to_left=sorted(left - right),
            unique_to_right=sorted(right - left),
            missing_data=missing,
            left_evidence_count=_evidence_count(left_claims),
            right_evidence_count=_evidence_count(right_claims),
        )


class TreatmentDimension:
    name = "treatment"

    def compare(self, context: DimensionContext) -> DimensionOverlap:
        left = set(context.left_fp.interventions)
        right = set(context.right_fp.interventions)
        left_cov = context.left_fp.coverage.get("intervention")
        right_cov = context.right_fp.coverage.get("intervention")
        missing = DimensionMissingData(
            left=_missing_reason(bool(left_cov and left_cov.present), len(left)),
            right=_missing_reason(bool(right_cov and right_cov.present), len(right)),
        )
        left_claims = context.repository.list_claims(
            context.left_fp.condition_curie, predicate=Predicate.TREATED_BY
        )
        right_claims = context.repository.list_claims(
            context.right_fp.condition_curie, predicate=Predicate.TREATED_BY
        )
        return DimensionOverlap(
            dimension=self.name,
            shared=sorted(left & right),
            unique_to_left=sorted(left - right),
            unique_to_right=sorted(right - left),
            missing_data=missing,
            left_evidence_count=_evidence_count(left_claims),
            right_evidence_count=_evidence_count(right_claims),
        )


class EvidenceCoverageDimension:
    name = "evidence_coverage"

    def compare(self, context: DimensionContext) -> DimensionOverlap:
        left_total = len(context.left_fp.claim_ids)
        right_total = len(context.right_fp.claim_ids)
        shared_claims = sorted(
            set(context.left_fp.claim_ids) & set(context.right_fp.claim_ids), key=str
        )
        missing = DimensionMissingData(
            left=MissingDataReason.NOT_RECORDED
            if left_total == 0
            else MissingDataReason.NOT_APPLICABLE,
            right=MissingDataReason.NOT_RECORDED
            if right_total == 0
            else MissingDataReason.NOT_APPLICABLE,
        )
        warnings: list[str] = []
        if left_total != right_total:
            warnings.append("Asymmetric claim counts may reflect uneven curation depth.")
        return DimensionOverlap(
            dimension=self.name,
            shared=[str(item) for item in shared_claims],
            unique_to_left=[
                str(item)
                for item in sorted(
                    set(context.left_fp.claim_ids) - set(context.right_fp.claim_ids), key=str
                )
            ],
            unique_to_right=[
                str(item)
                for item in sorted(
                    set(context.right_fp.claim_ids) - set(context.left_fp.claim_ids), key=str
                )
            ],
            missing_data=missing,
            left_evidence_count=left_total,
            right_evidence_count=right_total,
            warnings=warnings,
        )


DIMENSION_REGISTRY: dict[str, ComparisonDimension] = {
    "phenotype": PhenotypeDimension(),
    "gene": GeneDimension(),
    "mechanism": MechanismDimension(),
    "treatment": TreatmentDimension(),
    "evidence_coverage": EvidenceCoverageDimension(),
}


def build_dimension_context(
    repository: BiomedicalRepository,
    left_curie: str,
    right_curie: str,
) -> DimensionContext:
    return DimensionContext(
        repository=repository,
        left_fp=build_fingerprint(repository, left_curie),
        right_fp=build_fingerprint(repository, right_curie),
    )
