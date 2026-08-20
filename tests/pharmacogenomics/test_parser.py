import pytest

from med_research.pipeline.pharmacogenomics.parser import parse_star_allele


@pytest.mark.parametrize(
    "gene,allele_str,expected",
    [
        ("CYP2D6", "*1/*4", {"gene": "CYP2D6", "alleles": ["*1", "*4"]}),
        ("CYP2C19", "*2", {"gene": "CYP2C19", "alleles": ["*2"]}),
    ],
)
def test_parse_star_allele(gene, allele_str, expected):
    result = parse_star_allele(gene, allele_str)
    assert result == expected


def test_unknown_gene():
    with pytest.raises(ValueError):
        parse_star_allele("XYZ", "*1")


def test_unknown_allele():
    with pytest.raises(ValueError):
        parse_star_allele("CYP2D6", "*99")
