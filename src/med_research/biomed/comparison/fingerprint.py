"""Build versioned condition fingerprints from active canonical claims."""

from __future__ import annotations

from uuid import UUID

from med_research.biomed.comparison.models import ConditionFingerprint, DimensionCoverage
from med_research.biomed.identifiers import fingerprint_json, normalize_curie
from med_research.biomed.models import Predicate
from med_research.biomed.repository import BiomedicalRepository

_DIMENSION_PREDICATES: dict[str, Predicate] = {
    "gene": Predicate.ASSOCIATED_WITH_GENE,
    "pathway": Predicate.INVOLVES_PATHWAY,
    "intervention": Predicate.TREATED_BY,
    "biomarker": Predicate.HAS_BIOMARKER,
}


def build_fingerprint(
    repository: BiomedicalRepository, condition_curie: str
) -> ConditionFingerprint:
    normalized = normalize_curie(condition_curie)
    claims = [
        claim_view
        for claim_view in repository.list_claims(normalized)
        if repository.claim_is_current(claim_view.claim.id)
    ]

    positive_phenotypes: set[str] = set()
    negative_phenotypes: set[str] = set()
    genes: set[str] = set()
    pathways: set[str] = set()
    interventions: set[str] = set()
    biomarkers: set[str] = set()
    claim_ids: list[UUID] = []
    snapshot_ids_by_dimension: dict[str, set[UUID]] = {
        "phenotype": set(),
        "gene": set(),
        "pathway": set(),
        "intervention": set(),
        "biomarker": set(),
    }

    for claim_view in claims:
        claim = claim_view.claim
        claim_ids.append(claim.id)
        evidence_snapshots = {item.snapshot_id for item in claim_view.evidence}

        if claim.predicate is Predicate.HAS_PHENOTYPE:
            negated = bool(claim.qualifiers.get("negated"))
            if negated:
                negative_phenotypes.add(claim.object_curie)
            else:
                positive_phenotypes.add(claim.object_curie)
            snapshot_ids_by_dimension["phenotype"].update(evidence_snapshots)
            continue

        for dimension, predicate in _DIMENSION_PREDICATES.items():
            if claim.predicate is predicate:
                target = {
                    "gene": genes,
                    "pathway": pathways,
                    "intervention": interventions,
                    "biomarker": biomarkers,
                }[dimension]
                target.add(claim.object_curie)
                snapshot_ids_by_dimension[dimension].update(evidence_snapshots)
                break

    dimension_values = {
        "phenotype": (positive_phenotypes, negative_phenotypes),
        "gene": (genes,),
        "pathway": (pathways,),
        "intervention": (interventions,),
        "biomarker": (biomarkers,),
    }
    coverage = {
        dimension: DimensionCoverage(
            present=any(values for values in dimension_values[dimension]),
            count=sum(len(values) for values in dimension_values[dimension]),
            snapshot_ids=sorted(snapshot_ids_by_dimension[dimension]),
        )
        for dimension in ("phenotype", "gene", "pathway", "intervention", "biomarker")
    }

    sorted_claim_ids = sorted(str(item) for item in claim_ids)
    claim_set_fingerprint = fingerprint_json(
        {
            "condition_curie": normalized,
            "claim_ids": sorted_claim_ids,
        }
    )

    return ConditionFingerprint(
        condition_curie=normalized,
        positive_phenotypes=sorted(positive_phenotypes),
        negative_phenotypes=sorted(negative_phenotypes),
        genes=sorted(genes),
        pathways=sorted(pathways),
        interventions=sorted(interventions),
        biomarkers=sorted(biomarkers),
        coverage=coverage,
        claim_ids=sorted(claim_ids, key=str),
        claim_set_fingerprint=claim_set_fingerprint,
    )
