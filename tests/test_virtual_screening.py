"""
Unit tests for the Lupus Virtual Drug Screening Engine.

Tests cover:
  - screening.py: compound library building, property scoring,
    binding estimation, target complementarity, composite scoring,
    untargeted gene detection
"""


import pytest

# ── Sample fixture data ──────────────────────────────────────────────

@pytest.fixture
def sample_compound():
    """A typical small-molecule drug compound."""
    return {
        "id": "baricitinib",
        "name": "Baricitinib (Olumiant)",
        "type": "Small Molecule",
        "target": "JAK1/JAK2",
        "mechanism": "JAK1/2 inhibitor blocking type I IFN and IL-6 signaling",
        "category": "Targeted Synthetic - JAK Inhibitor",
        "mw": 371,
        "logp": 1.7,
        "hbd": 2,
        "hba": 7,
        "rotb": 5,
        "tpsa": 112,
    }


@pytest.fixture
def sample_biologic():
    """A monoclonal antibody compound."""
    return {
        "id": "rituximab",
        "name": "Rituximab (Rituxan)",
        "type": "Monoclonal Antibody",
        "target": "CD20",
        "mechanism": "Depletes CD20+ B cells via ADCC",
        "category": "Biologic - B Cell Depletion",
        "mw": 145000,
        "logp": -10.5,
        "hbd": 115,
        "hba": 145,
        "rotb": 198,
        "tpsa": 4800,
    }


@pytest.fixture
def sample_gene_info():
    """Gene info dict matching KG structure."""
    return {
        "id": "BTK",
        "name": "Bruton Tyrosine Kinase",
        "category": "B Cell Signaling",
        "function": "Essential kinase for B cell receptor and Fc receptor signaling",
    }


@pytest.fixture
def sample_library():
    """A small compound library for screening tests."""
    return [
        {
            "id": "baricitinib",
            "name": "Baricitinib (Olumiant)",
            "type": "Small Molecule",
            "target": "JAK1/JAK2",
            "mechanism": "JAK1/2 inhibitor blocking type I IFN and IL-6 signaling",
            "category": "Targeted Synthetic - JAK Inhibitor",
            "mw": 371, "logp": 1.7, "hbd": 2, "hba": 7, "rotb": 5, "tpsa": 112,
        },
        {
            "id": "hydroxychloroquine",
            "name": "Hydroxychloroquine (Plaquenil)",
            "type": "Small Molecule",
            "target": "TLR7/TLR9 endosomal signaling",
            "mechanism": "Inhibits endosomal acidification, blocking TLR7/9 activation",
            "category": "Immunomodulator - Antimalarial",
            "mw": 336, "logp": 3.6, "hbd": 1, "hba": 3, "rotb": 8, "tpsa": 45,
        },
        {
            "id": "belimumab",
            "name": "Belimumab (Benlysta)",
            "type": "Monoclonal Antibody",
            "target": "BAFF (BLyS)",
            "mechanism": "Binds and neutralizes soluble BAFF",
            "category": "Biologic - B Cell Modulation",
            "mw": 147000, "logp": -10.0, "hbd": 120, "hba": 150, "rotb": 200, "tpsa": 5000,
        },
    ]


# ═══════════════════════════════════════════════════════════════════════
#  scoring tests
# ═══════════════════════════════════════════════════════════════════════

