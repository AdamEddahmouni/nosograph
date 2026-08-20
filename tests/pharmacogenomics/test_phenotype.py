import pytest

from med_research.pipeline.pharmacogenomics.phenotype import (
    dosing_recommendation,
    phenotype_from_alleles,
)


@pytest.mark.parametrize(
    "gene,alleles,expected",
    [
        ("CYP2D6", ["*4"], "Poor Metabolizer"),
        ("CYP2D6", ["*1", "*10"], "Intermediate Metabolizer"),
        ("CYP2D6", ["*1", "*1"], "Normal Metabolizer"),
        ("CYP2D6", ["*1", "*2"], "Normal Metabolizer"),
        ("CYP2D6", ["*1", "*1", "*1"], "Rapid Metabolizer"),
        ("CYP2D6", ["*1", "*1", "*1", "*1"], "Ultrarapid Metabolizer"),
    ],
)
def test_phenotype_from_alleles(gene, alleles, expected):
    assert phenotype_from_alleles(gene, alleles) == expected


def test_dosing_recommendation_known():
    rec = dosing_recommendation("CYP2D6", "Poor Metabolizer")
    assert "alternative" in rec.lower()


def test_dosing_recommendation_unknown():
    rec = dosing_recommendation("UNKNOWN", "Anything")
    assert rec == "No specific recommendation available."
