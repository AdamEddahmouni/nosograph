from med_research.biomed.models import EvidenceDirection


def test_support_and_contradiction_remain_separate(
    repository, mondo_snapshot, claim, support, contradiction
) -> None:
    repository.upsert_snapshot(mondo_snapshot)
    repository.add_claim(claim)
    repository.add_claim_evidence(support)
    repository.add_claim_evidence(contradiction)
    view = repository.list_claims("MONDO:0007915")[0]
    assert {item.direction for item in view.evidence} == {
        EvidenceDirection.SUPPORTING,
        EvidenceDirection.CONTRADICTORY,
    }


def test_claim_is_current_requires_active_snapshot(
    repository, mondo_snapshot, claim, support
) -> None:
    repository.upsert_snapshot(mondo_snapshot)
    repository.add_claim(claim)
    repository.add_claim_evidence(support)
    assert repository.claim_is_current(claim.id) is False
    repository.activate_snapshot("mondo", mondo_snapshot.id)
    assert repository.claim_is_current(claim.id) is True
