from med_research.web.models.universal import (
    ClaimEvidenceView,
    ConditionSummary,
    ResearchDisclaimer,
)


def test_research_disclaimer_is_required_on_condition_summary() -> None:
    payload = ConditionSummary.model_validate(
        {
            "curie": "MONDO:0007915",
            "label": "systemic lupus erythematosus",
            "entity_type": "condition",
            "snapshots": [],
            "readiness": {
                "ontology_present": True,
                "legacy_curated": False,
            },
            "disclaimer": ResearchDisclaimer().model_dump(),
        }
    )
    assert "research" in payload.disclaimer.text.lower()


def test_claim_evidence_keeps_directions_separate() -> None:
    evidence = ClaimEvidenceView.model_validate(
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "direction": "supporting",
            "snapshot_id": "00000000-0000-0000-0000-000000000001",
            "source_record_id": "row-1",
        }
    )
    assert evidence.direction == "supporting"
