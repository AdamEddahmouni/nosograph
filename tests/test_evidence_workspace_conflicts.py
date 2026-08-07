from med_research.pipeline.evidence_workspace.extraction import extract_claims
from med_research.pipeline.evidence_workspace.ranking import rank_drugs
from med_research.pipeline.evidence_workspace.schemas import EvidenceRecord


def record(evidence_id, text):
    return EvidenceRecord(
        evidence_id=evidence_id,
        source="pubmed",
        native_id=evidence_id,
        title="SLE evidence",
        url=f"https://pubmed.ncbi.nlm.nih.gov/{evidence_id}/",
        snippet=text,
        evidence_type="RCT",
    )


def test_conflicting_claims_share_group_and_reduce_confidence():
    result = extract_claims(
        [
            record("1", "Baricitinib improved SLE disease activity."),
            record("2", "Baricitinib failed to improve SLE disease activity."),
        ],
        "sle",
        enable_llm=False,
    )
    claims = [claim for claim in result.claims if claim.subject_id == "baricitinib"]

    assert len(claims) == 2
    assert claims[0].conflict_group
    assert claims[0].conflict_group == claims[1].conflict_group
    assert all(claim.confidence_components["conflict_adjustment"] < 1 for claim in claims)


def test_llm_cannot_introduce_unknown_sle_entity():
    class Client:
        def extract(self, records, claims, model=None):
            return [
                {
                    "subject_id": "invented_drug",
                    "subject_type": "drug",
                    "subject_name": "Invented drug",
                    "relationship": "supports",
                    "text": "Invented drug works.",
                    "evidence_ids": ["1"],
                }
            ]

    result = extract_claims([record("1", "JAK1 is relevant to SLE.")], "sle", llm_client=Client())

    assert all(claim.subject_id != "invented_drug" for claim in result.claims)
    assert "invalid claim" in result.warnings[0]


def test_ranking_citation_ids_are_evidence_ids():
    evidence = record("1", "Baricitinib improved SLE disease activity.")
    claims = extract_claims([evidence], "sle", enable_llm=False).claims

    ranked = rank_drugs([evidence], claims)

    assert ranked[0].citation_ids
    assert set(ranked[0].citation_ids) == {"1"}
