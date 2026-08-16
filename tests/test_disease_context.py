"""Tests for disease context resolver."""

from med_research.diseases.context import resolve_disease_context


def test_resolve_sle_context() -> None:
    ctx = resolve_disease_context("sle")
    assert ctx["disease_id"] == "sle"
    assert ctx["readiness_tier"] == "L3"
    assert ctx["mondo_curie"] or ctx["efo_id"]
