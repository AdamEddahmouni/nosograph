"""Tests for corpus status reporting."""

from med_research.diseases.corpus_status import build_corpus_status


def test_build_corpus_status_limit() -> None:
    report = build_corpus_status(limit=3, include_symptom_source=False)
    assert report["aggregate"]["total"] == 3
    assert len(report["per_disease"]) == 3