class TestDruglikeness:
    """Tests for compute_druglikeness()."""

    def test_perfect_small_molecule(self, sample_compound):
        from med_research.pipeline.virtual_screening.screening import compute_druglikeness
        score = compute_druglikeness(sample_compound)
        # baricitinib: MW 371, LogP 1.7, HBD 2, HBA 7 — all within Lipinski
        assert score == 10.0

    def test_biologic_gets_neutral_score(self, sample_biologic):
        from med_research.pipeline.virtual_screening.screening import compute_druglikeness
        score = compute_druglikeness(sample_biologic)
        # Biologics (MW > 50000) get neutral 5.0
        assert score == 5.0

    def test_high_mw_penalty(self):
        from med_research.pipeline.virtual_screening.screening import compute_druglikeness
        compound = {
            "mw": 800,
            "logp": 2.0,
            "hbd": 2,
            "hba": 5,
        }
        score = compute_druglikeness(compound)
        # MW 500-1000 gets 0.5 violation = -1.25 from 10 = 8.75
        assert score == 8.8

    def test_multiple_violations(self):
        from med_research.pipeline.virtual_screening.screening import compute_druglikeness
        compound = {
            "mw": 550,
            "logp": 6.0,
            "hbd": 6,
            "hba": 12,
        }
        score = compute_druglikeness(compound)
        # MW 500-1000: +0.5, LogP > 5: +1, HBD > 5: +1, HBA > 10: +1
        # Total violations = 3.5 → 10 - 3.5*2.5 = 1.25
        assert score == 1.2

    def test_returns_float(self, sample_compound):
        from med_research.pipeline.virtual_screening.screening import compute_druglikeness
        score = compute_druglikeness(sample_compound)
        assert isinstance(score, float)

    def test_score_bounded_zero_to_ten(self):
        from med_research.pipeline.virtual_screening.screening import compute_druglikeness
        # Extreme worst case
        compound = {"mw": 900, "logp": 10.0, "hbd": 10, "hba": 20}
        score = compute_druglikeness(compound)
        assert 0.0 <= score <= 10.0


class TestTargetComplementarity:
    """Tests for compute_target_complementarity()."""

    def test_btk_inhibitor_matches_b_cell_signaling(self, sample_compound, sample_gene_info):
        from med_research.pipeline.virtual_screening.screening import compute_target_complementarity
        score = compute_target_complementarity(sample_compound, sample_gene_info)
        # BTK is B Cell Signaling; baricitinib mentions "JAK" but not B cell keywords
        # Should get baseline + some function overlap
        assert score >= 2.0
        assert score <= 10.0

    def test_direct_target_match(self):
        from med_research.pipeline.virtual_screening.screening import compute_target_complementarity
        compound = {
            "mechanism": "BTK inhibitor blocking B cell receptor signaling",
            "target": "BTK",
            "category": "Targeted Synthetic - BTK Inhibitor",
        }
        gene = {
            "id": "BTK",
            "name": "Bruton Tyrosine Kinase",
            "category": "B Cell Signaling",
            "function": "Kinase involved in BCR signaling",
        }
        score = compute_target_complementarity(compound, gene)
        # Should find "b cell" and "btk" keywords in B Cell Signaling category
        assert score >= 4.0

    def test_no_category_match(self):
        from med_research.pipeline.virtual_screening.screening import compute_target_complementarity
        compound = {
            "mechanism": "Unknown mechanism of action",
            "target": "Unknown",
            "category": "Unknown",
        }
        gene = {
            "id": "IRF5",
            "name": "Interferon Regulatory Factor 5",
            "category": "Type I Interferon Pathway",
            "function": "Transcription factor driving type I IFN",
        }
        score = compute_target_complementarity(compound, gene)
        # Should still get baseline score
        assert score >= 2.0

    def test_returns_float(self, sample_compound, sample_gene_info):
        from med_research.pipeline.virtual_screening.screening import compute_target_complementarity
        score = compute_target_complementarity(sample_compound, sample_gene_info)
        assert isinstance(score, float)


