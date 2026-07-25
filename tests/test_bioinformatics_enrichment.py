"""
Unit tests for the Lupus Pathway Enrichment module.

Tests cover:
  - get_lupus_gene_list(): gene filtering, exclusions
  - cross_reference_with_kg_pathways(): matching logic
  - Data loading functions
"""


import pytest


class TestGetLupusGeneList:
    """Tests for get_lupus_gene_list()."""

    @pytest.fixture
    def sample_kg_genes(self):
        from bioinformatics.enrichment import load_kg_genes
        return load_kg_genes()

    def test_excludes_drug_target_genes(self, sample_kg_genes):
        from bioinformatics.enrichment import get_lupus_gene_list

        gene_list = get_lupus_gene_list(sample_kg_genes, G=None, untargeted_only=False)
        symbols = {g["gene_id"] for g in gene_list}
        excluded = {"CD20", "IMPDH", "Calcineurin", "Glucocorticoid Receptor"}
        assert symbols.isdisjoint(excluded)

    def test_includes_lupus_risk_genes(self, sample_kg_genes):
        from bioinformatics.enrichment import get_lupus_gene_list

        gene_list = get_lupus_gene_list(sample_kg_genes, G=None, untargeted_only=False)
        symbols = {g["gene_id"] for g in gene_list}
        expected = {
            "HLA-DRB1", "IRF5", "STAT4", "BLK", "TNFAIP3",
            "ITGAM", "BANK1", "PTPN22", "TNFSF4", "FCGR2A",
            "FCGR3A", "TLR7", "TLR9", "BAFF", "IFNAR1",
            "JAK1", "TYK2", "BTK",
        }
        assert expected.issubset(symbols)

    def test_returns_list_of_dicts(self, sample_kg_genes):
        from bioinformatics.enrichment import get_lupus_gene_list

        gene_list = get_lupus_gene_list(sample_kg_genes, G=None, untargeted_only=False)
        assert isinstance(gene_list, list)
        for g in gene_list:
            assert "gene_id" in g
            assert "symbol" in g
            assert "category" in g

    def test_untargeted_only_mode(self, sample_kg_genes, sample_graph):
        from bioinformatics.enrichment import get_lupus_gene_list

        untargeted = get_lupus_gene_list(sample_kg_genes, G=sample_graph, untargeted_only=True)
        all_genes = get_lupus_gene_list(sample_kg_genes, G=sample_graph, untargeted_only=False)

        # Untargeted should be a subset of all
        untargeted_ids = {g["gene_id"] for g in untargeted}
        all_ids = {g["gene_id"] for g in all_genes}
        assert untargeted_ids.issubset(all_ids)
        assert len(untargeted_ids) < len(all_ids)

    def test_untargeted_excludes_targeted(self, sample_kg_genes, sample_graph):
        from bioinformatics.enrichment import get_lupus_gene_list

        untargeted = get_lupus_gene_list(sample_kg_genes, G=sample_graph, untargeted_only=True)
        ids = {g["gene_id"] for g in untargeted}
        # These genes have TARGETS edges in the KG
        targeted = {"BAFF", "IFNAR1", "TLR7", "TLR9", "JAK1"}
        assert ids.isdisjoint(targeted)

    def test_has_correct_count(self, sample_kg_genes):
        from bioinformatics.enrichment import get_lupus_gene_list

        gene_list = get_lupus_gene_list(sample_kg_genes, G=None, untargeted_only=False)
        # 22 total - 4 drug target genes = 18 lupus genes
        assert len(gene_list) >= 18

    def test_symbols_are_clean(self, sample_kg_genes):
        from bioinformatics.enrichment import get_lupus_gene_list

        gene_list = get_lupus_gene_list(sample_kg_genes, G=None, untargeted_only=False)
        for g in gene_list:
            symbol = g["symbol"]
            # Should not contain parentheses (stripped brand/detail parts)
            assert "(" not in symbol


