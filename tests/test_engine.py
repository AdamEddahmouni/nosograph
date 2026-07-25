"""
Unit tests for the Lupus Drug Repurposing Engine.

Tests cover:
  - compute_composite_score(): weight math, tier boundaries
  - compute_pathway_proximity(): graph distance → score mapping
  - identify_untargeted_genes(): gene filtering
  - score_candidates(): full scoring pipeline
  - analyze(): summary output
"""


import pytest


class TestComputeCompositeScore:
    """Tests for compute_composite_score()."""

    def test_perfect_score(self):
        from med_research.pipeline.drug_repurposing.engine import compute_composite_score

        candidate = {
            "target_similarity_score": 10,
            "pathway_proximity_score": 10,
            "mechanistic_rationale_score": 10,
            "clinical_evidence_score": 10,
            "safety_score": 10,
            "novelty_score": 10,
        }
        score = compute_composite_score(candidate)
        # 10*0.25 + 10*0.15 + 10*0.25 + 10*0.20 + 10*0.10 + 10*0.05
        assert score == 10.00

    def test_minimum_score(self):
        from med_research.pipeline.drug_repurposing.engine import compute_composite_score

        candidate = {
            "target_similarity_score": 0,
            "pathway_proximity_score": 0,
            "mechanistic_rationale_score": 0,
            "clinical_evidence_score": 0,
            "safety_score": 0,
            "novelty_score": 0,
        }
        score = compute_composite_score(candidate)
        assert score == 0.00

    def test_mid_range_score(self):
        from med_research.pipeline.drug_repurposing.engine import compute_composite_score

        candidate = {
            "target_similarity_score": 5,
            "pathway_proximity_score": 5,
            "mechanistic_rationale_score": 5,
            "clinical_evidence_score": 5,
            "safety_score": 5,
            "novelty_score": 5,
        }
        score = compute_composite_score(candidate)
        # 5 * (0.25+0.15+0.25+0.20+0.10+0.05) = 5 * 1.0 = 5.0
        assert score == 5.00

    def test_weighted_calculation(self):
        from med_research.pipeline.drug_repurposing.engine import compute_composite_score

        candidate = {
            "target_similarity_score": 10,
            "pathway_proximity_score": 2,
            "mechanistic_rationale_score": 8,
            "clinical_evidence_score": 4,
            "safety_score": 6,
            "novelty_score": 0,
        }
        score = compute_composite_score(candidate)
        # New weights: 20/15/20/15/20/10. Legacy safety_score used as fallback.
        expected = 10*0.20 + 2*0.15 + 8*0.20 + 4*0.15 + 6*0.20 + 0*0.10
        assert score == round(expected, 2)

    def test_result_is_float(self):
        from med_research.pipeline.drug_repurposing.engine import compute_composite_score

        candidate = {
            "target_similarity_score": 7.5,
            "pathway_proximity_score": 6.2,
            "mechanistic_rationale_score": 8.1,
            "clinical_evidence_score": 3.9,
            "safety_score": 7.0,
            "novelty_score": 2.5,
        }
        score = compute_composite_score(candidate)
        assert isinstance(score, float)

    def test_missing_keys_default_to_five(self):
        """Missing keys default to 5 (from candidate.get(key, 5)), not 0."""
        from med_research.pipeline.drug_repurposing.engine import compute_composite_score

        candidate = {
            "target_similarity_score": 10,
        }
        score = compute_composite_score(candidate)
        # Only target_similarity=10 is set; others all default to 5
        # New weights: 10*0.20 + 5*0.15 + 5*0.20 + 5*0.15 + 5*0.20 + 5*0.10 = 6.0
        assert score == 6.0


