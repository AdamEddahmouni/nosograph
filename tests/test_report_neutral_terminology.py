"""Report HTML should not leak unrelated SLE/lupus labels for non-SLE diseases."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from med_research.pipeline.reporting import disease_context

pytestmark = pytest.mark.unit

UNRELATED_TERMS = re.compile(r"\b(?:lupus|sle|systemic lupus erythematosus)\b", re.IGNORECASE)


def _visible_text(html: str) -> str:
    """Strip tags/scripts so we only inspect user-visible copy."""
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def _disease_labels(disease_id: str) -> set[str]:
    context = disease_context(disease_id)
    return {
        context["name"],
        context["profile_name"],
        context["short_label"],
        context["name"].split("(")[0].strip(),
    }


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_drug_synergy_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.drug_synergy.engine import compute_synergy
    from med_research.pipeline.drug_synergy.report import generate_html_report

    pairs = compute_synergy(disease_id=disease_id, save=False)
    assert pairs
    report_path = generate_html_report(pairs[:5], disease_id=disease_id)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible


@pytest.mark.parametrize("disease_id", ["ra", "ibd"])
def test_gene_expression_report_avoids_unrelated_lupus_copy(disease_id):
    from med_research.pipeline.gene_expression.correlator import compute_all_correlations
    from med_research.pipeline.gene_expression.report import generate_html_report

    results = compute_all_correlations(disease_id=disease_id, save=False)
    assert results
    report_path = generate_html_report(results[:5], disease_id=disease_id)
    html = Path(report_path).read_text(encoding="utf-8")
    visible = _visible_text(html)
    assert any(label in visible for label in _disease_labels(disease_id) if label)
    assert not UNRELATED_TERMS.search(visible), visible