class TestCrossReferenceWithKG:
    """Tests for cross_reference_with_kg_pathways()."""

    @pytest.fixture
    def sample_enrichment(self):
        return {
            "GO_Biological_Process_2023": {
                "library": "GO_Biological_Process_2023",
                "terms": [
                    {
                        "term": "type I interferon signaling pathway",
                        "adj_p_value": 1e-6,
                        "genes": ["IRF5", "TLR7", "IFNAR1"],
                        "odds_ratio": 15.0,
                        "overlap": "3/50",
                        "p_value": 1e-8,
                        "combined_score": 100.0,
                    },
                    {
                        "term": "B cell receptor signaling pathway",
                        "adj_p_value": 0.001,
                        "genes": ["BTK", "BLK", "BANK1"],
                        "odds_ratio": 8.0,
                        "overlap": "3/80",
                        "p_value": 0.001,
                        "combined_score": 50.0,
                    },
                    {
                        "term": "nucleotide metabolism",
                        "adj_p_value": 0.5,
                        "genes": ["IMPDH"],
                        "odds_ratio": 2.0,
                        "overlap": "1/10",
                        "p_value": 0.6,
                        "combined_score": 1.0,
                    },
                ],
                "total_significant": 3,
            },
        }

    @pytest.fixture
    def sample_kg_pathways(self):
        return {
            "pathways": [
                {
                    "id": "type1-ifn",
                    "name": "Type I Interferon Pathway",
                    "description": "Central pathogenic pathway in SLE.",
                },
                {
                    "id": "bcell-signaling",
                    "name": "B Cell Receptor Signaling & Survival",
                    "description": "B cells central to SLE pathogenesis.",
                },
                {
                    "id": "complement",
                    "name": "Complement System & Immune Complex Clearance",
                    "description": "Defective clearance hallmark of SLE.",
                },
            ]
        }

    def test_matches_interferon_pathway(self, sample_enrichment, sample_kg_pathways):
        from bioinformatics.enrichment import cross_reference_with_kg_pathways

        matches = cross_reference_with_kg_pathways(sample_enrichment, sample_kg_pathways)
        assert len(matches) > 0
        # Should match "type I interferon signaling pathway" to "Type I Interferon Pathway"
        match_keys = list(matches.keys())
        assert any("type1-ifn" in k for k in match_keys)

    def test_matches_bcell_pathway(self, sample_enrichment, sample_kg_pathways):
        from bioinformatics.enrichment import cross_reference_with_kg_pathways

        matches = cross_reference_with_kg_pathways(sample_enrichment, sample_kg_pathways)
        match_keys = list(matches.keys())
        assert any("bcell-signaling" in k for k in match_keys)

    def test_does_not_match_nucleotide(self, sample_enrichment, sample_kg_pathways):
        from bioinformatics.enrichment import cross_reference_with_kg_pathways

        matches = cross_reference_with_kg_pathways(sample_enrichment, sample_kg_pathways)
        # Nucleotide metabolism should not match any lupus pathway
        match_values = [v for vs in matches.values() for v in vs]
        for m in match_values:
            assert "nucleotide" not in m["enrichment_term"].lower()

    def test_returns_dict(self, sample_enrichment, sample_kg_pathways):
        from bioinformatics.enrichment import cross_reference_with_kg_pathways

        matches = cross_reference_with_kg_pathways(sample_enrichment, sample_kg_pathways)
        assert isinstance(matches, dict)

    def test_empty_enrichment(self, sample_kg_pathways):
        from bioinformatics.enrichment import cross_reference_with_kg_pathways

        matches = cross_reference_with_kg_pathways({}, sample_kg_pathways)
        assert matches == {}

    def test_empty_pathways(self, sample_enrichment):
        from bioinformatics.enrichment import cross_reference_with_kg_pathways

        matches = cross_reference_with_kg_pathways(
            sample_enrichment, {"pathways": []}
        )
        assert matches == {}


class TestLoadFunctions:
    """Tests for data loading in enrichment module."""

    def test_load_kg_genes(self):
        from bioinformatics.enrichment import load_kg_genes

        genes = load_kg_genes()
        assert isinstance(genes, dict)
        assert len(genes) >= 20
        assert "HLA-DRB1" in genes
        assert "IRF5" in genes

    def test_load_kg_graph(self):
        from bioinformatics.enrichment import load_kg_graph

        G = load_kg_graph()
        assert G.number_of_nodes() >= 40
        assert G.number_of_edges() >= 50
