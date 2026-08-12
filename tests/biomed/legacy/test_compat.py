from __future__ import annotations

import pytest

from med_research.biomed.legacy.compat import legacy_projection_enabled
from med_research.biomed.repository import BiomedicalRepository

DISEASES = ["sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"]


@pytest.mark.parametrize("disease_id", DISEASES)
def test_existing_graph_builder_still_works_after_migration_import(disease_id: str) -> None:
    from med_research.pipeline.knowledge_graph.builder import build_graph

    graph = build_graph(disease_id)
    assert graph.number_of_nodes() > 0


def test_canonical_projection_is_optional_when_snapshot_inactive(
    repository: BiomedicalRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BIOMED_LEGACY_PROJECTION", raising=False)
    assert legacy_projection_enabled(repository) is False