class TestBindingEstimate:
    """Tests for compute_binding_estimate()."""

    def test_ideal_small_molecule(self, sample_compound):
        from med_research.pipeline.virtual_screening.screening import compute_binding_estimate
        score = compute_binding_estimate(sample_compound, {})
        # baricitinib: MW 371 (200-600 ✓), LogP 1.7 (1-4 ✓), HBD 2/HBA 7 (balanced ✓), TPSA 112 (<140 ✓)
        # 5 + 2 + 1.5 + 1.5 + 1 = 11 → capped at 10
        assert score == 10.0

    def test_biologic_penalty(self, sample_biologic):
        from med_research.pipeline.virtual_screening.screening import compute_binding_estimate
        score = compute_binding_estimate(sample_biologic, {})
        # Biologics (MW > 50000) get a flat 3.0
        assert score == 3.0

    def test_poor_molecule(self):
        from med_research.pipeline.virtual_screening.screening import compute_binding_estimate
        compound = {
            "mw": 1200,
            "logp": -2.0,
            "hbd": 10,
            "hba": 15,
            "tpsa": 300,
        }
        score = compute_binding_estimate(compound, {})
        # MW > 800: -1, LogP out of range: 0, HBD/HBA unbalanced: 0, TPSA > 140: 0
        # 5 - 1 = 4
        assert score <= 5.0

    def test_returns_float(self, sample_compound):
        from med_research.pipeline.virtual_screening.screening import compute_binding_estimate
        score = compute_binding_estimate(sample_compound, {})
        assert isinstance(score, float)


class TestCompositeScore:
    """Tests for compute_composite_score()."""

    def test_balanced_scores(self):
        from med_research.pipeline.virtual_screening.screening import compute_composite_score
        scores = {
            "binding_estimate": 8.0,
            "druglikeness": 7.0,
            "target_complementarity": 6.0,
            "similarity_score": 5.0,
            "novelty_score": 4.0,
        }
        result = compute_composite_score(scores)
        # 8*0.30 + 7*0.20 + 6*0.25 + 5*0.15 + 4*0.10
        # = 2.4 + 1.4 + 1.5 + 0.75 + 0.4 = 6.45
        assert result == 6.45

    def test_maximum_score(self):
        from med_research.pipeline.virtual_screening.screening import compute_composite_score
        scores = {
            "binding_estimate": 10.0,
            "druglikeness": 10.0,
            "target_complementarity": 10.0,
            "similarity_score": 10.0,
            "novelty_score": 10.0,
        }
        result = compute_composite_score(scores)
        assert result == 10.0

    def test_minimum_score(self):
        from med_research.pipeline.virtual_screening.screening import compute_composite_score
        scores = {
            "binding_estimate": 0.0,
            "druglikeness": 0.0,
            "target_complementarity": 0.0,
            "similarity_score": 0.0,
            "novelty_score": 0.0,
        }
        result = compute_composite_score(scores)
        assert result == 0.0

    def test_returns_float(self):
        from med_research.pipeline.virtual_screening.screening import compute_composite_score
        scores = {
            "binding_estimate": 5.0,
            "druglikeness": 5.0,
            "target_complementarity": 5.0,
            "similarity_score": 5.0,
            "novelty_score": 5.0,
        }
        result = compute_composite_score(scores)
        assert isinstance(result, float)


# ═══════════════════════════════════════════════════════════════════════
#  compound library tests
# ═══════════════════════════════════════════════════════════════════════

class TestBuildCompoundLibrary:
    """Tests for build_compound_library()."""

    def test_returns_list_of_dicts(self):
        from med_research.pipeline.virtual_screening.screening import build_compound_library
        library = build_compound_library()
        assert isinstance(library, list)
        assert len(library) >= 15
        for compound in library:
            assert isinstance(compound, dict)
            assert "id" in compound
            assert "name" in compound
            assert "mw" in compound
            assert "logp" in compound

    def test_each_compound_has_required_fields(self):
        from med_research.pipeline.virtual_screening.screening import build_compound_library
        library = build_compound_library()
        required = {"id", "name", "type", "target", "mechanism", "category",
                     "mw", "logp", "hbd", "hba", "rotb", "tpsa"}
        for compound in library:
            missing = required - set(compound.keys())
            assert not missing, f"Missing fields in {compound['id']}: {missing}"

    def test_known_drug_included(self):
        from med_research.pipeline.virtual_screening.screening import build_compound_library
        library = build_compound_library()
        ids = {c["id"] for c in library}
        assert "baricitinib" in ids
        assert "hydroxychloroquine" in ids
        assert "belimumab" in ids


# ═══════════════════════════════════════════════════════════════════════
#  screening pipeline tests
# ═══════════════════════════════════════════════════════════════════════

