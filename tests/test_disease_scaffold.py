"""Tests for the disease scaffolding engine (`med-research disease add`).

All external API calls are mocked — no network access required. The
end-to-end test writes a scaffold into the real diseases/ tree (to prove
the knowledge-graph builder and schemas accept it) and cleans up after.
"""

import json
import shutil
from pathlib import Path

import pytest

from med_research.diseases import scaffold
from med_research.diseases.schemas import (
    DrugsFile,
    GenesFile,
    PathwaysFile,
    RelationshipsFile,
)

# ── Fixture payloads (shapes verified against the live APIs) ─────────────

OT_SEARCH_HITS = [
    {"id": "EFO_0001370", "name": "Rheumatoid Arthritis", "entity": "disease"},
    {"id": "EFO_0005855", "name": "Psoriatic arthritis", "entity": "disease"},
]

OT_TARGETS = {
    "data": {
        "disease": {
            "id": "EFO_0001370",
            "name": "Rheumatoid Arthritis",
            "synonyms": ["RA", "Rheumatoid arthritis"],
            "description": {"value": "Chronic inflammatory joint disease."},
            "associatedTargets": {
                "count": 5,
                "rows": [
                    {
                        "score": 0.97,
                        "target": {
                            "id": "ENSG00000232810",
                            "approvedSymbol": "TNF",
                            "approvedName": "Tumor necrosis factor",
                            "biotype": "protein_coding",
                        },
                    },
                    {
                        "score": 0.9,
                        "target": {
                            "id": "ENSG00000175084",
                            "approvedSymbol": "IL6R",
                            "approvedName": "Interleukin-6 receptor",
                            "biotype": "protein_coding",
                        },
                    },
                    {
                        "score": 0.8,
                        "target": {
                            "id": "ENSG00000138378",
                            "approvedSymbol": "STAT4",
                            "approvedName": "Signal transducer and activator of transcription 4",
                            "biotype": "protein_coding",
                        },
                    },
                    {
                        "score": 0.75,
                        "target": {
                            "id": "ENSG00000134242",
                            "approvedSymbol": "PTPN22",
                            "approvedName": "Tyrosine-protein phosphatase non-receptor type 22",
                            "biotype": "protein_coding",
                        },
                    },
                    {
                        "score": 0.7,
                        "target": {
                            "id": "ENSG00000096968",
                            "approvedSymbol": "JAK2",
                            "approvedName": "Tyrosine-protein kinase JAK2",
                            "biotype": "protein_coding",
                        },
                    },
                ],
            },
        }
    }
}

OT_DRUGS = {
    "data": {
        "disease": {
            "knownDrugs": {
                "count": 4,
                "rows": [
                    {
                        "drug": {
                            "id": "CHEMBL1201581",
                            "name": "Adalimumab",
                            "drugType": "Antibody",
                        },
                        "maximumClinicalTrialPhase": 0,
                        "status": "Approved",
                        "target": {"approvedSymbol": "TNF"},
                        "mechanismsOfAction": {
                            "rows": [
                                {
                                    "actionType": "ANTIBODY",
                                    "mechanismOfAction": "TNF-alpha inhibitor",
                                    "target": {"approvedSymbol": "TNF"},
                                }
                            ]
                        },
                    },
                    {
                        "drug": {
                            "id": "CHEMBL2073839",
                            "name": "Baricitinib",
                            "drugType": "Small molecule",
                        },
                        "maximumClinicalTrialPhase": 3,
                        "status": "Phase 3",
                        "target": {"approvedSymbol": "JAK1"},
                        "mechanismsOfAction": {
                            "rows": [
                                {
                                    "actionType": "INHIBITOR",
                                    "mechanismOfAction": "JAK inhibitor",
                                    "target": {"approvedSymbol": "JAK1"},
                                }
                            ]
                        },
                    },
                    {
                        "drug": {
                            "id": "CHEMBL1200490",
                            "name": "Methotrexate",
                            "drugType": "Small molecule",
                        },
                        "maximumClinicalTrialPhase": 0,
                        "status": "Approved",
                        "target": {"approvedSymbol": "TNF"},
                        "mechanismsOfAction": {
                            "rows": [
                                {
                                    "actionType": "INHIBITOR",
                                    "mechanismOfAction": "Dihydrofolate reductase inhibitor",
                                    "target": {"approvedSymbol": "DHFR"},
                                }
                            ]
                        },
                    },
                    {
                        "drug": {
                            "id": "CHEMBL2111306",
                            "name": "GLPG0634",
                            "drugType": "Small molecule",
                        },
                        "maximumClinicalTrialPhase": 2,
                        "status": "Phase 2",
                        "target": {"approvedSymbol": "JAK1"},
                        "mechanismsOfAction": {
                            "rows": [
                                {"actionType": "INHIBITOR", "target": {"approvedSymbol": "JAK1"}}
                            ]
                        },
                    },
                ],
            }
        }
    }
}

GWAS_GENES = [
    {"symbol": "HLA-DRB1", "n_studies": 8, "best_p": 1e-12},
    {"symbol": "TNF", "n_studies": 5, "best_p": 1e-8},
]

REACTOME_HITS = [
    {
        "stId": "R-HSA-1234567",
        "displayName": "Rheumatoid arthritis",
        "schemaClass": "Pathway",
        "description": {"value": "Cytokine signaling in rheumatoid arthritis."},
    }
]

pytestmark = pytest.mark.unit




# ── HTTP mock dispatchers ────────────────────────────────────────────────


