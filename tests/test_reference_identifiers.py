"""Offline tests for the reference-identifier resolution check."""

from __future__ import annotations

import pytest

from med_research.diseases.base import Disease
from med_research.diseases.identifiers import REFERENCE_DISEASES
from scripts.check_reference_identifiers import (
    Identifier,
    Occurrence,
    Resolution,
    collect_identifiers,
    extract_identifiers,
    resolve_clinvars,
    resolve_dois,
    resolve_pmids,
)

pytestmark = pytest.mark.unit


def test_extract_identifiers_supports_prefixes_and_free_text() -> None:
    found = extract_identifiers(
        "PMID:12345; DOI:10.1038/nature12373. Also PMID 67890 and CLINVAR:7105"
    )

    assert found == [
        ("PMID", "12345"),
        ("PMID", "67890"),
        ("CLINVAR", "7105"),
        ("DOI", "10.1038/nature12373"),
    ]


def test_extract_identifiers_does_not_invent_bare_words() -> None:
    assert extract_identifiers("PMID DOI CLINVAR curator note") == []


def test_collect_identifiers_includes_variant_clinvar_ids() -> None:
    identifiers = collect_identifiers(["cystic_fibrosis", "melanoma"])
    by_key = {(item.scheme, item.value): item for item in identifiers}

    assert ("CLINVAR", "7105") in by_key
    assert ("CLINVAR", "13961") in by_key
    assert any(
        occurrence.record_id == "CFTR" for occurrence in by_key[("CLINVAR", "7105")].occurrences
    )


def test_resolve_pmids_batches_and_marks_missing_ids_dead() -> None:
    seen_urls: list[str] = []

    def fake_request(url: str, *, timeout: float, sleeper) -> dict:
        seen_urls.append(url)
        return {
            "result": {
                "1": {"uid": "1"},
                "2": {"error": "cannot get document summary"},
            }
        }

    results = resolve_pmids(
        ["1", "2"],
        request=fake_request,
        sleeper=lambda _: None,
    )

    assert results["1"].status == "resolved"
    assert results["2"].status == "dead"
    assert "db=pubmed" in seen_urls[0]


def test_resolve_dois_uses_handle_response_code() -> None:
    def fake_request(url: str, *, timeout: float, sleeper) -> dict | None:
        if "missing" in url:
            return None
        return {"responseCode": 1}

    results = resolve_dois(
        ["10.1000/good", "10.1000/missing"],
        request=fake_request,
        sleeper=lambda _: None,
    )

    assert results["10.1000/good"].status == "resolved"
    assert results["10.1000/missing"].status == "dead"


def test_resolve_clinvars_uses_accession_as_validity_signal() -> None:
    def fake_request(url: str, *, timeout: float, sleeper) -> dict:
        return {"result": {"7105": {"accession": "VCV000007105"}}}

    results = resolve_clinvars(
        ["7105"],
        request=fake_request,
        sleeper=lambda _: None,
    )

    assert results["7105"].status == "resolved"


def test_main_fails_on_dead_identifier(monkeypatch, capsys) -> None:
    import scripts.check_reference_identifiers as checker

    identifier = Identifier(
        scheme="PMID",
        value="123",
        occurrences={Occurrence("sle", "genes", "G1")},
    )
    monkeypatch.setattr(checker, "collect_identifiers", lambda ids: [identifier])
    monkeypatch.setattr(
        checker,
        "resolve_all",
        lambda ids, **kwargs: {("PMID", "123"): Resolution("PMID", "123", "dead", "not found")},
    )

    code = checker.main(["--disease", "sle"])
    output = capsys.readouterr().out

    assert code == 1
    assert "DEAD PMID:123" in output
    assert "sle/genes/G1" in output


def test_each_reference_module_has_doi_citation() -> None:
    identifiers = collect_identifiers(REFERENCE_DISEASES)
    doi_diseases = {
        occurrence.disease_id
        for identifier in identifiers
        if identifier.scheme == "DOI"
        for occurrence in identifier.occurrences
    }

    assert set(REFERENCE_DISEASES) <= doi_diseases


def test_curated_variant_records_have_clinvar_provenance() -> None:
    curated = (
        "cystic_fibrosis",
        "melanoma",
        "sle",
        "tuberculosis",
        "als",
        "t2d",
        "ms",
        "ibd",
        "ad",
        "ra",
    )

    for disease_id in curated:
        genes = Disease(disease_id).load_genes()["genes"]
        variant_genes = [gene for gene in genes if gene.get("variants")]
        assert variant_genes, f"{disease_id} has no variant records"
        for gene in variant_genes:
            for variant in gene["variants"]:
                assert variant["clinvar_id"]
                assert variant["hgvs"]
                assert variant["clinical_significance"]
                assert f"CLINVAR:{variant['clinvar_id']}" in gene["references"]


def test_ra_padi4_records_are_explicit_association_variants() -> None:
    genes = Disease("ra").load_genes()["genes"]
    padi4 = next(gene for gene in genes if gene["id"] == "PADI4")

    assert {variant["clinvar_id"] for variant in padi4["variants"]} == {"590790", "590889"}
    assert all(variant["clinical_significance"] == "association" for variant in padi4["variants"])