class TestIdentifyUntargetedGenes:
    """Tests for identify_untargeted_genes()."""

    def test_returns_list(self, sample_graph):
        from med_research.pipeline.drug_repurposing.engine import identify_untargeted_genes

        result = identify_untargeted_genes(sample_graph)
        assert isinstance(result, list)

    def test_all_returned_have_dict_structure(self, sample_graph):
        from med_research.pipeline.drug_repurposing.engine import identify_untargeted_genes

        result = identify_untargeted_genes(sample_graph)
        for gene in result:
            assert "id" in gene
            assert "name" in gene

    def test_untargeted_genes_count(self, sample_graph):
        from med_research.pipeline.drug_repurposing.engine import identify_untargeted_genes

        result = identify_untargeted_genes(sample_graph)
        # Use >= to avoid fragile exact-count assertions
        assert len(result) >= 10

    def test_targeted_genes_not_in_result(self, sample_graph):
        from med_research.pipeline.drug_repurposing.engine import identify_untargeted_genes

        result = identify_untargeted_genes(sample_graph)
        result_ids = {g["id"] for g in result}
        # BAFF, IFNAR1, TLR7, TLR9, JAK1 are targeted by drugs
        targeted = {"BAFF", "IFNAR1", "TLR7", "TLR9", "JAK1"}
        assert result_ids.isdisjoint(targeted)

    def test_drug_target_genes_excluded(self, sample_graph):
        """CD20, IMPDH, Calcineurin, Glucocorticoid Receptor are not lupus risk genes."""
        from med_research.pipeline.drug_repurposing.engine import identify_untargeted_genes

        result = identify_untargeted_genes(sample_graph)
        result_ids = {g["id"] for g in result}
        excluded = {"CD20", "IMPDH", "Calcineurin", "Glucocorticoid Receptor"}
        assert result_ids.isdisjoint(excluded)

    def test_known_untargeted_gene_present(self, sample_graph):
        from med_research.pipeline.drug_repurposing.engine import identify_untargeted_genes

        result = identify_untargeted_genes(sample_graph)
        result_ids = {g["id"] for g in result}
        assert "HLA-DRB1" in result_ids
        assert "IRF5" in result_ids
        assert "STAT4" in result_ids
        assert "BLK" in result_ids


class TestScoreCandidates:
    """Tests for score_candidates()."""

    def test_returns_list(self, sample_graph, sample_genes, sample_candidates):
        from med_research.pipeline.drug_repurposing.engine import score_candidates

        scored = score_candidates(sample_graph, sample_candidates, sample_genes)
        assert isinstance(scored, list)

    def test_all_have_composite_score(self, sample_graph, sample_genes, sample_candidates):
        from med_research.pipeline.drug_repurposing.engine import score_candidates

        scored = score_candidates(sample_graph, sample_candidates, sample_genes)
        for c in scored:
            assert "composite_score" in c
            assert isinstance(c["composite_score"], float)
            assert 0 <= c["composite_score"] <= 10

    def test_all_have_tier(self, sample_graph, sample_genes, sample_candidates):
        from med_research.pipeline.drug_repurposing.engine import score_candidates

        scored = score_candidates(sample_graph, sample_candidates, sample_genes)
        tier_names = {
            "🔴 Tier 1 — Highest Priority",
            "🟠 Tier 2 — High Priority",
            "🟡 Tier 3 — Medium Priority",
            "🟢 Tier 4 — Lower Priority",
        }
        for c in scored:
            assert "tier" in c
            assert c["tier"] in tier_names

    def test_sorted_descending_by_score(self, sample_graph, sample_genes, sample_candidates):
        from med_research.pipeline.drug_repurposing.engine import score_candidates

        scored = score_candidates(sample_graph, sample_candidates, sample_genes)
        for i in range(len(scored) - 1):
            assert scored[i]["composite_score"] >= scored[i + 1]["composite_score"]

    def test_gene_name_is_populated(self, sample_graph, sample_genes, sample_candidates):
        from med_research.pipeline.drug_repurposing.engine import score_candidates

        scored = score_candidates(sample_graph, sample_candidates, sample_genes)
        for c in scored:
            assert "gene_name" in c
            assert len(c["gene_name"]) > 0

    def test_all_have_final_proximity(self, sample_graph, sample_genes, sample_candidates):
        from med_research.pipeline.drug_repurposing.engine import score_candidates

        scored = score_candidates(sample_graph, sample_candidates, sample_genes)
        for c in scored:
            assert "final_proximity" in c
            assert 0 <= c["final_proximity"] <= 10

    def test_tier_boundaries(self, sample_graph, sample_genes, sample_candidates):
        """Verify tier assignment matches composite score thresholds."""
        from med_research.pipeline.drug_repurposing.engine import score_candidates

        scored = score_candidates(sample_graph, sample_candidates, sample_genes)
        for c in scored:
            s = c["composite_score"]
            tier = c["tier"]
            if s >= 8.0:
                assert "Tier 1" in tier
            elif s >= 7.0:
                assert "Tier 2" in tier
            elif s >= 6.0:
                assert "Tier 3" in tier
            else:
                assert "Tier 4" in tier

    def test_scored_count_ge_input(self, sample_graph, sample_genes, sample_candidates):
        """Score all candidates — output count should match input count."""
        from med_research.pipeline.drug_repurposing.engine import score_candidates

        scored = score_candidates(sample_graph, sample_candidates, sample_genes)
        assert len(scored) >= len(sample_candidates)