def _fake_ot_post(url, payload, timeout=30):
    query = payload.get("query", "")
    if "queryString" in query:
        return {"data": {"search": {"total": 2, "hits": OT_SEARCH_HITS}}}
    if "associatedTargets" in query:
        return OT_TARGETS
    if "drugAndClinicalCandidates" in query or "knownDrugs" in query:
        return OT_DRUGS
    return None


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Route all scaffold HTTP through fixtures; block real calls."""
    monkeypatch.setattr(scaffold, "_http_post_json", _fake_ot_post)
    monkeypatch.setattr(scaffold, "_http_get_json", lambda *a, **k: REACTOME_HITS)
    monkeypatch.setattr(scaffold, "_gwas_genes_for_trait", lambda *a, **k: GWAS_GENES)


# ── Unit tests ───────────────────────────────────────────────────────────


def test_sanitize_id():
    assert scaffold.sanitize_id("Crohn's disease") == "crohns_disease"
    assert scaffold.sanitize_id("Rheumatoid Arthritis") == "rheumatoid_arthritis"
    assert scaffold.sanitize_id("  ") == "disease"
    assert scaffold.sanitize_id("T2D") == "t2d"


def test_search_efo_id():
    assert scaffold.search_efo_id("rheumatoid arthritis") == "EFO_0001370"
    # non-disease hits are skipped
    assert scaffold.search_efo_id("") is None


def test_fetch_ot_associated_targets_filters_and_sorts():
    targets = scaffold.fetch_ot_associated_targets("EFO_0001370", max_genes=10)
    assert [t["symbol"] for t in targets] == ["TNF", "IL6R", "STAT4", "PTPN22", "JAK2"]
    assert targets[0]["score"] == 0.97


def test_fetch_ot_disease_info_handles_single_and_list_description(monkeypatch):
    monkeypatch.setattr(scaffold, "_http_post_json", lambda *a, **k: OT_TARGETS)
    info = scaffold.fetch_ot_disease_info("EFO_0001370")
    assert info["name"] == "Rheumatoid Arthritis"
    assert info["description"] == "Chronic inflammatory joint disease."
    assert "RA" in info["synonyms"]

    # list-shaped description (legacy/mirror responses) also parses
    import copy

    payload = copy.deepcopy(OT_TARGETS)
    payload["data"]["disease"]["description"] = [{"value": "Legacy shape"}]
    monkeypatch.setattr(scaffold, "_http_post_json", lambda *a, **k: payload)
    assert scaffold.fetch_ot_disease_info("EFO_0001370")["description"] == "Legacy shape"


def test_fetch_ot_known_drugs():
    drugs = scaffold.fetch_ot_known_drugs("EFO_0001370", max_drugs=10)
    by_name = {d["name"]: d for d in drugs}
    assert by_name["Adalimumab"]["targets"] == ["TNF"]
    assert by_name["Baricitinib"]["mechanism"] == "JAK inhibitor"
    # phase 0 (approved) drugs sort ahead of investigational ones
    assert drugs[0]["name"] == "Adalimumab"


def test_keyword_pathways():
    genes = [
        {"symbol": "JAK2"},
        {"symbol": "STAT4"},
        {"symbol": "TNF"},
        {"symbol": "IL6R"},
        {"symbol": "IRF5"},
        {"symbol": "HLA-DRB1"},
    ]
    paths = scaffold.keyword_pathways(genes)
    by_name = {p["name"]: p for p in paths}
    assert "JAK-STAT Signaling" in by_name
    assert "JAK2" in by_name["JAK-STAT Signaling"]["key_components"]
    assert "TNF Signaling" in by_name
    assert "Type I Interferon Pathway" in by_name  # via IRF5
    # genes that match nothing (HLA-DRB1) do not create orphan pathways
    assert all(p["key_components"] for p in paths)


def test_build_genes_json_merges_sources():
    genes = scaffold.build_genes_json(
        scaffold.fetch_ot_associated_targets("EFO_0001370"),
        GWAS_GENES,
        disease_id="ra_test",
    )["genes"]
    symbols = {g["id"] for g in genes}
    assert "TNF" in symbols  # both sources
    assert "IL6R" in symbols  # Open Targets only
    assert "HLA-DRB1" in symbols  # GWAS only
    # shared gene carries combined evidence
    tnf = next(g for g in genes if g["id"] == "TNF")
    assert "Open Targets association score" in tnf["disease_evidence"]
    assert "GWAS Catalog" in tnf["disease_evidence"]
    # Open Targets order preserved at the top
    assert genes[0]["id"] == "TNF"


def test_build_drugs_json_approval_mapping():
    drugs = scaffold.build_drugs_json(scaffold.fetch_ot_known_drugs("EFO_0001370"))["drugs"]
    by_name = {d["name"]: d for d in drugs}
    assert by_name["Adalimumab"]["approval"] == "Approved"
    assert by_name["Baricitinib"]["approval"] == "Phase 3"
    assert by_name["GLPG0634"]["approval"] == "Phase 2"
    assert by_name["Adalimumab"]["type"] == "Antibody"


def test_build_pathways_json_merges_reactome_and_keyword():
    reactome = scaffold.fetch_reactome_pathways("Rheumatoid Arthritis")
    genes = scaffold.build_genes_json(
        scaffold.fetch_ot_associated_targets("EFO_0001370"), GWAS_GENES, "ra_test"
    )["genes"]
    paths = scaffold.build_pathways_json(reactome, genes, max_pathways=30)["pathways"]
    names = {p["name"] for p in paths}
    assert "Rheumatoid arthritis" in names  # Reactome hit kept
    assert "JAK-STAT Signaling" in names  # keyword template
    # no duplicate names
    assert len(names) == len(paths)


def test_build_relationships_json():
    genes = scaffold.build_genes_json(
        scaffold.fetch_ot_associated_targets("EFO_0001370"), GWAS_GENES, "ra_test"
    )["genes"]
    drugs = scaffold.build_drugs_json(scaffold.fetch_ot_known_drugs("EFO_0001370"))["drugs"]
    paths = scaffold.build_pathways_json([], genes, max_pathways=30)["pathways"]
    rels = scaffold.build_relationships_json(genes, drugs, paths, "Rheumatoid Arthritis (RA_TEST)")[
        "relationships"
    ]

    types = {r["type"] for r in rels}
    assert types >= {"TARGETS", "TREATS", "PARTICIPATES_IN", "ASSOCIATED_WITH"}

    targets = [r for r in rels if r["type"] == "TARGETS"]
    assert any(r["source"] == "CHEMBL1201581" and r["target"] == "TNF" for r in targets)

    treats = [r for r in rels if r["type"] == "TREATS"]
    # approved (Adalimumab, Methotrexate) yes; Phase 2 (GLPG0634) no
    treated = {r["source"] for r in treats}
    assert "CHEMBL1201581" in treated
    assert "CHEMBL2111306" not in treated

    associated = [r for r in rels if r["type"] == "ASSOCIATED_WITH"]
    assert any(r["source"] == "HLA-DRB1" for r in associated)


def test_generate_config_py_has_required_keys():
    src = scaffold.generate_config_py("ra_test", "Rheumatoid Arthritis")
    for key in (
        "PIPELINE_LABEL",
        "SYMPTOMS",
        "PUBMED_QUERIES",
        "CAR_T_SCORES",
        "DRUG_SAFETY_RISK",
        "SCREENING_PROFILE",
    ):
        assert f"{key} =" in src


def test_generate_config_py_escapes_apostrophes():
    src = scaffold.generate_config_py("bells_palsy", "Bell's palsy")
    compile(src, "<config>", "exec")
    assert "Bell's palsy" in src
    assert "'(Bell's palsy" not in src


# ── End-to-end ───────────────────────────────────────────────────────────


def test_scaffold_disease_end_to_end(tmp_path, monkeypatch):
    summary = scaffold.scaffold_disease(
        "ra_test",
        name="Rheumatoid Arthritis",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
        use_bulk=False,
    )

    assert summary["counts"]["genes"] >= 6  # 5 OT + 1 GWAS-only
    assert summary["counts"]["drugs"] == 4
    assert summary["counts"]["pathways"] > 0
    assert summary["counts"]["relationships"] > 0
    assert summary["sources"]["opentargets"] and summary["sources"]["gwas"]

    data_dir = tmp_path / "data"
    assert (tmp_path / "__init__.py").exists()
    assert (tmp_path / "config.py").exists()
    assert (data_dir / "profile.json").exists()

    # All data files validate against the platform schemas
    genes = json.loads((data_dir / "genes.json").read_text(encoding="utf-8"))
    assert isinstance(GenesFile.model_validate(genes), GenesFile)
    drugs = json.loads((data_dir / "drugs.json").read_text(encoding="utf-8"))
    assert isinstance(DrugsFile.model_validate(drugs), DrugsFile)
    paths = json.loads((data_dir / "pathways.json").read_text(encoding="utf-8"))
    assert isinstance(PathwaysFile.model_validate(paths), PathwaysFile)
    rels = json.loads((data_dir / "relationships.json").read_text(encoding="utf-8"))
    assert isinstance(RelationshipsFile.model_validate(rels), RelationshipsFile)


def test_scaffold_disease_integration_with_builder():
    """Scaffold into the real diseases/ tree and prove build_graph accepts it."""
    from pathlib import Path

    import med_research.diseases as diseases_pkg
    from med_research.pipeline.knowledge_graph.builder import build_graph

    root = Path(diseases_pkg.__file__).parent
    disease_dir = root / "zz_scaffold_test"
    try:
        summary = scaffold.scaffold_disease(
            "zz_scaffold_test",
            name="Scaffold Test Disease",
            efo_id="EFO_0001370",
            target_dir=disease_dir,
            overwrite=True,
            use_cache=False,
            use_bulk=False,
        )
        G = build_graph("zz_scaffold_test")
        assert G.number_of_nodes() > 0
        # relationships resolved: gene->disease edges exist
        disease_node = next(n for n, d in G.nodes(data=True) if d.get("type") == "disease")
        assert G.out_degree(disease_node) >= 0
        # genes connect to the disease node via ASSOCIATED_WITH
        assert any(
            G.has_edge(n, disease_node) for n, d in G.nodes(data=True) if d.get("type") == "gene"
        )
        assert summary["counts"]["genes"] > 0
    finally:
        shutil.rmtree(disease_dir, ignore_errors=True)


def test_scaffold_all_sources_offline_still_valid(tmp_path, monkeypatch):
    """Every external source failing must still produce a usable scaffold."""
    monkeypatch.setattr(scaffold, "_http_post_json", lambda *a, **k: None)
    monkeypatch.setattr(scaffold, "_http_get_json", lambda *a, **k: None)
    monkeypatch.setattr(scaffold, "_gwas_genes_for_trait", lambda *a, **k: [])

    summary = scaffold.scaffold_disease(
        "offline_test",
        name="Offline Disease",
        target_dir=tmp_path,
        use_cache=False,
        use_bulk=False,
    )
    assert summary["counts"]["genes"] == 0
    assert summary["counts"]["drugs"] == 0
    # keyword pathways are derived from nothing -> empty, but files still valid
    data_dir = tmp_path / "data"
    genes = json.loads((data_dir / "genes.json").read_text(encoding="utf-8"))
    assert isinstance(GenesFile.model_validate(genes), GenesFile)
    assert (tmp_path / "__init__.py").exists()


def test_scaffold_existing_raises_without_overwrite(tmp_path):
    scaffold.scaffold_disease(
        "dup_test",
        name="Dup Disease",
        target_dir=tmp_path,
        use_cache=False,
    )
    with pytest.raises(FileExistsError):
        scaffold.scaffold_disease(
            "dup_test",
            name="Dup Disease",
            target_dir=tmp_path,
            use_cache=False,
        )
    # overwrite succeeds
    summary = scaffold.scaffold_disease(
        "dup_test",
        name="Dup Disease",
        target_dir=tmp_path,
        use_cache=False,
        overwrite=True,
    )
    assert summary["disease_id"] == "dup_test"


def test_scaffold_id_is_sanitized(tmp_path):
    # target_dir is an exact write destination; the sanitized id is applied
    # when no target_dir is given (i.e. to the real diseases/ tree).
    summary = scaffold.scaffold_disease(
        "Crohn's Disease",
        name="Crohn's disease",
        target_dir=tmp_path,
        use_cache=False,
    )
    assert summary["disease_id"] == "crohns_disease"
    assert (tmp_path / "__init__.py").exists()
    assert summary["files"][0].startswith(str(tmp_path))


# ── Refresh (merge into existing module) ────────────────────────────────


def test_merge_genes_preserves_curated_fields():
    existing = [
        {
            "id": "TNF",
            "name": "Tumor necrosis factor",
            "chromosome": "6p21.33",
            "function": "Pro-inflammatory cytokine.",
            "category": "Cytokine",
            "lupus_evidence": "Curated note.",
            "disease_evidence": "Curated evidence.",
            "odds_ratio": 1.5,
            "references": ["PMID-1"],
            "sle_evidence": "",
        }
    ]
    fresh = [
        {
            "id": "TNF",
            "name": "Tumor necrosis factor",
            "chromosome": "",
            "function": "",
            "category": "",
            "lupus_evidence": "",
            "disease_evidence": "Open Targets association score 0.97",
            "odds_ratio": None,
            "references": [],
            "sle_evidence": "",
        },
        {
            "id": "NEWGENE",
            "name": "New Gene",
            "chromosome": "",
            "function": "",
            "category": "",
            "lupus_evidence": "",
            "disease_evidence": "GWAS Catalog: 2 study(ies), best p=1.0e-08",
            "odds_ratio": None,
            "references": [],
            "sle_evidence": "",
        },
    ]
    result = scaffold.merge_genes(existing, fresh)
    merged = {g["id"]: g for g in result["genes"]}

    # Curated fields preserved verbatim on the existing gene
    assert merged["TNF"]["category"] == "Cytokine"
    assert merged["TNF"]["function"] == "Pro-inflammatory cytokine."
    assert merged["TNF"]["lupus_evidence"] == "Curated note."
    assert merged["TNF"]["odds_ratio"] == 1.5
    assert merged["TNF"]["references"] == ["PMID-1"]
    assert merged["TNF"]["chromosome"] == "6p21.33"
    # Source evidence appended, curated text never replaced
    assert "Curated evidence." in merged["TNF"]["disease_evidence"]
    assert "Open Targets association score 0.97" in merged["TNF"]["disease_evidence"]
    # New gene added with full scaffold values
    assert "NEWGENE" in merged
    assert "GWAS Catalog" in merged["NEWGENE"]["disease_evidence"]

    assert "NEWGENE" in result["added"]
    assert "TNF" in result["updated"]
    assert "TNF" not in result["kept"]  # updated != kept
    assert "NEWGENE" not in result["kept"]


def test_merge_replaces_stale_source_evidence():
    """Repeated refreshes replace source fragments instead of accumulating."""
    existing = [
        {
            "id": "TLR7",
            "name": "TLR7",
            "category": "Innate Immune Sensing",
            "disease_evidence": "Curated note. | GWAS Catalog: 3 study(ies), best p=1.0e-06",
        }
    ]
    fresh = [
        {
            "id": "TLR7",
            "name": "TLR7",
            "category": "",
            "disease_evidence": "GWAS Catalog: 5 study(ies), best p=1.0e-08",
        }
    ]
    result = scaffold.merge_genes(existing, fresh)
    ev = result["genes"][0]["disease_evidence"]
    assert "Curated note." in ev  # human text preserved
    assert "5 study(ies)" in ev  # fresh source fragment present
    assert "3 study(ies)" not in ev  # stale fragment replaced, not accumulated
    assert ev.count("GWAS Catalog") == 1


def test_merge_backfills_empty_curated_fields():
    existing = [
        {
            "id": "TLR7",
            "name": "TLR7",
            "category": "",
            "function": "",
            "chromosome": "",
            "odds_ratio": None,
            "disease_evidence": "",
        }
    ]
    fresh = [
        {
            "id": "TLR7",
            "name": "TLR7",
            "category": "Innate Immune Sensing",
            "function": "Senses viral RNA.",
            "chromosome": "Xp22",
            "odds_ratio": 2.0,
            "disease_evidence": "Open Targets association score 0.9",
        }
    ]
    result = scaffold.merge_genes(existing, fresh)
    gene = result["genes"][0]
    assert gene["category"] == "Innate Immune Sensing"
    assert gene["function"] == "Senses viral RNA."
    assert gene["chromosome"] == "Xp22"
    assert gene["odds_ratio"] == 2.0
    assert "TLR7" in result["updated"]


def test_merge_genes_keeps_genes_dropped_by_sources():
    existing = [
        {"id": "CURATED", "name": "Curated", "category": "Kept", "disease_evidence": "Manual"}
    ]
    fresh = [{"id": "ONLY_SOURCE", "name": "Source", "disease_evidence": "Auto"}]
    result = scaffold.merge_genes(existing, fresh)
    ids = {g["id"] for g in result["genes"]}
    assert "CURATED" in ids and "ONLY_SOURCE" in ids
    assert "CURATED" in result["kept"]
    assert "ONLY_SOURCE" in result["added"]


def test_merge_drugs_updates_source_fields_preserves_curated():
    existing = [
        {
            "id": "CHEMBL123",
            "name": "Drug A",
            "type": "Small molecule",
            "target": "JAK1",
            "mechanism": "Curated mechanism.",
            "approval": "Phase 2",
            "category": "JAK inhibitor",
            "route": "Oral",
            "efficacy": "Curated efficacy",
            "adverse_effects": "Nausea",
            "references": ["PMID-9"],
            "disease_evidence": "Curated.",
        }
    ]
    fresh = [
        {
            "id": "CHEMBL123",
            "name": "Drug A",
            "type": "Small molecule",
            "target": "JAK1",
            "mechanism": "JAK inhibitor",
            "approval": "Phase 3",
            "category": "",
            "route": "",
            "efficacy": "",
            "adverse_effects": "",
            "references": [],
            "disease_evidence": "Open Targets known-drug association (max phase 3)",
        },
        {
            "id": "CHEMBL456",
            "name": "Drug B",
            "type": "Antibody",
            "target": "TNF",
            "mechanism": "TNF-alpha inhibitor",
            "approval": "Approved",
            "category": "",
            "route": "",
            "efficacy": "",
            "adverse_effects": "",
            "references": [],
            "disease_evidence": "Open Targets known-drug association (max phase 0)",
        },
    ]
    result = scaffold.merge_drugs(existing, fresh)
    merged = {d["id"]: d for d in result["drugs"]}

    # Source-derived approval updates; curated fields survive
    assert merged["CHEMBL123"]["approval"] == "Phase 3"
    assert merged["CHEMBL123"]["mechanism"] == "Curated mechanism."
    assert merged["CHEMBL123"]["category"] == "JAK inhibitor"
    assert merged["CHEMBL123"]["route"] == "Oral"
    assert merged["CHEMBL123"]["efficacy"] == "Curated efficacy"
    assert merged["CHEMBL123"]["adverse_effects"] == "Nausea"
    assert merged["CHEMBL123"]["references"] == ["PMID-9"]
    assert "Open Targets known-drug association" in merged["CHEMBL123"]["disease_evidence"]
    assert "Curated." in merged["CHEMBL123"]["disease_evidence"]

    assert "CHEMBL456" in merged
    assert "CHEMBL456" in result["added"]
    assert "CHEMBL123" in result["updated"]


def test_merge_pathways_unions_components():
    existing = [
        {
            "id": "jak-stat",
            "name": "JAK-STAT Signaling",
            "description": "Curated desc",
            "key_components": ["JAK1"],
            "therapeutic_targets": ["JAK1"],
            "references": ["PMID-1"],
        }
    ]
    fresh = [
        {
            "id": "jak-stat",
            "name": "JAK-STAT Signaling",
            "description": "Auto desc",
            "key_components": ["JAK1", "STAT3"],
            "therapeutic_targets": ["JAK1", "STAT3"],
            "references": [],
        }
    ]
    result = scaffold.merge_pathways(existing, fresh)
    p = result["pathways"][0]
    assert p["description"] == "Curated desc"
    assert set(p["key_components"]) == {"JAK1", "STAT3"}
    assert p["references"] == ["PMID-1"]
    assert "jak-stat" in result["updated"]


def test_refresh_disease_preserves_curation_and_adds_new(tmp_path, monkeypatch):
    """End-to-end: scaffold, curate a field, refresh, verify merge."""
    scaffold.scaffold_disease(
        "ra_refresh",
        name="Rheumatoid Arthritis",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    genes_path = data_dir / "genes.json"

    # Human curation: tag a gene with a category + evidence note
    genes = json.loads(genes_path.read_text(encoding="utf-8"))
    for g in genes["genes"]:
        if g["id"] == "TNF":
            g["category"] = "Cytokine — curated"
            g["function"] = "Curated function text"
    genes_path.write_text(json.dumps(genes, indent=2), encoding="utf-8")

    summary = scaffold.refresh_disease(
        "ra_refresh",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    assert summary["merge"]["genes"]["kept"]

    merged = json.loads(genes_path.read_text(encoding="utf-8"))
    tnf = next(g for g in merged["genes"] if g["id"] == "TNF")
    assert tnf["category"] == "Cytokine — curated"
    assert tnf["function"] == "Curated function text"
    # All genes present and schema-valid
    assert isinstance(GenesFile.model_validate(merged), GenesFile)


def test_refresh_disease_dry_run_writes_nothing(tmp_path):
    scaffold.scaffold_disease(
        "dry_test",
        name="Dry Test",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    genes_path = tmp_path / "data" / "genes.json"
    before = genes_path.read_text(encoding="utf-8")
    summary = scaffold.refresh_disease(
        "dry_test",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
        dry_run=True,
    )
    assert summary["dry_run"] is True
    assert genes_path.read_text(encoding="utf-8") == before


def test_refresh_disease_missing_module_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        scaffold.refresh_disease("no_such_module", target_dir=tmp_path, use_cache=False)


# ── Refresh + prune (--prune) ───────────────────────────────────────────


def _add_orphan_entities(data_dir, with_pathway_ref=True):
    """Inject a gene + drug no source reports, plus an optional pathway ref."""
    genes_path = data_dir / "genes.json"
    genes = json.loads(genes_path.read_text(encoding="utf-8"))
    genes["genes"].append(
        {
            "id": "ORPHAN",
            "name": "Orphan",
            "chromosome": "",
            "function": "",
            "disease_evidence": "Curated legacy",
            "odds_ratio": None,
            "references": [],
            "category": "Curated",
        }
    )
    genes_path.write_text(json.dumps(genes, indent=2), encoding="utf-8")

    drugs_path = data_dir / "drugs.json"
    drugs = json.loads(drugs_path.read_text(encoding="utf-8"))
    drugs["drugs"].append(
        {
            "id": "CHEMBLORPHAN",
            "name": "Orphan drug",
            "type": "",
            "target": "ORPHAN",
            "mechanism": "",
            "approval": "",
            "route": "",
            "efficacy": "",
            "references": [],
            "category": "",
            "disease_evidence": "Curated legacy",
        }
    )
    drugs_path.write_text(json.dumps(drugs, indent=2), encoding="utf-8")

    if with_pathway_ref:
        paths_path = data_dir / "pathways.json"
        paths = json.loads(paths_path.read_text(encoding="utf-8"))
        # Real scaffolded pathways keep key_components == therapeutic_targets;
        # append to both so a prune → restore round-trip is byte-identical.
        for field in ("key_components", "therapeutic_targets"):
            paths["pathways"][0][field].append("ORPHAN")
        paths_path.write_text(json.dumps(paths, indent=2), encoding="utf-8")


def test_refresh_prune_removes_dropped_entities_and_backs_up(tmp_path):
    scaffold.scaffold_disease(
        "prune_test",
        name="Prune Test",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    _add_orphan_entities(data_dir)

    summary = scaffold.refresh_disease(
        "prune_test",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
        prune=True,
        confirm=lambda plan: True,
    )
    p = summary["prune"]
    assert p["enabled"] and not p["aborted"]
    assert "ORPHAN" in p["genes"]
    assert "CHEMBLORPHAN" in p["drugs"]
    assert p["scrubbed_pathways"]
    assert p["backup"] and Path(p["backup"]).exists()

    # Files on disk reflect the prune
    genes = json.loads((data_dir / "genes.json").read_text(encoding="utf-8"))["genes"]
    drugs = json.loads((data_dir / "drugs.json").read_text(encoding="utf-8"))["drugs"]
    assert all(g["id"] != "ORPHAN" for g in genes)
    assert all(d["id"] != "CHEMBLORPHAN" for d in drugs)
    assert any(g["id"] == "TNF" for g in genes)  # curated genes untouched
    # Pathway component references scrubbed
    paths = json.loads((data_dir / "pathways.json").read_text(encoding="utf-8"))["pathways"]
    assert all("ORPHAN" not in (pw.get("key_components") or []) for pw in paths)
    # Pruned ids no longer counted as kept
    assert "ORPHAN" not in summary["merge"]["genes"]["kept"]

    # Backup contains the removed entities for restoration
    backup = json.loads(Path(p["backup"]).read_text(encoding="utf-8"))
    assert [g["id"] for g in backup["genes"]] == ["ORPHAN"]
    assert [d["id"] for d in backup["drugs"]] == ["CHEMBLORPHAN"]


def test_refresh_prune_confirm_decline_aborts(tmp_path):
    """Declining the prune aborts the entire write — no files change."""
    scaffold.scaffold_disease(
        "prune_abort",
        name="Prune Abort",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    _add_orphan_entities(data_dir, with_pathway_ref=False)
    snapshots = {
        fname: (data_dir / fname).read_text(encoding="utf-8")
        for fname in ("genes.json", "drugs.json", "pathways.json", "relationships.json")
    }

    summary = scaffold.refresh_disease(
        "prune_abort",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
        prune=True,
        confirm=lambda plan: False,
    )
    p = summary["prune"]
    assert p["enabled"] and p["aborted"]
    assert p["backup"] is None
    # Nothing on disk changed — orphan and merge both stayed away
    for fname, before in snapshots.items():
        assert (data_dir / fname).read_text(encoding="utf-8") == before


def test_refresh_prune_dry_run_reports_without_writing(tmp_path):
    scaffold.scaffold_disease(
        "prune_dry",
        name="Prune Dry",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    _add_orphan_entities(data_dir, with_pathway_ref=False)
    before = (data_dir / "genes.json").read_text(encoding="utf-8")

    def _never_called(plan):
        raise AssertionError("confirm must not run during a dry run")

    summary = scaffold.refresh_disease(
        "prune_dry",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
        prune=True,
        dry_run=True,
        confirm=_never_called,
    )
    p = summary["prune"]
    assert p["enabled"] and not p["aborted"]
    assert "ORPHAN" in p["genes"]
    assert p["backup"] is None
    assert (data_dir / "genes.json").read_text(encoding="utf-8") == before


def test_refresh_prune_nothing_to_prune_skips_confirm(tmp_path):
    """Fresh sources report the same entities → no candidates, no prompt."""
    scaffold.scaffold_disease(
        "prune_clean",
        name="Prune Clean",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    called = {"n": 0}

    def _confirm(plan):
        called["n"] += 1
        return True

    summary = scaffold.refresh_disease(
        "prune_clean",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
        prune=True,
        confirm=_confirm,
    )
    assert called["n"] == 0
    assert summary["prune"]["enabled"] and not summary["prune"]["aborted"]
    assert summary["prune"]["genes"] == []
    assert summary["prune"]["drugs"] == []
    assert summary["prune"]["backup"] is None


# ── CLI wiring ───────────────────────────────────────────────────────────


def test_cli_parser_has_disease_subcommands():
    from med_research.cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args(
        ["disease", "add", "crohns", "--name", "Crohn's disease", "--efo", "EFO_0000384"]
    )
    assert args.command == "disease"
    assert args.disease_action == "add"
    assert args.disease_id == "crohns"
    assert args.efo == "EFO_0000384"

    args = parser.parse_args(["disease", "validate", "sle"])
    assert args.disease_action == "validate"
    assert args.disease_id == "sle"

    args = parser.parse_args(["disease", "refresh", "sle", "--dry-run", "--skip-gwas"])
    assert args.disease_action == "refresh"
    assert args.disease_id == "sle"
    assert args.dry_run is True
    assert args.skip_gwas is True

    args = parser.parse_args(["disease", "refresh", "sle", "--prune", "--yes"])
    assert args.prune is True
    assert args.yes is True

    args = parser.parse_args(
        ["disease", "restore", "sle", "--backup", "data/backups/pruned_sle_x.json", "--dry-run"]
    )
    assert args.disease_action == "restore"
    assert args.disease_id == "sle"
    assert args.backup == "data/backups/pruned_sle_x.json"
    assert args.dry_run is True

    args = parser.parse_args(["disease", "backups", "sle", "--purge", "--keep", "3", "--yes"])
    assert args.disease_action == "backups"
    assert args.disease_id == "sle"
    assert args.purge is True
    assert args.keep == 3
    assert args.yes is True


def test_cmd_disease_refresh_missing_module(caplog):
    from med_research.cli import _build_parser, cmd_disease

    parser = _build_parser()
    assert cmd_disease(parser.parse_args(["disease", "refresh", "no_such_disease"])) == 1
    assert "disease add" in caplog.text


def test_cmd_disease_refresh_prune_wiring(monkeypatch):
    """--prune/--yes flow through to refresh_disease's confirm gate."""
    import med_research.diseases.scaffold as scaf
    from med_research.cli import _build_parser, cmd_disease

    captured = {}

    def fake_refresh(**kwargs):
        captured.update(kwargs)
        return {
            "disease_id": "sle",
            "name": "Systemic Lupus",
            "efo_id": None,
            "root": "/tmp",
            "dry_run": kwargs["dry_run"],
            "sources": {},
            "merge": {
                "genes": {"added": [], "updated": [], "kept": []},
                "drugs": {"added": [], "updated": [], "kept": []},
                "pathways": {"added": [], "updated": [], "kept": []},
            },
            "counts": {"genes": 0, "drugs": 0, "pathways": 0, "relationships": 0},
            "files": [],
            "prune": {
                "enabled": kwargs["prune"],
                "aborted": False,
                "genes": [],
                "drugs": [],
                "scrubbed_pathways": [],
                "backup": None,
            },
        }

    monkeypatch.setattr(scaf, "refresh_disease", fake_refresh)
    monkeypatch.setattr(scaf, "print_refresh_summary", lambda s: None)
    parser = _build_parser()

    # --prune --yes → prune enabled, no interactive prompt
    cmd_disease(parser.parse_args(["disease", "refresh", "sle", "--prune", "--yes"]))
    assert captured["prune"] is True
    assert captured["confirm"] is None

    # --prune alone → confirmation callback provided
    cmd_disease(parser.parse_args(["disease", "refresh", "sle", "--prune"]))
    assert callable(captured["confirm"])

    # --prune + --dry-run → nothing written, so no prompt
    cmd_disease(parser.parse_args(["disease", "refresh", "sle", "--prune", "--dry-run"]))
    assert captured["confirm"] is None

    # no --prune → prune stays off, no prompt
    cmd_disease(parser.parse_args(["disease", "refresh", "sle"]))
    assert captured["prune"] is False
    assert captured["confirm"] is None