class TestScreenCompounds:
    """Integration tests for screen_compounds()."""

    def test_returns_complete_structure(self, sample_library):
        from med_research.pipeline.virtual_screening.screening import screen_compounds
        results = screen_compounds(
            target_genes=["BTK"],
            compound_library=sample_library,
            top_n=5,
        )
        assert "results_per_target" in results
        assert "all_results" in results
        assert "stats" in results
        assert "compound_library" in results

    def test_target_results_have_top_compounds(self, sample_library):
        from med_research.pipeline.virtual_screening.screening import screen_compounds
        results = screen_compounds(
            target_genes=["BTK"],
            compound_library=sample_library,
            top_n=3,
        )
        target_data = results["results_per_target"]["BTK"]
        assert len(target_data["top_compounds"]) <= 3
        assert len(target_data["top_compounds"]) >= 1

    def test_results_sorted_descending(self, sample_library):
        from med_research.pipeline.virtual_screening.screening import screen_compounds
        results = screen_compounds(
            target_genes=["BTK"],
            compound_library=sample_library,
            top_n=10,
        )
        top = results["results_per_target"]["BTK"]["top_compounds"]
        for i in range(len(top) - 1):
            assert top[i]["composite_score"] >= top[i + 1]["composite_score"]

    def test_each_result_has_tier(self, sample_library):
        from med_research.pipeline.virtual_screening.screening import screen_compounds
        results = screen_compounds(
            target_genes=["BTK"],
            compound_library=sample_library,
        )
        for c in results["all_results"]:
            assert "tier" in c
            assert c["tier"] in [
                "🔴 Tier 1 — Strong Candidate",
                "🟠 Tier 2 — Promising",
                "🟡 Tier 3 — Possible",
                "🟢 Tier 4 — Low Priority",
            ]

    def test_stats_are_accurate(self, sample_library):
        from med_research.pipeline.virtual_screening.screening import screen_compounds
        results = screen_compounds(
            target_genes=["BTK", "STAT4"],
            compound_library=sample_library,
        )
        stats = results["stats"]
        assert stats["targets_screened"] == 2
        assert stats["compounds_screened"] == len(sample_library)
        assert stats["total_pairings"] == len(sample_library) * 2

    def test_single_gene_filtering(self, sample_library):
        from med_research.pipeline.virtual_screening.screening import screen_compounds
        results = screen_compounds(
            target_genes=["STAT4"],
            compound_library=sample_library,
        )
        assert "STAT4" in results["results_per_target"]
        assert "BTK" not in results["results_per_target"]

    def test_composite_score_bounds(self, sample_library):
        from med_research.pipeline.virtual_screening.screening import screen_compounds
        results = screen_compounds(
            target_genes=["BTK"],
            compound_library=sample_library,
        )
        for c in results["all_results"]:
            assert 0.0 <= c["composite_score"] <= 10.0


# ═══════════════════════════════════════════════════════════════════════
#  utility tests
# ═══════════════════════════════════════════════════════════════════════

class TestNoveltyScore:
    """Tests for compute_novelty_score()."""

    def test_approved_sle_drug_low_novelty(self):
        from med_research.pipeline.virtual_screening.screening import compute_novelty_score
        compound = {"category": "Biologic - approved for SLE"}
        score = compute_novelty_score(compound, {})
        assert score <= 4.0

    def test_investigational_high_novelty(self):
        from med_research.pipeline.virtual_screening.screening import compute_novelty_score
        compound = {"category": "Investigational - Phase 2"}
        score = compute_novelty_score(compound, {})
        assert score >= 7.0

    def test_default_novelty(self):
        from med_research.pipeline.virtual_screening.screening import compute_novelty_score
        compound = {"category": "Unknown Category"}
        score = compute_novelty_score(compound, {})
        assert score == 5.0


