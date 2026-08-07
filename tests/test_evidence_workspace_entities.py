from med_research.pipeline.evidence_workspace.extraction import extract_claims
from med_research.pipeline.evidence_workspace.schemas import EvidenceRecord


def test_deterministic_extraction_captures_variants_and_outcomes():
    record = EvidenceRecord(
        evidence_id="pmid:variant",
        source="pubmed",
        native_id="variant",
        title="SLE biomarker study",
        url="https://pubmed.ncbi.nlm.nih.gov/variant/",
        snippet=(
            "The STAT4 rs7574865 variant was associated with SLE. "
            "The primary outcome was SRI-4 response and the study reported remission."
        ),
    )

    result = extract_claims([record], "sle", enable_llm=False)

    variants = [claim for claim in result.claims if claim.subject_type == "variant"]
    outcomes = [claim for claim in result.claims if claim.subject_type == "outcome"]
    assert any(claim.subject_id == "rs7574865" for claim in variants)
    assert any(claim.subject_id == "sri-4_response" for claim in outcomes)
    assert all(claim.evidence_ids == ["pmid:variant"] for claim in variants + outcomes)
