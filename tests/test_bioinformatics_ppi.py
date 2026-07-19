"""
Unit tests for the Lupus PPI Network module.

Tests cover:
  - get_gene_symbols(): gene filtering, symbol extraction
  - compute_hub_scores(): centrality calculations
  - cross_reference_with_candidates(): matching logic
  - Data loading functions
"""

import pytest
import networkx as nx


class TestGetGeneSymbols:
    """Tests for get_gene_symbols()."""

    @pytest.fixture
    def sample_genes(self):
        from bioinformatics.ppi import load_genes
        return load_genes()

    def test_excludes_drug_target_genes(self, sample_genes):
        from bioinformatics.ppi import get_gene_symbols

        symbols = get_gene_symbols(sample_genes)
        symbol_set = {s for _, s in symbols}
        excluded = {"CD20", "IMPDH", "Calcineurin", "Glucocorticoid Receptor"}
        for ex in excluded:
            assert ex not in symbol_set

    def test_returns_tuples(self, sample_genes):
        from bioinformatics.ppi import get_gene_symbols

        symbols = get_gene_symbols(sample_genes)
        assert isinstance(symbols, list)
        for item in symbols:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)  # gene_id
            assert isinstance(item[1], str)  # symbol

    def test_count(self, sample_genes):
        from bioinformatics.ppi import get_gene_symbols

        symbols = get_gene_symbols(sample_genes)
        # 22 total - 4 drug target genes = 18
        assert len(symbols) >= 18

    def test_has_expected_genes(self, sample_genes):
        from bioinformatics.ppi import get_gene_symbols

        symbols = get_gene_symbols(sample_genes)
        gene_ids = {gid for gid, _ in symbols}
        expected = {
            "HLA-DRB1", "IRF5", "STAT4", "BTK", "TYK2",
            "BLK", "TNFAIP3", "ITGAM", "BANK1", "PTPN22",
        }
        assert expected.issubset(gene_ids)


class TestComputeHubScores:
    """Tests for compute_hub_scores()."""

    def test_empty_graph(self):
        from bioinformatics.ppi import compute_hub_scores

        G = nx.Graph()
        scores = compute_hub_scores(G)
        assert scores == []

    def test_single_node(self):
        from bioinformatics.ppi import compute_hub_scores

        G = nx.Graph()
        G.add_node("BTK", symbol="BTK", gene_id="BTK", is_seed=True, is_lupus_gene=True)

        scores = compute_hub_scores(G)
        assert len(scores) == 1
        assert scores[0]["symbol"] == "BTK"
        assert scores[0]["is_lupus_gene"] is True
        assert scores[0]["degree"] == 0
        # Single isolated node: degree_centrality=0, betweenness_centrality=1
        # hub_score = (0 + 1) / 2 = 0.5
        assert scores[0]["hub_score"] == 0.5

    def test_star_graph(self):
        from bioinformatics.ppi import compute_hub_scores

        G = nx.Graph()
        G.add_node("hub", symbol="HUB", gene_id="HUB", is_seed=True, is_lupus_gene=True)
        for i in range(5):
            name = f"spoke{i}"
            G.add_node(name, symbol=name, gene_id=None, is_seed=False, is_lupus_gene=False)
            G.add_edge("hub", name, score=0.9, weight=0.9)

        scores = compute_hub_scores(G)
        assert len(scores) == 6

        # Hub should be top
        hub = scores[0]
        assert hub["symbol"] == "HUB"
        assert hub["degree"] == 5
        assert hub["hub_score"] > 0

        # Hub should have highest hub score
        for s in scores[1:]:
            assert hub["hub_score"] >= s["hub_score"]

    def test_hub_scores_sorted_descending(self):
        from bioinformatics.ppi import compute_hub_scores

        G = nx.Graph()
        G.add_node("A", symbol="A", gene_id="A", is_seed=True, is_lupus_gene=True)
        G.add_node("B", symbol="B", gene_id="B", is_seed=True, is_lupus_gene=True)
        G.add_node("C", symbol="C", gene_id=None, is_seed=False, is_lupus_gene=False)
        G.add_edge("A", "B", score=0.8, weight=0.8)
        G.add_edge("A", "C", score=0.7, weight=0.7)

        scores = compute_hub_scores(G)
        for i in range(len(scores) - 1):
            assert scores[i]["hub_score"] >= scores[i + 1]["hub_score"]

    def test_result_structure(self):
        from bioinformatics.ppi import compute_hub_scores

        G = nx.Graph()
        G.add_node("A", symbol="A", gene_id="A", is_seed=True, is_lupus_gene=True)

        scores = compute_hub_scores(G)
        for s in scores:
            for key in [
                "node_id", "symbol", "is_seed", "is_lupus_gene",
                "degree", "degree_centrality", "betweenness_centrality", "hub_score",
            ]:
                assert key in s, f"Missing key: {key}"

    def test_disconnected_nodes(self):
        from bioinformatics.ppi import compute_hub_scores

        G = nx.Graph()
        for name in ["A", "B", "C"]:
            G.add_node(name, symbol=name, gene_id=name, is_seed=True, is_lupus_gene=True)

        scores = compute_hub_scores(G)
        assert len(scores) == 3
        # All disconnected, all should have hub_score 0
        for s in scores:
            assert s["hub_score"] == 0.0
            assert s["degree"] == 0