class TestSimilarityScore:
    """Tests for compute_similarity_score()."""

    def test_known_candidate_returns_high_score(self, sample_gene_info):
        from med_research.pipeline.virtual_screening.screening import compute_similarity_score
        # Ibrutinib is a known BTK repurposing candidate
        compound = {
            "name": "Ibrutinib (Imbruvica)",
            "category": "Targeted Synthetic - BTK Inhibitor",
        }
        score = compute_similarity_score(compound, sample_gene_info)
        # Should match against drug_repurposing/data/candidates.json (c001 targets BTK)
        assert score >= 7.0

    def test_unrelated_compound_returns_neutral(self, sample_gene_info):
        from med_research.pipeline.virtual_screening.screening import compute_similarity_score
        compound = {
            "name": "Completely Unknown Drug",
            "category": "Unknown",
        }
        score = compute_similarity_score(compound, sample_gene_info)
        # Should get neutral 3.0 since no match
        assert score == 3.0

    def test_category_overlap_returns_moderate(self, sample_gene_info):
        from med_research.pipeline.virtual_screening.screening import compute_similarity_score
        # Acetinib is a BTK inhibitor (same category as BTK candidates)
        compound = {
            "name": "Acalabrutinib (Calquence)",
            "category": "Targeted Synthetic - BTK Inhibitor",
        }
        score = compute_similarity_score(compound, sample_gene_info)
        # Category overlap with BTK candidates should give moderate score
        assert score >= 4.0

    def test_returns_float(self, sample_gene_info):
        from med_research.pipeline.virtual_screening.screening import compute_similarity_score
        compound = {"name": "Test Drug", "category": "Test"}
        score = compute_similarity_score(compound, sample_gene_info)
        assert isinstance(score, float)


class TestVinaStatus:
    """Tests for get_vina_status()."""

    def test_returns_string(self):
        from med_research.pipeline.virtual_screening.screening import get_vina_status
        status = get_vina_status()
        assert isinstance(status, str)
        assert "available" in status.lower() or "not available" in status.lower()


# ═══════════════════════════════════════════════════════════════════════
#  disease_id threading tests
# ═══════════════════════════════════════════════════════════════════════

