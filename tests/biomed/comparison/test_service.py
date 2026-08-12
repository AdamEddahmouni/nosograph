from __future__ import annotations

from med_research.biomed.comparison.models import SimilarityConfig
from med_research.biomed.comparison.service import ConditionComparisonService
from med_research.biomed.models import RunStatus


def test_compare_persists_research_run(biomed_repository) -> None:
    service = ConditionComparisonService(biomed_repository)
    result = service.compare("MONDO:0007915", "MONDO:0008390", SimilarityConfig.v1_default())
    run = biomed_repository.get_research_run(result.run_id)
    assert run is not None
    assert run.status == RunStatus.COMPLETED
    assert run.result is not None
    assert run.result["overall_score"] == result.overall_score
    assert run.fingerprint


def test_replay_with_same_inputs_returns_same_run_id(biomed_repository) -> None:
    service = ConditionComparisonService(biomed_repository)
    config = SimilarityConfig.v1_default()
    first = service.compare("MONDO:0007915", "MONDO:0008390", config)
    second = service.compare("MONDO:0007915", "MONDO:0008390", config)
    assert first.run_id == second.run_id