class TestCrossReferenceWithCandidates:
    """Tests for cross_reference_with_candidates()."""

    @pytest.fixture
    def sample_ppi_graph(self):
        G = nx.Graph()
        G.add_node("BTK", symbol="BTK", gene_id="BTK", is_seed=True, is_lupus_gene=True)
        G.add_node("NOVEL", symbol="NOVEL", gene_id="NOVEL", is_seed=True, is_lupus_gene=True)
        G.add_node("PARTNER", symbol="PARTNER", gene_id=None, is_seed=False, is_lupus_gene=False)
        G.add_edge("BTK", "PARTNER", score=0.9, weight=0.9)
        return G

    @pytest.fixture
    def sample_hub_scores(self):
        return [
            {
                "node_id": "BTK",
                "symbol": "BTK",
                "gene_id": "BTK",
                "is_seed": True,
                "is_lupus_gene": True,
                "degree": 1,
                "degree_centrality": 0.5,
                "betweenness_centrality": 0.0,
                "hub_score": 0.25,
            },
            {
                "node_id": "PARTNER",
                "symbol": "PARTNER",
                "gene_id": None,
                "is_seed": False,
                "is_lupus_gene": False,
                "degree": 1,
                "degree_centrality": 0.5,
                "betweenness_centrality": 0.0,
                "hub_score": 0.25,
            },
            {
                "node_id": "NOVEL",
                "symbol": "NOVEL",
                "gene_id": "NOVEL",
                "is_seed": True,
                "is_lupus_gene": True,
                "degree": 0,
                "degree_centrality": 0.0,
                "betweenness_centrality": 0.0,
                "hub_score": 0.0,
            },
        ]

    @pytest.fixture
    def sample_kg_genes(self):
        from bioinformatics.ppi import load_genes
        return load_genes()

    @pytest.fixture
    def sample_candidates(self):
        return [
            {
                "id": "c001",
                "gene_id": "BTK",
                "drug_name": "Fenebrutinib (GDC-0853)",
                "drug_category": "BTK Inhibitor",
                "target_similarity_score": 10,
                "pathway_proximity_score": 10,
                "mechanistic_rationale_score": 10,
                "clinical_evidence_score": 9,
                "safety_score": 7,
                "novelty_score": 2,
                "composite_score": 9.25,
                "evidence_level": "Phase 2",
                "status": "Investigational",
                "mechanism": "BTK inhibitor",
                "rationale": "BTK inhibition for SLE",
            },
            {
                "id": "c002",
                "gene_id": "BTK",
                "drug_name": "Ibrutinib (Imbruvica)",
                "drug_category": "BTK Inhibitor",
                "target_similarity_score": 10,
                "pathway_proximity_score": 10,
                "mechanistic_rationale_score": 9,
                "clinical_evidence_score": 3,
                "safety_score": 5,
                "novelty_score": 3,
                "composite_score": 7.55,
                "evidence_level": "Preclinical",
                "status": "Approved (other)",
                "mechanism": "Covalent BTK inhibitor",
                "rationale": "BTK for SLE",
            },
        ]

    def test_matches_btk_to_candidates(
        self, sample_hub_scores, sample_ppi_graph, sample_kg_genes, sample_candidates
    ):
        from bioinformatics.ppi import cross_reference_with_candidates

        crossref = cross_reference_with_candidates(
            sample_hub_scores, sample_ppi_graph, sample_kg_genes, sample_candidates
        )

        matches = crossref["hub_candidate_matches"]
        assert len(matches) >= 1
        btk_match = next((m for m in matches if m["gene_id"] == "BTK"), None)
        assert btk_match is not None
        assert btk_match["n_candidates"] == 2

    def test_novel_is_untargeted(
        self, sample_hub_scores, sample_ppi_graph, sample_kg_genes, sample_candidates
    ):
        from bioinformatics.ppi import cross_reference_with_candidates

        crossref = cross_reference_with_candidates(
            sample_hub_scores, sample_ppi_graph, sample_kg_genes, sample_candidates
        )

        untargeted = crossref["hub_untargeted"]
        untargeted_ids = {u["gene_id"] for u in untargeted}
        assert "NOVEL" in untargeted_ids

    def test_returns_expected_keys(
        self, sample_hub_scores, sample_ppi_graph, sample_kg_genes, sample_candidates
    ):
        from bioinformatics.ppi import cross_reference_with_candidates

        crossref = cross_reference_with_candidates(
            sample_hub_scores, sample_ppi_graph, sample_kg_genes, sample_candidates
        )

        for key in [
            "lupus_hubs", "non_lupus_hubs", "hub_candidate_matches",
            "hub_untargeted", "top_hubs_overall",
        ]:
            assert key in crossref, f"Missing key: {key}"

    def test_separates_lupus_from_nonlupus(
        self, sample_hub_scores, sample_ppi_graph, sample_kg_genes, sample_candidates
    ):
        from bioinformatics.ppi import cross_reference_with_candidates

        crossref = cross_reference_with_candidates(
            sample_hub_scores, sample_ppi_graph, sample_kg_genes, sample_candidates
        )

        lupus = crossref["lupus_hubs"]
        non_lupus = crossref["non_lupus_hubs"]

        lupus_ids = {h["symbol"] for h in lupus}
        non_lupus_ids = {h["symbol"] for h in non_lupus}

        assert "BTK" in lupus_ids
        assert "NOVEL" in lupus_ids
        assert "PARTNER" in non_lupus_ids
        assert lupus_ids.isdisjoint(non_lupus_ids)


class TestLoadFunctions:
    """Tests for PPI data loading."""

    def test_load_genes(self):
        from bioinformatics.ppi import load_genes

        genes = load_genes()
        assert isinstance(genes, dict)
        assert len(genes) >= 20