class TestDiseaseThreading:
    """Tests that disease_id flows through data loading and screening."""

    def test_load_kg_genes_threads_disease(self, monkeypatch):
        import med_research.pipeline.virtual_screening.screening as screening

        captured = {}

        def fake_config_load_genes(disease_id="sle"):
            captured["disease_id"] = disease_id
            return {"genes": [{"id": "BTK", "name": "Bruton"}]}

        monkeypatch.setattr(screening, "config_load_genes", fake_config_load_genes)
        genes = screening.load_kg_genes("ra")
        assert captured["disease_id"] == "ra"
        assert "BTK" in genes

    def test_load_kg_drugs_threads_disease(self, monkeypatch):
        import med_research.pipeline.virtual_screening.screening as screening

        captured = {}

        def fake_config_load_drugs(disease_id="sle"):
            captured["disease_id"] = disease_id
            return {"drugs": [{"id": "baricitinib", "name": "Baricitinib"}]}

        monkeypatch.setattr(screening, "config_load_drugs", fake_config_load_drugs)
        drugs = screening.load_kg_drugs("ms")
        assert captured["disease_id"] == "ms"
        assert "baricitinib" in drugs

    def test_build_compound_library_threads_disease(self, monkeypatch):
        import med_research.pipeline.virtual_screening.screening as screening

        captured = {}

        def fake_load_kg_drugs(disease_id="sle"):
            captured["disease_id"] = disease_id
            return {
                "baricitinib": {"id": "baricitinib", "name": "Baricitinib",
                                "type": "Small Molecule", "target": "JAK1",
                                "mechanism": "JAK1/2 inhibitor", "category": "JAK Inhibitor"},
            }

        monkeypatch.setattr(screening, "load_kg_drugs", fake_load_kg_drugs)
        library = screening.build_compound_library("ibd")
        assert captured["disease_id"] == "ibd"
        assert library[0]["id"] == "baricitinib"

    def test_get_untargeted_genes_threads_disease(self, monkeypatch):
        import med_research.pipeline.virtual_screening.screening as screening

        captured = {}

        def fake_build_graph(disease_id="sle"):
            captured["graph_disease"] = disease_id
            import networkx as nx
            G = nx.MultiDiGraph()
            G.add_node("d1", type="disease")
            G.add_node("BTK", type="gene")
            G.add_edge("d1", "BTK", type="TARGETS")
            return G

        def fake_load_kg_genes(disease_id="sle"):
            captured["genes_disease"] = disease_id
            return {
                "BTK": {"id": "BTK", "name": "Bruton"},
                "TYK2": {"id": "TYK2", "name": "TYK2"},
            }

        # build_graph is imported lazily inside get_untargeted_genes,
        # so patch it at its source module.
        import med_research.pipeline.knowledge_graph.builder as kg_builder
        monkeypatch.setattr(kg_builder, "build_graph", fake_build_graph)
        monkeypatch.setattr(screening, "load_kg_genes", fake_load_kg_genes)
        untargeted = screening.get_untargeted_genes("ssc")
        assert captured["graph_disease"] == "ssc"
        assert captured["genes_disease"] == "ssc"
        ids = {g["id"] for g in untargeted}
        assert "BTK" not in ids  # BTK has a TARGETS edge in the fake graph
        assert "TYK2" in ids

    def test_sle_drug_target_filter_only_applies_to_sle(self, monkeypatch):
        """The curated drug-target exclusion (CD20, IMPDH, ...) is SLE-only."""
        import networkx as nx

        import med_research.pipeline.knowledge_graph.builder as kg_builder
        import med_research.pipeline.virtual_screening.screening as screening

        def fake_build_graph(disease_id="sle"):
            G = nx.MultiDiGraph()
            G.add_node("d1", type="disease")
            for gid in ("CD20", "TYK2", "STAT4"):
                G.add_node(gid, type="gene")
            return G

        def fake_load_kg_genes(disease_id="sle"):
            return {
                g: {"id": g, "name": g, "category": "", "function": ""}
                for g in ("CD20", "TYK2", "STAT4")
            }

        monkeypatch.setattr(kg_builder, "build_graph", fake_build_graph)
        monkeypatch.setattr(screening, "load_kg_genes", fake_load_kg_genes)

        sle_ids = {g["id"] for g in screening.get_untargeted_genes("sle")}
        assert "CD20" not in sle_ids  # SLE excludes its curated drug targets
        assert "TYK2" in sle_ids

        ra_ids = {g["id"] for g in screening.get_untargeted_genes("ra")}
        assert "CD20" in ra_ids  # other diseases may legitimately target CD20

    def test_screen_compounds_threads_disease(self, monkeypatch):
        import med_research.pipeline.virtual_screening.screening as screening

        captured = {}

        def fake_build_compound_library(disease_id="sle"):
            captured["library_disease"] = disease_id
            return [
                {"id": "baricitinib", "name": "Baricitinib", "type": "Small Molecule",
                 "target": "JAK1", "mechanism": "JAK1/2 inhibitor",
                 "category": "JAK Inhibitor", "mw": 371, "logp": 1.7,
                 "hbd": 2, "hba": 7, "rotb": 5, "tpsa": 112},
            ]

        def fake_get_untargeted_genes(disease_id="sle"):
            captured["untargeted_disease"] = disease_id
            return [{"id": "TYK2", "name": "TYK2"}]

        def fake_load_kg_genes(disease_id="sle"):
            captured["genes_disease"] = disease_id
            return {"TYK2": {"id": "TYK2", "name": "TYK2", "category": "JAK-STAT", "function": "kinase"}}

        monkeypatch.setattr(screening, "build_compound_library", fake_build_compound_library)
        monkeypatch.setattr(screening, "get_untargeted_genes", fake_get_untargeted_genes)
        monkeypatch.setattr(screening, "load_kg_genes", fake_load_kg_genes)

        results = screening.screen_compounds(disease_id="ra", top_n=5)
        assert captured["library_disease"] == "ra"
        assert captured["untargeted_disease"] == "ra"
        assert captured["genes_disease"] == "ra"
        assert "TYK2" in results["target_genes"]
        assert results["stats"]["targets_screened"] == 1
