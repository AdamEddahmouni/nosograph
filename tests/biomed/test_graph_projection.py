import pytest

from med_research.biomed.graph import project_claim_graph


def test_projection_rejects_unbounded_request(repository) -> None:
    with pytest.raises(ValueError, match="max_hops"):
        project_claim_graph(repository, "MONDO:0007915", max_hops=4)


def test_projection_builds_claim_edges(
    repository, mondo_snapshot, claim, support, sle_entity
) -> None:
    repository.upsert_snapshot(mondo_snapshot)
    repository.upsert_entity(sle_entity)
    repository.activate_snapshot("mondo", mondo_snapshot.id)
    repository.add_claim(claim)
    repository.add_claim_evidence(support)
    graph = project_claim_graph(repository, "MONDO:0007915", max_hops=1, max_nodes=10)
    assert graph.has_edge("MONDO:0007915", "HP:0001945")
