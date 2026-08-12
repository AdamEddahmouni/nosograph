from datetime import date

import pytest
from pydantic import ValidationError

from med_research.pipeline.evidence_workspace.schemas import (
    EvidenceRecord,
    ResearchRequest,
    deduplicate_evidence,
)

pytestmark = pytest.mark.unit


def test_request_defaults_to_sle_and_both_sources_and_candidates():
    request = ResearchRequest(question="  Find JAK interventions  ")

    assert request.disease_id == "sle"
    assert request.question == "Find JAK interventions"
    assert request.sources == ("pubmed", "clinical_trials")
    assert request.candidate_type == "both"


def test_request_rejects_empty_question_and_invalid_date_range():
    with pytest.raises(ValidationError):
        ResearchRequest(question="  ")

    with pytest.raises(ValidationError):
        ResearchRequest(
            question="JAK interventions",
            date_from=date(2024, 1, 1),
            date_to=date(2023, 1, 1),
        )


def test_request_rejects_unsupported_source_and_bounds_limit():
    with pytest.raises(ValidationError):
        ResearchRequest(question="JAK", sources=("fda",))

    with pytest.raises(ValidationError):
        ResearchRequest(question="JAK", max_evidence=0)


def test_evidence_deduplication_merges_missing_metadata_and_provenance():
    first = EvidenceRecord(
        evidence_id="pmid:1",
        source="pubmed",
        native_id="1",
        title="JAK study",
        url="https://pubmed.ncbi.nlm.nih.gov/1/",
        snippet="short",
        retrieval_time="2026-08-06T00:00:00Z",
    )
    second = EvidenceRecord(
        evidence_id="pmid:duplicate",
        source="pubmed",
        native_id="1",
        title="JAK study",
        url="https://pubmed.ncbi.nlm.nih.gov/1/",
        doi="10.1000/example",
        snippet="longer abstract",
        retrieval_time="2026-08-06T00:00:01Z",
    )

    result = deduplicate_evidence([first, second])

    assert len(result) == 1
    assert result[0].doi == "10.1000/example"
    assert result[0].snippet == "longer abstract"
    assert result[0].source_ids == ["1"]
    assert result[0].evidence_id == "pmid:1"


def test_request_json_round_trip():
    request = ResearchRequest(
        question="Find JAK/STAT interventions",
        date_from=date(2020, 1, 1),
        enable_llm=False,
    )

    restored = ResearchRequest.model_validate_json(request.model_dump_json())

    assert restored == request
