from med_research.pipeline.evidence_workspace.extraction import extract_claims
from med_research.pipeline.evidence_workspace.schemas import EvidenceRecord


def _record(text="Baricitinib targets JAK1 in SLE and improved disease activity."):
    return EvidenceRecord(
        evidence_id="pmid:1",
        source="pubmed",
        native_id="1",
        title="JAK study",
        url="https://pubmed.ncbi.nlm.nih.gov/1/",
        snippet=text,
        evidence_type="RCT",
    )


def test_deterministic_extraction_produces_provenance_backed_claims_without_llm():
    result = extract_claims([_record()], "sle", enable_llm=True, llm_client=None)

    assert result.claims
    assert {claim.subject_id for claim in result.claims} >= {"baricitinib", "JAK1"}
    assert all(claim.evidence_ids == ["pmid:1"] for claim in result.claims)
    assert result.llm_status == "skipped"
    assert result.warnings


def test_invalid_llm_claim_is_discarded_but_rules_claim_survives():
    class Client:
        def extract(self, records, claims, model=None):
            return [{"subject_id": "unknown", "subject_type": "drug", "evidence_ids": ["missing"]}]

    result = extract_claims([_record()], "sle", llm_client=Client(), model="test-model")

    assert result.claims
    assert all(claim.extraction_method == "rules" for claim in result.claims)
    assert result.llm_status == "completed"
    assert "invalid claim" in result.warnings[0]


def test_negative_language_creates_contradiction_for_drug():
    result = extract_claims(
        [_record("Baricitinib failed to improve SLE outcomes.")], "sle", enable_llm=False
    )

    drug_claim = next(claim for claim in result.claims if claim.subject_id == "baricitinib")
    assert drug_claim.relationship == "contradicts"
