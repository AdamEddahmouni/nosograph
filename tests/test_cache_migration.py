"""Tests for legacy flat-JSON to CacheManager namespace migration."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from med_research.cache import (
    NS_CLINICAL_TRIALS,
    NS_ENRICHMENT,
    NS_EVIDENCE_GATHER,
    NS_GEO,
    NS_GWAS,
    NS_LITERATURE_MINING,
    NS_LLM_EXTRACTOR,
    NS_PPI,
    CacheManager,
    migrate_legacy_caches,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / "central_cache"


@pytest.fixture
def mgr(cache_dir):
    return CacheManager(cache_dir=cache_dir, ttl_seconds=86400)


@pytest.fixture
def legacy_dirs(tmp_path, monkeypatch):
    """Point migration source directories at isolated temp paths."""

    bio = tmp_path / "bioinformatics" / "data"
    lit = tmp_path / "literature_mining" / "data"
    trials = tmp_path / "clinical_trials" / "data"
    evidence = tmp_path / "evidence" / "data"
    geo = tmp_path / "gene_expression" / "data" / "geo_cache"
    for d in (bio, lit, trials, evidence, geo):
        d.mkdir(parents=True)

    monkeypatch.setattr("med_research.cache._BIOINFORMATICS_DATA", bio)
    monkeypatch.setattr("med_research.cache._LITERATURE_DATA", lit)
    monkeypatch.setattr("med_research.cache._CLINICAL_TRIALS_DATA", trials)
    monkeypatch.setattr("med_research.cache._EVIDENCE_DATA", evidence)
    monkeypatch.setattr("med_research.cache._GEO_CACHE_DIR", geo)
    return {
        "bio": bio,
        "lit": lit,
        "trials": trials,
        "evidence": evidence,
        "geo": geo,
    }


def test_migrate_gwas_legacy_file(mgr, legacy_dirs):
    legacy_dirs["bio"].joinpath("gwas_cache_ra.json").write_text(
        json.dumps(
            {
                "gwas_results": {"gene_associations": {}, "total_studies": 1},
                "crossref": {"matches": []},
            }
        ),
        encoding="utf-8",
    )

    summary = migrate_legacy_caches(mgr)
    assert summary["total"]["migrated"] == 1
    cached = mgr.get(NS_GWAS, "ra", ttl_seconds=10**9)
    assert cached is not None
    assert "gwas_results" in cached


def test_migrate_gwas_sle_legacy_filename(mgr, legacy_dirs):
    legacy_dirs["bio"].joinpath("gwas_cache.json").write_text(
        json.dumps(
            {
                "gwas_results": {"gene_associations": {}},
                "crossref": {},
            }
        ),
        encoding="utf-8",
    )

    summary = migrate_legacy_caches(mgr)
    assert summary["total"]["migrated"] == 1
    assert mgr.get(NS_GWAS, "sle", ttl_seconds=10**9) is not None


def test_migrate_enrichment_builds_lookup_key(mgr, legacy_dirs):
    libraries = ["GO_Biological_Process_2023"]
    legacy_dirs["bio"].joinpath("enrichment_cache.json").write_text(
        json.dumps(
            {
                "cache_key": "GENE1,GENE2",
                "libraries": libraries,
                "top_n": 15,
                "results": {"GO_Biological_Process_2023": {"terms": []}},
            }
        ),
        encoding="utf-8",
    )

    summary = migrate_legacy_caches(mgr)
    assert summary["total"]["migrated"] == 1
    lookup_key = 'GENE1,GENE2|||["GO_Biological_Process_2023"]|||15'
    assert mgr.get(NS_ENRICHMENT, lookup_key, ttl_seconds=10**9) is not None


def test_migrate_ppi_legacy_file(mgr, legacy_dirs):
    payload = {
        "cache_key": "TP53,BRCA1",
        "confidence": 0.4,
        "id_map": {"TP53": "9606.ENSP00000269305"},
        "interactions": [],
    }
    legacy_dirs["bio"].joinpath("ppi_cache.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    summary = migrate_legacy_caches(mgr)
    assert summary["total"]["migrated"] == 1
    assert mgr.get(NS_PPI, "TP53,BRCA1|||0.4", ttl_seconds=10**9) == payload


def test_migrate_literature_per_disease(mgr, legacy_dirs):
    articles = [{"pmid": "123", "title": "Test"}]
    legacy_dirs["lit"].joinpath("pubmed_cache_ibd.json").write_text(
        json.dumps(articles),
        encoding="utf-8",
    )

    summary = migrate_legacy_caches(mgr)
    assert summary["total"]["migrated"] == 1
    assert mgr.get(NS_LITERATURE_MINING, "ibd", ttl_seconds=10**9) == articles


def test_migrate_literature_sle_default_filename(mgr, legacy_dirs):
    articles = [{"pmid": "456", "title": "SLE paper"}]
    legacy_dirs["lit"].joinpath("pubmed_cache.json").write_text(
        json.dumps(articles),
        encoding="utf-8",
    )

    summary = migrate_legacy_caches(mgr)
    assert summary["namespaces"]["literature_mining"]["migrated"] == 1
    assert mgr.get(NS_LITERATURE_MINING, "sle", ttl_seconds=10**9) == articles


def test_migrate_all_namespaces_in_one_run(mgr, legacy_dirs):
    legacy_dirs["bio"].joinpath("gwas_cache_ra.json").write_text(
        json.dumps({"gwas_results": {}, "crossref": {}}),
        encoding="utf-8",
    )
    legacy_dirs["bio"].joinpath("enrichment_cache.json").write_text(
        json.dumps(
            {
                "cache_key": "A",
                "libraries": ["GO"],
                "top_n": 10,
                "results": {},
            }
        ),
        encoding="utf-8",
    )
    legacy_dirs["bio"].joinpath("ppi_cache.json").write_text(
        json.dumps({"cache_key": "A", "confidence": 0.4}),
        encoding="utf-8",
    )
    legacy_dirs["lit"].joinpath("pubmed_cache.json").write_text(json.dumps([]), encoding="utf-8")
    legacy_dirs["trials"].joinpath("ct_cache_sle_abc123def456.json").write_text(
        json.dumps({"trials": [], "kg_crossref": {}}),
        encoding="utf-8",
    )
    legacy_dirs["evidence"].joinpath("evidence_cache.json").write_text(
        json.dumps({"q|||pubmed|||5": []}),
        encoding="utf-8",
    )
    legacy_dirs["evidence"].joinpath("extraction_cache.json").write_text(
        json.dumps({"id|||model": {}}),
        encoding="utf-8",
    )
    legacy_dirs["geo"].joinpath("sle_search.json").write_text(json.dumps([]), encoding="utf-8")

    summary = migrate_legacy_caches(mgr)
    assert summary["total"]["migrated"] == 8
    for namespace in (
        "gwas",
        "enrichment",
        "ppi",
        "literature_mining",
        "clinical_trials",
        NS_EVIDENCE_GATHER,
        NS_LLM_EXTRACTOR,
        "geo",
    ):
        assert summary["namespaces"][namespace]["migrated"] == 1


def test_migrate_clinical_trials_legacy_file(mgr, legacy_dirs):
    payload = {"trials": [{"nct_id": "NCT0001"}], "kg_crossref": {}}
    legacy_dirs["trials"].joinpath("ct_cache_sle_a1b2c3d4e5f6.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    summary = migrate_legacy_caches(mgr)
    assert summary["total"]["migrated"] == 1
    assert mgr.get(NS_CLINICAL_TRIALS, "sle|||a1b2c3d4e5f6", ttl_seconds=10**9) == payload


def test_migrate_evidence_and_extractor_dict_caches(mgr, legacy_dirs):
    evidence = {"lupus|||pubmed|||20": [{"title": "Paper"}]}
    extraction = {"pmid123|||gpt-4": {"entities": []}}
    legacy_dirs["evidence"].joinpath("evidence_cache.json").write_text(
        json.dumps(evidence),
        encoding="utf-8",
    )
    legacy_dirs["evidence"].joinpath("extraction_cache.json").write_text(
        json.dumps(extraction),
        encoding="utf-8",
    )

    summary = migrate_legacy_caches(mgr)
    assert summary["total"]["migrated"] == 2
    assert mgr.get(NS_EVIDENCE_GATHER, "lupus|||pubmed|||20", ttl_seconds=10**9) is not None
    assert mgr.get(NS_LLM_EXTRACTOR, "pmid123|||gpt-4", ttl_seconds=10**9) is not None


def test_migrate_geo_directory_files(mgr, legacy_dirs):
    studies = [{"accession": "GSE123"}]
    legacy_dirs["geo"].joinpath("sle_broad_search.json").write_text(
        json.dumps(studies),
        encoding="utf-8",
    )

    summary = migrate_legacy_caches(mgr)
    assert summary["total"]["migrated"] == 1
    assert mgr.get(NS_GEO, "sle_broad_search", ttl_seconds=10**9) == studies


def test_migrate_skips_existing_central_entries(mgr, legacy_dirs):
    mgr.set(NS_GWAS, "ra", {"gwas_results": {}, "crossref": {}})
    legacy_dirs["bio"].joinpath("gwas_cache_ra.json").write_text(
        json.dumps({"gwas_results": {"new": True}, "crossref": {}}),
        encoding="utf-8",
    )

    summary = migrate_legacy_caches(mgr)
    assert summary["total"]["skipped"] == 1
    assert summary["total"]["migrated"] == 0
    cached = mgr.get(NS_GWAS, "ra", ttl_seconds=10**9)
    assert "new" not in cached.get("gwas_results", {})


def test_migrate_dry_run_does_not_write(mgr, legacy_dirs):
    legacy_dirs["bio"].joinpath("gwas_cache.json").write_text(
        json.dumps({"gwas_results": {}, "crossref": {}}),
        encoding="utf-8",
    )

    summary = migrate_legacy_caches(mgr, dry_run=True)
    assert summary["total"]["migrated"] == 1
    assert mgr.get(NS_GWAS, "sle", ttl_seconds=10**9) is None


def test_cache_migrate_cli_command(cache_dir, legacy_dirs, monkeypatch, caplog):
    from med_research.cli import cmd_cache

    def _manager(*_args, **_kwargs):
        return CacheManager(cache_dir=cache_dir, ttl_seconds=86400)

    monkeypatch.setattr("med_research.cache.CacheManager", _manager)
    legacy_dirs["bio"].joinpath("gwas_cache.json").write_text(
        json.dumps({"gwas_results": {}, "crossref": {}}),
        encoding="utf-8",
    )

    assert cmd_cache(SimpleNamespace(cache_action="migrate", dry_run=False)) == 0
    assert "Migration complete" in caplog.text
    assert CacheManager(cache_dir=cache_dir).get(NS_GWAS, "sle", ttl_seconds=10**9) is not None