# ── Restore (undo --prune) ────────────────────────────────────────────


def _rebuild_relationships(data_dir, disease_label):
    """Rebuild relationships.json from the current entity files."""
    genes = json.loads((data_dir / "genes.json").read_text(encoding="utf-8"))["genes"]
    drugs = json.loads((data_dir / "drugs.json").read_text(encoding="utf-8"))["drugs"]
    paths = json.loads((data_dir / "pathways.json").read_text(encoding="utf-8"))["pathways"]
    rels = scaffold.build_relationships_json(genes, drugs, paths, disease_label)
    (data_dir / "relationships.json").write_text(
        json.dumps(rels, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def test_prune_then_restore_round_trip(tmp_path):
    """A full prune → restore cycle returns the module to its pre-prune shape."""
    from med_research.diseases import audit

    scaffold.scaffold_disease(
        "roundtrip",
        name="Roundtrip",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    _add_orphan_entities(data_dir)  # ORPHAN + CHEMBLORPHAN + pathway refs
    # Keep relationships.json consistent with the injected entities (as a real
    # curated module would be), so the round-trip comparison is meaningful.
    label = next(
        r["target"]
        for r in json.loads((data_dir / "relationships.json").read_text(encoding="utf-8"))[
            "relationships"
        ]
        if r["type"] == "ASSOCIATED_WITH"
    )
    _rebuild_relationships(data_dir, label)

    pre_prune = {
        fname: (data_dir / fname).read_text(encoding="utf-8")
        for fname in ("genes.json", "drugs.json", "pathways.json", "relationships.json")
    }

    summary = scaffold.refresh_disease(
        "roundtrip",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
        prune=True,
        confirm=lambda plan: True,
    )
    backup = summary["prune"]["backup"]
    assert backup and Path(backup).exists()
    genes = json.loads((data_dir / "genes.json").read_text(encoding="utf-8"))["genes"]
    assert all(g["id"] != "ORPHAN" for g in genes)

    restored = scaffold.restore_disease("roundtrip", backup_path=backup, target_dir=tmp_path)
    assert restored["restored"] == {"genes": ["ORPHAN"], "drugs": ["CHEMBLORPHAN"]}
    assert restored["skipped"] == {"genes": [], "drugs": []}
    assert restored["updated_pathways"]  # membership re-attached

    # The module is byte-identical to its pre-prune state
    for fname, before in pre_prune.items():
        assert (data_dir / fname).read_text(encoding="utf-8") == before

    # Both mutations are traceable in the audit log
    entries = audit.read_audit("roundtrip", target_dir=tmp_path)
    assert [e["action"] for e in entries] == ["prune", "restore"]


def test_restore_auto_selects_newest_backup(tmp_path):
    scaffold.scaffold_disease(
        "auto_restore",
        name="Auto Restore",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    _write_backup(data_dir, "auto_restore", "20260101_000000_000000", genes=["OLD"])
    _write_backup(data_dir, "auto_restore", "20260102_000000_000000", genes=["NEW"])

    summary = scaffold.restore_disease("auto_restore", target_dir=tmp_path)
    assert summary["restored"]["genes"] == ["NEW"]
    assert Path(summary["backup"]).name.startswith("pruned_auto_restore_20260102")


def test_restore_legacy_backup_reattaches_pathway_by_keyword(tmp_path):
    """Backups without a membership map fall back to keyword matching."""
    scaffold.scaffold_disease(
        "legacy",
        name="Legacy",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    backup = data_dir / "backups" / "pruned_legacy_20260101_000000_000000.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(
        json.dumps(
            {
                "disease_id": "legacy",
                "pruned_at": "2026-01-01T00:00:00",
                "genes": [
                    {
                        "id": "IL6",
                        "name": "IL6",
                        "chromosome": "",
                        "function": "",
                        "disease_evidence": "legacy",
                        "odds_ratio": None,
                        "references": [],
                        "category": "",
                    }
                ],
                "drugs": [],
                # no pathway_memberships key → the keyword template must re-attach IL6
            }
        ),
        encoding="utf-8",
    )

    summary = scaffold.restore_disease("legacy", backup_path=backup, target_dir=tmp_path)
    assert summary["restored"]["genes"] == ["IL6"]
    paths = json.loads((data_dir / "pathways.json").read_text(encoding="utf-8"))["pathways"]
    il6 = next(p for p in paths if p["id"] == "il6-signaling")
    assert "IL6" in il6["key_components"]


def test_restore_skips_entities_already_present(tmp_path):
    scaffold.scaffold_disease(
        "skip_restore",
        name="Skip Restore",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    backup = data_dir / "backups" / "pruned_skip_restore_20260101_000000_000000.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(
        json.dumps(
            {
                "disease_id": "skip_restore",
                "pruned_at": "2026-01-01T00:00:00",
                "genes": [{"id": "TNF", "name": "TNF"}, {"id": "IL6", "name": "IL6"}],
                "drugs": [],
            }
        ),
        encoding="utf-8",
    )

    summary = scaffold.restore_disease("skip_restore", backup_path=backup, target_dir=tmp_path)
    assert summary["restored"]["genes"] == ["IL6"]
    assert summary["skipped"]["genes"] == ["TNF"]


def test_restore_dry_run_writes_nothing(tmp_path):
    scaffold.scaffold_disease(
        "dry_restore",
        name="Dry Restore",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    _write_backup(data_dir, "dry_restore", "20260101_000000_000000", genes=["IL6"])
    before = {
        fname: (data_dir / fname).read_text(encoding="utf-8")
        for fname in ("genes.json", "drugs.json", "pathways.json", "relationships.json")
    }
    summary = scaffold.restore_disease("dry_restore", target_dir=tmp_path, dry_run=True)
    assert summary["dry_run"] is True
    assert summary["restored"]["genes"] == ["IL6"]
    for fname, content in before.items():
        assert (data_dir / fname).read_text(encoding="utf-8") == content


def test_restore_missing_backup_raises(tmp_path):
    scaffold.scaffold_disease(
        "no_backup",
        name="No Backup",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    with pytest.raises(FileNotFoundError, match="Backup file not found"):
        scaffold.restore_disease(
            "no_backup",
            backup_path=tmp_path / "data" / "backups" / "nope.json",
            target_dir=tmp_path,
        )
    with pytest.raises(FileNotFoundError, match="No pruned backups"):
        scaffold.restore_disease("no_backup", target_dir=tmp_path)


def test_restore_unparseable_backup_raises(tmp_path):
    scaffold.scaffold_disease(
        "bad_backup",
        name="Bad Backup",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    bad = data_dir / "backups" / "pruned_bad_backup_20260101_000000_000000.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Could not parse backup"):
        scaffold.restore_disease("bad_backup", target_dir=tmp_path)


def test_restore_wrong_disease_backup_warns(tmp_path, caplog):
    """Restoring another disease's backup warns but still proceeds."""
    import logging

    scaffold.scaffold_disease(
        "ms_restore",
        name="MS Restore",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    foreign = data_dir / "backups" / "pruned_other_20260101_000000_000000.json"
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign.write_text(
        json.dumps(
            {
                "disease_id": "other",
                "pruned_at": "2026-01-01T00:00:00",
                "genes": [{"id": "IL6", "name": "IL6"}],
                "drugs": [],
            }
        ),
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        summary = scaffold.restore_disease("ms_restore", backup_path=foreign, target_dir=tmp_path)
    assert summary["backup_disease_id"] == "other"
    assert any("created for" in r.message for r in caplog.records)


# ── Backup housekeeping (list / purge) ────────────────────────────────


def _write_backup(data_dir, disease_id, ts, genes=(), drugs=(), memberships=None):
    """Craft a pruned backup file with a fixed timestamp (for ordering)."""
    p = data_dir / "backups" / f"pruned_{disease_id}_{ts}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "disease_id": disease_id,
        "pruned_at": ts.replace("_", "T"),
        "genes": [{"id": g, "name": g} for g in genes],
        "drugs": [{"id": d, "name": d} for d in drugs],
    }
    if memberships is not None:
        payload["pathway_memberships"] = memberships
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_list_backups_inventory(tmp_path):
    scaffold.scaffold_disease(
        "inv_test",
        name="Inv Test",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    _write_backup(
        data_dir, "inv_test", "20260102_000000_000000", genes=["ORPHAN"], drugs=["CHEMBLORPHAN"]
    )
    _write_backup(data_dir, "inv_test", "20260101_000000_000000", genes=["TLR7"])

    inv = scaffold.list_backups("inv_test", target_dir=tmp_path)
    assert inv["count"] == 2
    # Newest first
    assert Path(inv["backups"][0]["path"]).name.startswith("pruned_inv_test_20260102")
    assert inv["backups"][0]["genes"] == ["ORPHAN"]
    assert inv["backups"][0]["drugs"] == ["CHEMBLORPHAN"]
    assert inv["backups"][1]["genes"] == ["TLR7"]
    assert all(e["readable"] for e in inv["backups"])
    assert inv["total_size_bytes"] > 0

    # Other diseases' backups are ignored
    _write_backup(data_dir, "other", "20260103_000000_000000", genes=["X"])
    assert scaffold.list_backups("inv_test", target_dir=tmp_path)["count"] == 2


def test_purge_backups_keeps_newest(tmp_path):
    scaffold.scaffold_disease(
        "purge_test",
        name="Purge Test",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    oldest = _write_backup(data_dir, "purge_test", "20260101_000000_000000", genes=["A"])
    middle = _write_backup(data_dir, "purge_test", "20260102_000000_000000", genes=["B"])
    newest = _write_backup(data_dir, "purge_test", "20260103_000000_000000", genes=["C"])

    r = scaffold.purge_backups("purge_test", keep=2, target_dir=tmp_path)
    p = r["purge"]
    assert not p["aborted"] and not p["dry_run"]
    assert len(p["deleted"]) == 1 and len(p["kept"]) == 2
    assert p["deleted"][0] == str(oldest)
    assert oldest.exists() is False
    assert middle.exists() and newest.exists()
    assert p["freed_bytes"] > 0

    # keep=0 deletes everything
    r = scaffold.purge_backups("purge_test", keep=0, target_dir=tmp_path)
    assert middle.exists() is False and newest.exists() is False


def test_purge_backups_confirm_decline_and_dry_run(tmp_path):
    scaffold.scaffold_disease(
        "purge_abort",
        name="Purge Abort",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    old = _write_backup(data_dir, "purge_abort", "20260101_000000_000000", genes=["A"])
    new = _write_backup(data_dir, "purge_abort", "20260102_000000_000000", genes=["B"])

    # Decline → nothing deleted
    r = scaffold.purge_backups(
        "purge_abort", keep=1, target_dir=tmp_path, confirm=lambda entries: False
    )
    assert r["purge"]["aborted"] and r["purge"]["deleted"] == []
    assert old.exists() and new.exists()

    # Dry-run → nothing deleted, preview lists candidates
    r = scaffold.purge_backups("purge_abort", keep=1, target_dir=tmp_path, dry_run=True)
    assert r["purge"]["dry_run"] and len(r["purge"]["deleted"]) == 1
    assert old.exists()


def test_purge_nothing_to_delete(tmp_path):
    scaffold.scaffold_disease(
        "purge_none",
        name="Purge None",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    _write_backup(tmp_path / "data", "purge_none", "20260101_000000_000000", genes=["A"])
    called = {"n": 0}

    def _confirm(entries):
        called["n"] += 1
        return True

    r = scaffold.purge_backups("purge_none", keep=5, target_dir=tmp_path, confirm=_confirm)
    assert called["n"] == 0  # nothing to delete → no prompt
    assert r["purge"]["deleted"] == []


def test_list_backups_unreadable_file_flagged(tmp_path):
    scaffold.scaffold_disease(
        "inv_bad",
        name="Inv Bad",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    good = _write_backup(data_dir, "inv_bad", "20260102_000000_000000", genes=["A"])
    bad = data_dir / "backups" / "pruned_inv_bad_20260101_000000_000000.json"
    bad.write_text("{not json", encoding="utf-8")

    inv = scaffold.list_backups("inv_bad", target_dir=tmp_path)
    by_name = {Path(e["path"]).name: e for e in inv["backups"]}
    assert by_name[good.name]["readable"] is True
    assert by_name[bad.name]["readable"] is False
    assert by_name[bad.name]["genes"] == []
    assert inv["count"] == 2  # still counted, just not readable


def test_list_backups_missing_module_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="disease add"):
        scaffold.list_backups("no_module", target_dir=tmp_path)


def test_print_backups_summary_heads(caplog):
    """Lock in the four inventory/purge head variants."""
    base = {
        "disease_id": "sle",
        "backups": [],
        "count": 0,
        "total_size_bytes": 0,
    }
    entry = {
        "path": "data/backups/pruned_sle_20260101_000000_000000.json",
        "size_bytes": 100,
        "modified": "2026-01-01T00:00:00",
        "genes": ["ORPHAN"],
        "drugs": [],
        "backup_disease_id": "sle",
        "readable": True,
    }
    inv = {**base, "backups": [entry], "count": 1, "total_size_bytes": 100}

    # Plain inventory
    scaffold.print_backups_summary(inv)
    assert "💾 BACKUP INVENTORY: sle" in caplog.text
    assert "Restores: 1 gene(s)" in caplog.text

    # Dry-run purge
    caplog.clear()
    scaffold.print_backups_summary(
        {
            **inv,
            "purge": {
                "enabled": True,
                "aborted": False,
                "keep": 1,
                "dry_run": True,
                "deleted": [entry["path"]],
                "freed_bytes": 100,
                "kept": [],
            },
        }
    )
    assert "🗑️  PURGE PREVIEW (dry-run — nothing deleted)" in caplog.text
    assert "Would delete: 1 backup(s)" in caplog.text

    # Aborted purge
    caplog.clear()
    scaffold.print_backups_summary(
        {
            **inv,
            "purge": {
                "enabled": True,
                "aborted": True,
                "keep": 1,
                "dry_run": False,
                "deleted": [],
                "freed_bytes": 0,
                "kept": [entry["path"]],
            },
        }
    )
    assert "⚠️  PURGE ABORTED — nothing deleted" in caplog.text
    assert "cancelled by user" in caplog.text

    # Applied purge
    caplog.clear()
    scaffold.print_backups_summary(
        {
            **inv,
            "purge": {
                "enabled": True,
                "aborted": False,
                "keep": 0,
                "dry_run": False,
                "deleted": [entry["path"]],
                "freed_bytes": 100,
                "kept": [],
            },
        }
    )
    assert "🗑️  BACKUPS PURGED: sle" in caplog.text
    assert "Deleted: 1 backup(s), 100 bytes freed" in caplog.text


# ── Restore (re-merge a pruned backup) ────────────────────────────────


def test_restore_disease_round_trip(tmp_path):
    """Prune → restore returns the module (entities + pathway membership)."""
    scaffold.scaffold_disease(
        "restore_test",
        name="Restore Test",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    _add_orphan_entities(data_dir)  # ORPHAN gene, CHEMBLORPHAN drug, pathway ref

    pruned = scaffold.refresh_disease(
        "restore_test",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
        prune=True,
        confirm=lambda plan: True,
    )
    backup = pruned["prune"]["backup"]
    assert backup and Path(backup).exists()

    # Prune removed the orphan + its pathway membership
    genes = json.loads((data_dir / "genes.json").read_text(encoding="utf-8"))["genes"]
    assert all(g["id"] != "ORPHAN" for g in genes)
    paths = json.loads((data_dir / "pathways.json").read_text(encoding="utf-8"))["pathways"]
    assert all("ORPHAN" not in (pw.get("key_components") or []) for pw in paths)

    # Restore from the backup
    r = scaffold.restore_disease("restore_test", backup_path=backup, target_dir=tmp_path)
    assert "ORPHAN" in r["restored"]["genes"]
    assert "CHEMBLORPHAN" in r["restored"]["drugs"]
    assert r["updated_pathways"]  # membership re-attached

    # Gene restored verbatim (curated fields intact)
    genes = json.loads((data_dir / "genes.json").read_text(encoding="utf-8"))["genes"]
    orphan = next(g for g in genes if g["id"] == "ORPHAN")
    assert orphan["category"] == "Curated"
    assert orphan["disease_evidence"] == "Curated legacy"
    assert orphan["name"] == "Orphan"
    # Drug restored
    drugs = json.loads((data_dir / "drugs.json").read_text(encoding="utf-8"))["drugs"]
    assert any(d["id"] == "CHEMBLORPHAN" for d in drugs)
    # Pathway membership back
    paths = json.loads((data_dir / "pathways.json").read_text(encoding="utf-8"))["pathways"]
    assert any("ORPHAN" in (pw.get("key_components") or []) for pw in paths)
    # Relationships rebuilt for the restored entities
    rels = json.loads((data_dir / "relationships.json").read_text(encoding="utf-8"))[
        "relationships"
    ]
    assert any(x["source"] == "CHEMBLORPHAN" and x["type"] == "TARGETS" for x in rels)
    assert any(x["source"] == "ORPHAN" and x["type"] == "ASSOCIATED_WITH" for x in rels)


def test_restore_disease_skips_existing_ids(tmp_path):
    scaffold.scaffold_disease(
        "restore_skip",
        name="Restore Skip",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    backup = tmp_path / "backup.json"
    backup.write_text(
        json.dumps(
            {
                "disease_id": "restore_skip",
                "pruned_at": "2026-01-01T00:00:00",
                "genes": [
                    {
                        "id": "TNF",
                        "name": "Tumor necrosis factor",
                        "chromosome": "",
                        "function": "",
                        "disease_evidence": "Curated",
                        "odds_ratio": None,
                        "references": [],
                        "category": "Cytokine",
                    }
                ],
                "drugs": [],
            }
        ),
        encoding="utf-8",
    )

    r = scaffold.restore_disease("restore_skip", backup_path=backup, target_dir=tmp_path)
    assert "TNF" in r["skipped"]["genes"]
    assert "TNF" not in r["restored"]["genes"]
    # Not duplicated
    genes = json.loads((tmp_path / "data" / "genes.json").read_text(encoding="utf-8"))["genes"]
    assert sum(1 for g in genes if g["id"] == "TNF") == 1


def test_restore_disease_default_backup_and_dry_run(tmp_path):
    scaffold.scaffold_disease(
        "restore_dry",
        name="Restore Dry",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    data_dir = tmp_path / "data"
    _add_orphan_entities(data_dir, with_pathway_ref=False)
    pruned = scaffold.refresh_disease(
        "restore_dry",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
        prune=True,
        confirm=lambda plan: True,
    )
    before = (data_dir / "genes.json").read_text(encoding="utf-8")

    # No explicit --backup → newest backup for the disease is used
    r = scaffold.restore_disease("restore_dry", target_dir=tmp_path, dry_run=True)
    assert r["dry_run"] is True
    assert r["backup"] == pruned["prune"]["backup"]
    assert "ORPHAN" in r["restored"]["genes"]
    # Nothing written
    assert (data_dir / "genes.json").read_text(encoding="utf-8") == before


def test_restore_disease_legacy_backup_fuzzy_membership(tmp_path):
    """Backups without pathway_memberships fall back to keyword matching."""
    scaffold.scaffold_disease(
        "restore_legacy",
        name="Restore Legacy",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    # Pre-feature backup: no pathway_memberships key. Gene "FAS" is not in the
    # module but keyword-matches the tnf-signaling template (which exists).
    backup = tmp_path / "legacy.json"
    backup.write_text(
        json.dumps(
            {
                "disease_id": "restore_legacy",
                "pruned_at": "2026-01-01T00:00:00",
                "genes": [
                    {
                        "id": "FAS",
                        "name": "FAS",
                        "chromosome": "",
                        "function": "",
                        "disease_evidence": "Legacy",
                        "odds_ratio": None,
                        "references": [],
                        "category": "",
                    }
                ],
                "drugs": [],
            }
        ),
        encoding="utf-8",
    )

    r = scaffold.restore_disease("restore_legacy", backup_path=backup, target_dir=tmp_path)
    assert "FAS" in r["restored"]["genes"]
    assert "tnf-signaling" in r["updated_pathways"]
    paths = json.loads((tmp_path / "data" / "pathways.json").read_text(encoding="utf-8"))[
        "pathways"
    ]
    tnf = next(p for p in paths if p["id"] == "tnf-signaling")
    assert "FAS" in tnf["key_components"]


def test_restore_disease_backup_errors(tmp_path):
    scaffold.scaffold_disease(
        "restore_err",
        name="Restore Err",
        efo_id="EFO_0001370",
        target_dir=tmp_path,
        use_cache=False,
    )
    # Missing module
    with pytest.raises(FileNotFoundError):
        scaffold.restore_disease("no_module", target_dir=tmp_path)
    # Explicit backup missing
    with pytest.raises(FileNotFoundError):
        scaffold.restore_disease(
            "restore_err", backup_path=tmp_path / "nope.json", target_dir=tmp_path
        )
    # No backups for the disease → clear error
    with pytest.raises(FileNotFoundError, match="No pruned backups"):
        scaffold.restore_disease("restore_err", target_dir=tmp_path)
    # Unparseable JSON
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Could not parse"):
        scaffold.restore_disease("restore_err", backup_path=bad, target_dir=tmp_path)
    # Wrong shape (not a prune backup)
    bad2 = tmp_path / "bad2.json"
    bad2.write_text(json.dumps({"foo": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a prune backup"):
        scaffold.restore_disease("restore_err", backup_path=bad2, target_dir=tmp_path)


def test_cmd_disease_backups_wiring(monkeypatch):
    """List vs purge dispatch and flag plumbing for `disease backups`."""
    import med_research.diseases.scaffold as scaf
    from med_research.cli import _build_parser, cmd_disease

    captured = {}
    calls = []

    def fake_list(disease_id, target_dir=None):
        calls.append(("list", disease_id))
        return {"disease_id": disease_id, "backups": [], "count": 0, "total_size_bytes": 0}

    def fake_purge(disease_id, keep=5, target_dir=None, dry_run=False, confirm=None):
        calls.append(("purge", disease_id, keep, dry_run, confirm))
        captured.update(keep=keep, dry_run=dry_run, confirm=confirm)
        return {
            "disease_id": disease_id,
            "backups": [],
            "count": 0,
            "total_size_bytes": 0,
            "purge": {
                "enabled": True,
                "aborted": False,
                "keep": keep,
                "dry_run": dry_run,
                "deleted": [],
                "freed_bytes": 0,
                "kept": [],
            },
        }

    monkeypatch.setattr(scaf, "list_backups", fake_list)
    monkeypatch.setattr(scaf, "purge_backups", fake_purge)
    monkeypatch.setattr(scaf, "print_backups_summary", lambda s: None)
    parser = _build_parser()

    # Plain list
    cmd_disease(parser.parse_args(["disease", "backups", "sle"]))
    assert calls[-1] == ("list", "sle")

    # Purge with --yes → no prompt
    cmd_disease(parser.parse_args(["disease", "backups", "sle", "--purge", "--keep", "3", "--yes"]))
    assert calls[-1][0] == "purge" and calls[-1][2] == 3
    assert captured["confirm"] is None

    # Purge without --yes → confirmation callback
    cmd_disease(parser.parse_args(["disease", "backups", "sle", "--purge"]))
    assert callable(captured["confirm"])

    # Purge + dry-run → no prompt
    cmd_disease(parser.parse_args(["disease", "backups", "sle", "--purge", "--dry-run"]))
    assert captured["dry_run"] is True
    assert captured["confirm"] is None

    # Missing module → error exit
    monkeypatch.setattr(
        scaf,
        "list_backups",
        lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("no module")),
    )
    assert cmd_disease(parser.parse_args(["disease", "backups", "sle"])) == 1


def test_cmd_disease_restore_wiring(monkeypatch):
    """--backup/--dry-run flow through to restore_disease."""
    import med_research.diseases.scaffold as scaf
    from med_research.cli import _build_parser, cmd_disease

    captured = {}

    def fake_restore(**kwargs):
        captured.update(kwargs)
        return {
            "disease_id": "sle",
            "backup": "/x/b.json",
            "backup_disease_id": "sle",
            "root": "/tmp",
            "dry_run": kwargs["dry_run"],
            "restored": {"genes": [], "drugs": []},
            "skipped": {"genes": [], "drugs": []},
            "updated_pathways": [],
            "counts": {},
            "files": [],
        }

    monkeypatch.setattr(scaf, "restore_disease", fake_restore)
    monkeypatch.setattr(scaf, "print_restore_summary", lambda s: None)
    parser = _build_parser()

    cmd_disease(parser.parse_args(["disease", "restore", "sle", "--backup", "x.json"]))
    assert captured["backup_path"] == "x.json"
    assert captured["dry_run"] is False

    # No --backup → default (None, resolved inside restore_disease)
    cmd_disease(parser.parse_args(["disease", "restore", "sle", "--dry-run"]))
    assert captured["backup_path"] is None
    assert captured["dry_run"] is True

    # Missing module → error exit
    monkeypatch.setattr(
        scaf,
        "restore_disease",
        lambda **kw: (_ for _ in ()).throw(FileNotFoundError("no module")),
    )
    assert cmd_disease(parser.parse_args(["disease", "restore", "no_such"])) == 1


def test_print_refresh_summary_prune_modes(caplog):
    """Lock in the ABORTED / dry-run / applied wording of the prune summary."""
    base = {
        "disease_id": "sle",
        "name": "SLE",
        "efo_id": None,
        "root": "/x",
        "dry_run": False,
        "sources": {},
        "files": [],
        "counts": {},
        "merge": {
            "genes": {"added": [], "updated": [], "kept": []},
            "drugs": {"added": [], "updated": [], "kept": []},
            "pathways": {"added": [], "updated": [], "kept": []},
        },
    }

    # Aborted by the confirmation prompt
    scaffold.print_refresh_summary(
        {
            **base,
            "prune": {
                "enabled": True,
                "aborted": True,
                "genes": ["ORPHAN"],
                "drugs": [],
                "scrubbed_pathways": [],
                "backup": None,
            },
        }
    )
    assert "ABORTED by user — no files written" in caplog.text
    assert "no entities removed" in caplog.text
    assert "Files (would be written)" in caplog.text

    # Dry-run preview
    caplog.clear()
    scaffold.print_refresh_summary(
        {
            **base,
            "dry_run": True,
            "prune": {
                "enabled": True,
                "aborted": False,
                "genes": ["ORPHAN"],
                "drugs": [],
                "scrubbed_pathways": [],
                "backup": None,
            },
        }
    )
    assert "DRY-RUN — no files written" in caplog.text
    assert "would remove 1 genes" in caplog.text

    # Applied prune with backup + pathway scrub
    caplog.clear()
    scaffold.print_refresh_summary(
        {
            **base,
            "prune": {
                "enabled": True,
                "aborted": False,
                "genes": ["ORPHAN"],
                "drugs": [],
                "scrubbed_pathways": ["jak-stat"],
                "backup": "/x/backups/pruned.json",
            },
        }
    )
    assert "files updated" in caplog.text
    assert "removed 1 genes" in caplog.text
    assert "1 pathways scrubbed" in caplog.text
    assert "Backup:" in caplog.text
    assert "Files written:" in caplog.text


def test_cmd_disease_list_and_validate(caplog):
    from med_research.cli import _build_parser, cmd_disease

    parser = _build_parser()
    assert cmd_disease(parser.parse_args(["disease", "list"])) == 0

    assert "sle" in caplog.text

    caplog.clear()
    assert cmd_disease(parser.parse_args(["disease", "validate", "sle"])) == 0
    assert "Validating" in caplog.text

    # unknown disease -> error exit
    assert cmd_disease(parser.parse_args(["disease", "validate", "no_such_disease"])) == 1


def test_cmd_disease_validate_all_and_strict(monkeypatch, caplog):
    """`validate --all` checks every module; --strict gates the exit code."""
    import med_research.diseases.base as base
    from med_research.cli import _build_parser, cmd_disease

    parser = _build_parser()

    # Pin discovery to a single healthy disease so the test is independent of
    # whatever modules happen to live in the repo's diseases/ tree.
    monkeypatch.setattr(
        base.Disease, "discover", staticmethod(lambda: {"sle": base.Disease("sle")})
    )

    # Healthy disease: --all passes, strict or not
    assert cmd_disease(parser.parse_args(["disease", "validate", "--all"])) == 0
    assert "[OK] All disease configs complete." in caplog.text
    assert cmd_disease(parser.parse_args(["disease", "validate", "sle", "--strict"])) == 0

    # Simulate a stub disease: gaps flip the exit code only under --strict
    def _gappy(self):
        return {
            "SYMPTOMS": "ok",
            "PUBMED_QUERIES": "ok",
            "CAR_T_SCORES": "empty",
            "DRUG_SAFETY_RISK": "empty",
        }

    monkeypatch.setattr(base.Disease, "validate", _gappy)
    assert cmd_disease(parser.parse_args(["disease", "validate", "sle"])) == 0
    assert cmd_disease(parser.parse_args(["disease", "validate", "sle", "--strict"])) == 1
    assert cmd_disease(parser.parse_args(["disease", "validate", "--all"])) == 0
    assert cmd_disease(parser.parse_args(["disease", "validate", "--all", "--strict"])) == 1

    # A disease whose config fails to load is reported, not fatal
    def _exploding(self):
        raise RuntimeError("syntax error in config.py")

    monkeypatch.setattr(base.Disease, "validate", _exploding)
    assert cmd_disease(parser.parse_args(["disease", "validate", "--all", "--strict"])) == 1
    assert "config load failed" in caplog.text


def test_cmd_disease_validate_requires_id_or_all():
    from med_research.cli import _build_parser, cmd_disease

    parser = _build_parser()
    assert cmd_disease(parser.parse_args(["disease", "validate"])) == 2


def test_warn_config_gaps_reports_and_quiets(monkeypatch, caplog):
    """Pipeline-startup gap check: loud on gaps, silent when complete."""
    import logging

    import med_research.cli as cli_mod
    import med_research.diseases.base as base

    real_validate = base.Disease.validate

    def _gappy(self):
        return {
            "SYMPTOMS": "ok",
            "PUBMED_QUERIES": "ok",
            "CAR_T_SCORES": "empty",
            "DRUG_SAFETY_RISK": "empty",
        }

    monkeypatch.setattr(base.Disease, "validate", _gappy)
    with caplog.at_level(logging.WARNING, logger="med_research.cli"):
        assert cli_mod._warn_config_gaps(base.Disease("sle")) is True
    messages = [r.message for r in caplog.records]
    assert any("not fully configured" in m for m in messages)
    assert any("CAR_T_SCORES" in m for m in messages)

    monkeypatch.setattr(base.Disease, "validate", real_validate)
    caplog.clear()
    assert cli_mod._warn_config_gaps(base.Disease("sle")) is False


def test_run_all_warns_on_config_gaps(monkeypatch):
    """run-all consults the gap check before executing any pipeline step."""
    import med_research.cli as cli_mod
    from med_research.cli import _build_parser, cmd_run_all

    captured = {"n": 0, "disease": None}

    def _fake_warn(disease):
        captured["n"] += 1
        captured["disease"] = disease.disease_id
        return True

    monkeypatch.setattr(cli_mod, "_warn_config_gaps", _fake_warn)
    monkeypatch.setattr(cli_mod, "PIPELINE_STEPS", [])
    parser = _build_parser()
    assert cmd_run_all(parser.parse_args(["run-all", "--disease", "sle"])) == 0
    assert captured["n"] == 1 and captured["disease"] == "sle"
