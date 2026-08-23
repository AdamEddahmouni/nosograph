"""Unit tests for TargetHypothesisAgent knowledge-graph unwrapping."""

import datetime

import pytest

from med_research.pipeline.agent.hypothesis_agent import TargetHypothesisAgent, _records

pytestmark = pytest.mark.unit


def test_records_unwraps_genes_payload() -> None:
    payload = {"genes": [{"id": "BRAF", "symbol": "BRAF"}, {"id": "NRAS"}]}
    records = _records(payload, "genes")
    assert [row["id"] for row in records] == ["BRAF", "NRAS"]


def test_evaluate_target_uses_kg_gene_records() -> None:
    agent = TargetHypothesisAgent("melanoma")
    hypothesis = agent.evaluate_target("BRAF")
    assert hypothesis.target_gene == "BRAF"
    assert hypothesis.disease_id == "melanoma"
    assert hypothesis.overall_confidence > 0.5
    assert hypothesis.supporting_evidence


def test_generated_at_is_timezone_aware_utc() -> None:
    agent = TargetHypothesisAgent("melanoma")
    hypothesis = agent.evaluate_target("BRAF")
    generated_at = datetime.datetime.fromisoformat(hypothesis.generated_at)
    assert generated_at.tzinfo is not None
    assert generated_at.utcoffset() == datetime.timedelta(0)
