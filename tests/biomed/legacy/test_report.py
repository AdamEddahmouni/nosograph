from __future__ import annotations

from med_research.biomed.legacy.report import build_parity_report


def test_parity_report_matches_legacy_relationship_count_for_sle() -> None:
    report = build_parity_report("sle")
    assert report.relationships.source_count > 0
    assert report.relationships.imported_count == report.relationships.source_count
    assert report.exceptions == []