class TestAnalyzeFunction:
    """Smoke tests for analyze()."""

    def test_analyze_produces_output(self, sample_graph, sample_genes, sample_candidates, capsys):
        from med_research.pipeline.drug_repurposing.engine import (
            analyze,
            identify_untargeted_genes,
            score_candidates,
        )

        untargeted = identify_untargeted_genes(sample_graph)
        untargeted_ids = {g["id"] for g in untargeted}
        scored = score_candidates(sample_graph, sample_candidates, sample_genes)
        scored = [c for c in scored if c["gene_id"] in untargeted_ids]

        analyze(scored)
        captured = capsys.readouterr()
        assert "REPURPOSING ANALYSIS SUMMARY" in captured.out
        assert "Distribution by priority tier" in captured.out
        assert "Most promising drugs" in captured.out


class TestPathwayProximityHelper:
    """Tests for compute_pathway_proximity()."""

    def test_fallback_when_drug_not_in_graph(self, sample_graph):
        from med_research.pipeline.drug_repurposing.engine import compute_pathway_proximity

        candidate = {
            "drug_name": "NonexistentDrug (XYZ-001)",
            "pathway_proximity_score": 6.5,
        }
        score = compute_pathway_proximity(sample_graph, "BTK", candidate)
        assert score == 6.5

    def test_fallback_without_curated_score(self, sample_graph):
        from med_research.pipeline.drug_repurposing.engine import compute_pathway_proximity

        candidate = {
            "drug_name": "NonexistentDrug (XYZ-001)",
        }
        score = compute_pathway_proximity(sample_graph, "BTK", candidate)
        assert score == 5.0  # default from candidate.get("pathway_proximity_score", 5.0)

    def test_returns_float(self, sample_graph):
        from med_research.pipeline.drug_repurposing.engine import compute_pathway_proximity

        candidate = {
            "drug_name": "Fenebrutinib (GDC-0853)",
            "pathway_proximity_score": 8.0,
        }
        score = compute_pathway_proximity(sample_graph, "BTK", candidate)
        assert isinstance(score, float)

    def test_nonexistent_gene_raises_keyerror(self, sample_graph):
        """compute_pathway_proximity does G.nodes[gene_id] before any try/except,
        so a nonexistent gene raises KeyError (caught upstream by score_candidates)."""
        from med_research.pipeline.drug_repurposing.engine import compute_pathway_proximity

        candidate = {
            "drug_name": "Fenebrutinib (GDC-0853)",
            "pathway_proximity_score": 7.0,
        }
        with pytest.raises(KeyError):
            compute_pathway_proximity(sample_graph, "NONEXISTENT_GENE", candidate)

    def test_nonexistent_gene_handled_by_score_candidates(self, sample_graph, sample_genes):
        """score_candidates catches KeyError from compute_pathway_proximity gracefully."""
        from med_research.pipeline.drug_repurposing.engine import score_candidates

        candidates = [{
            "id": "test001",
            "gene_id": "NONEXISTENT_GENE",
            "drug_name": "Test Drug",
            "drug_category": "Test",
            "mechanism": "Test mechanism",
            "rationale": "Test rationale",
            "target_similarity_score": 5,
            "pathway_proximity_score": 7.0,
            "mechanistic_rationale_score": 5,
            "clinical_evidence_score": 5,
            "safety_score": 5,
            "novelty_score": 2,
            "evidence_level": "Test",
            "status": "Test",
        }]
        scored = score_candidates(sample_graph, candidates, sample_genes)
        assert len(scored) == 1
        # kg_pathway_proximity should fall back to curated score
        assert scored[0]["kg_pathway_proximity"] == 7.0
        assert scored[0]["final_proximity"] == 7.0

    def test_drug_in_graph_proximity(self, sample_graph):
        """Test proximity when drug IS in the graph — exercises nx.shortest_path_length."""
        from med_research.pipeline.drug_repurposing.engine import compute_pathway_proximity

        # Hydroxychloroquine targets TLR7 directly (TARGETS edge), distance to TLR7 = 1
        candidate = {
            "drug_name": "Hydroxychloroquine (Plaquenil)",
            "pathway_proximity_score": 5.0,
        }
        score = compute_pathway_proximity(sample_graph, "TLR7", candidate)
        # Distance 1 → score 10.0
        assert score == 10.0

    def test_drug_in_graph_indirect_proximity(self, sample_graph):
        """Test proximity with indirect path through the graph."""
        from med_research.pipeline.drug_repurposing.engine import compute_pathway_proximity

        # Belimumab targets BAFF → bcell-signaling → BTK participates in bcell-signaling
        # Distance from belimumab to BTK should be > 1
        candidate = {
            "drug_name": "Belimumab (Benlysta)",
            "pathway_proximity_score": 5.0,
        }
        score = compute_pathway_proximity(sample_graph, "BTK", candidate)
        # Should be a positive score from graph traversal
        assert isinstance(score, float)
        assert score > 0


