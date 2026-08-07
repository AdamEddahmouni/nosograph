"""Explainable computational candidate ranking."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from .schemas import Claim, EvidenceRecord, RankedCandidate


def _band(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "moderate"
    return "low"


def rank_candidates(
    records: list[EvidenceRecord], claims: list[Claim], candidate_type: str
) -> list[RankedCandidate]:
    allowed = {"drug": "drug", "drugs": "drug", "target": "target", "targets": "target"}
    subject_type = allowed.get(candidate_type)
    if subject_type is None:
        raise ValueError(f"unsupported candidate type: {candidate_type}")
    record_index = {record.evidence_id: record for record in records}
    grouped: dict[str, list[Claim]] = defaultdict(list)
    names: dict[str, str] = {}
    for claim in claims:
        if claim.subject_type == subject_type:
            grouped[claim.subject_id].append(claim)
            names[claim.subject_id] = claim.subject_name

    ranked = []
    for candidate_id, candidate_claims in grouped.items():
        support = [claim for claim in candidate_claims if claim.relationship == "supports"]
        contradiction = [claim for claim in candidate_claims if claim.relationship == "contradicts"]
        associated = [
            claim for claim in candidate_claims if claim.relationship == "associated_with"
        ]
        all_claims = support + contradiction + associated
        support_quality = []
        contradiction_quality = []
        for claim in support:
            support_quality.extend(
                record_index[evidence_id].quality_score
                for evidence_id in claim.evidence_ids
                if evidence_id in record_index
            )
        for claim in contradiction:
            contradiction_quality.extend(
                record_index[evidence_id].quality_score
                for evidence_id in claim.evidence_ids
                if evidence_id in record_index
            )
        support_factor = sum(support_quality) / len(support_quality) if support_quality else 1.0
        contradiction_factor = sum(contradiction_quality) / len(contradiction_quality) if contradiction_quality else 1.0
        support_score = min(
            35.0, (len(support) * 18.0 + sum(claim.confidence for claim in support) * 5) * support_factor
        )
        contradiction_penalty = min(25.0, len(contradiction) * 15.0 * contradiction_factor)
        recencies = []
        quality_scores = []
        clinical = 0.0
        for claim in all_claims:
            for evidence_id in claim.evidence_ids:
                record = record_index.get(evidence_id)
                if record is None:
                    continue
                quality_scores.append(record.quality_score)
                if record.published_date:
                    age = max(0, date.today().year - record.published_date.year)
                    recencies.append(max(0.2, 1 - age / 20))
                if record.source == "clinical_trials" or claim.evidence_type == "clinical_trial":
                    clinical = min(15.0, clinical + 7.5)
        recency_score = (sum(recencies) / len(recencies) * 15) if recencies else 5.0
        confidence_score = min(
            20.0, sum(claim.confidence for claim in all_claims) / max(1, len(all_claims)) * 20
        )
        evidence_quality = (
            (sum(quality_scores) / len(quality_scores) * 15) if quality_scores else 0.0
        )
        graph_signal = 0.0
        score = max(
            0.0,
            min(
                100.0,
                support_score
                - contradiction_penalty
                + recency_score
                + clinical
                + confidence_score
                + evidence_quality
                + graph_signal,
            ),
        )
        citation_ids = list(
            dict.fromkeys(evidence_id for claim in all_claims for evidence_id in claim.evidence_ids)
        )
        explanation = (
            f"Prioritized from {len(support)} supporting, {len(contradiction)} contradicting, "
            f"and {len(associated)} associated claim(s); evidence quality contributes "
            f"{evidence_quality:.1f} points; score is a computational heuristic."
        )
        ranked.append(
            RankedCandidate(
                candidate_id=candidate_id,
                candidate_type=subject_type,
                name=names[candidate_id],
                score=round(score, 2),
                confidence_band=_band(score),
                component_scores={
                    "support": round(support_score, 2),
                    "contradiction_penalty": round(contradiction_penalty, 2),
                    "recency": round(recency_score, 2),
                    "clinical_trial": round(clinical, 2),
                    "confidence": round(confidence_score, 2),
                    "evidence_quality": round(evidence_quality, 2),
                    "graph_signal": round(graph_signal, 2),
                },
                explanation=explanation,
                supporting_claim_ids=[claim.claim_id for claim in support],
                contradicting_claim_ids=[claim.claim_id for claim in contradiction],
                citation_ids=citation_ids,
            )
        )
    return sorted(ranked, key=lambda item: (-item.score, item.candidate_id))


def rank_drugs(records: list[EvidenceRecord], claims: list[Claim]) -> list[RankedCandidate]:
    return rank_candidates(records, claims, "drugs")


def rank_targets(records: list[EvidenceRecord], claims: list[Claim]) -> list[RankedCandidate]:
    return rank_candidates(records, claims, "targets")
