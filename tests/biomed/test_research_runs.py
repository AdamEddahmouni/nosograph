import pytest

from med_research.biomed.errors import RunTransitionError
from med_research.biomed.models import RunStatus


def test_terminal_run_is_immutable(repository, mondo_snapshot, run_create) -> None:
    repository.upsert_snapshot(mondo_snapshot)
    pending = repository.create_research_run(run_create)
    running = repository.transition_research_run(pending.id, RunStatus.RUNNING)
    completed = repository.transition_research_run(
        running.id, RunStatus.COMPLETED, result={"score": 0.75}, warnings=[]
    )
    assert completed.result == {"score": 0.75}
    with pytest.raises(RunTransitionError, match="terminal"):
        repository.transition_research_run(completed.id, RunStatus.FAILED, warnings=["changed"])


def test_identical_run_specs_return_same_run(repository, mondo_snapshot, run_create) -> None:
    repository.upsert_snapshot(mondo_snapshot)
    first = repository.create_research_run(run_create)
    second = repository.create_research_run(run_create)
    assert first.id == second.id