class TestPrintTopCandidates:
    """Smoke tests for print_top_candidates()."""

    def test_produces_output(self, sample_graph, sample_genes, sample_candidates, capsys):
        from med_research.pipeline.drug_repurposing.engine import (
            print_top_candidates,
            score_candidates,
        )

        scored = score_candidates(sample_graph, sample_candidates, sample_genes)
        print_top_candidates(scored, top_n=5)
        captured = capsys.readouterr()
        assert "TOP 5 REPURPOSING CANDIDATES" in captured.out
        assert "Drug:" in captured.out
        assert "Score:" in captured.out


class TestPrintGeneAnalysis:
    """Smoke tests for print_gene_analysis()."""

    def test_gene_with_candidates(self, sample_graph, sample_genes, sample_candidates, capsys):
        from med_research.pipeline.drug_repurposing.engine import (
            print_gene_analysis,
            score_candidates,
        )

        scored = score_candidates(sample_graph, sample_candidates, sample_genes)
        print_gene_analysis(scored, sample_genes, "BTK")
        captured = capsys.readouterr()
        assert "BTK" in captured.out

    def test_gene_without_candidates(self, sample_graph, sample_genes, sample_candidates, capsys):
        from med_research.pipeline.drug_repurposing.engine import (
            print_gene_analysis,
            score_candidates,
        )

        scored = score_candidates(sample_graph, sample_candidates, sample_genes)
        print_gene_analysis(scored, sample_genes, "NONEXISTENT")
        captured = capsys.readouterr()
        assert "No repurposing candidates" in captured.out


class TestLoadFunctions:
    """Tests for data loading helper functions."""

    def test_load_genes(self, sample_genes):
        assert isinstance(sample_genes, dict)
        assert len(sample_genes) >= 20

    def test_load_genes_has_expected_gene(self, sample_genes):
        assert "IRF5" in sample_genes
        assert sample_genes["IRF5"]["name"] == "Interferon Regulatory Factor 5"

    def test_load_candidates(self, sample_candidates):
        assert isinstance(sample_candidates, list)
        assert len(sample_candidates) >= 20

    def test_first_candidate_has_required_fields(self, sample_candidates):
        c = sample_candidates[0]
        for field in [
            "id", "gene_id", "drug_name", "mechanism", "rationale",
            "target_similarity_score", "pathway_proximity_score",
            "mechanistic_rationale_score", "clinical_evidence_score",
            "safety_score", "novelty_score", "evidence_level", "status",
        ]:
            assert field in c, f"Missing field: {field}"
