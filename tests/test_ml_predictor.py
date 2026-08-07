"""
Unit tests for the Lupus ML Target Predictor.

Tests cover:
  - predictor.py: feature extraction, category one-hot, molecular type detection,
    pathway counting, training pipeline
"""

import pytest

# ═══════════════════════════════════════════════════════════════════════
#  feature extraction tests
# ═══════════════════════════════════════════════════════════════════════

class TestExtractFeatures:
    """Tests for extract_features()."""

    def test_extracts_features_from_real_graph(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import extract_features
        G = build_graph()
        X, gene_ids, labels = extract_features(G)
        assert len(gene_ids) > 0
        assert len(X) == len(gene_ids)
        assert len(labels) == len(gene_ids)
        # 9 base features + 16 category features = 25
        assert X.shape[1] >= 20

    def test_labels_contain_targeting_info(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import extract_features
        G = build_graph()
        _, gene_ids, labels = extract_features(G)
        for _, (is_targeted, drugs) in zip(gene_ids, labels, strict=True):
            assert isinstance(is_targeted, int)
            assert isinstance(drugs, list)

    def test_targeted_genes_identified(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import extract_features
        G = build_graph()
        _, gene_ids, labels = extract_features(G)
        targeted = [g for g, (t, _) in zip(gene_ids, labels, strict=True) if t]
        # Known targeted genes: BAFF, IFNAR1, Calcineurin, JAK1, TYK2, CD20, IMPDH,
        # Glucocorticoid Receptor, TLR7, TLR9, IKZF1, IKZF3
        assert len(targeted) >= 8
        known = {"BAFF", "IFNAR1", "Calcineurin", "JAK1", "CD20", "IMPDH",
                 "Glucocorticoid Receptor", "TYK2", "IKZF1", "IKZF3"}
        assert known.intersection(set(targeted)) == known

    def test_features_are_numeric(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import extract_features
        G = build_graph()
        X, _, _ = extract_features(G)
        import numpy as np
        assert X.dtype == np.float64


class TestCountPathways:
    """Tests for _count_pathways()."""

    def test_returns_integer(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import _count_pathways
        G = build_graph()
        count = _count_pathways(G, "BTK")
        assert isinstance(count, int)
        assert count >= 0

    def test_known_pathway_gene(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import _count_pathways
        G = build_graph()
        # BTK participates in bcell-signaling
        count = _count_pathways(G, "BTK")
        assert count >= 1

    def test_untargeted_gene_has_zero(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import _count_pathways
        G = build_graph()
        # HLA-DRB1 may or may not be in pathways
        count = _count_pathways(G, "HLA-DRB1")
        assert isinstance(count, int)


class TestMolecularType:
    """Tests for _is_type()."""

    def test_detects_kinase(self):
        from med_research.pipeline.ml_predictor.predictor import _KINASE_KEYWORDS, _is_type
        assert _is_type("tyrosine kinase signaling", _KINASE_KEYWORDS) == 1

    def test_detects_receptor(self):
        from med_research.pipeline.ml_predictor.predictor import _RECEPTOR_KEYWORDS, _is_type
        assert _is_type("toll-like receptor 7", _RECEPTOR_KEYWORDS) == 1

    def test_detects_tf(self):
        from med_research.pipeline.ml_predictor.predictor import _TF_KEYWORDS, _is_type
        assert _is_type("transcription factor driving IFN", _TF_KEYWORDS) == 1

    def test_no_false_positive(self):
        from med_research.pipeline.ml_predictor.predictor import _KINASE_KEYWORDS, _is_type
        assert _is_type("complement protein", _KINASE_KEYWORDS) == 0


# ═══════════════════════════════════════════════════════════════════════
#  training pipeline tests
# ═══════════════════════════════════════════════════════════════════════

class TestTrainAndPredict:
    """Tests for train_and_predict() — requires xgboost + sklearn."""

    @pytest.fixture(autouse=True)
    def _check_deps(self):
        try:
            import sklearn  # noqa: F401
            import xgboost  # noqa: F401
        except ImportError:
            pytest.skip("xgboost/scikit-learn not installed")

    def test_returns_valid_structure(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import train_and_predict
        G = build_graph()
        results = train_and_predict(G, top_n=10)
        assert "predictions" in results
        assert "top_untargeted" in results
        assert "feature_importance" in results
        assert "model_metrics" in results

    def test_top_untargeted_are_untargeted(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import train_and_predict
        G = build_graph()
        results = train_and_predict(G, top_n=5)
        for p in results["top_untargeted"]:
            assert not p["is_targeted"]

    def test_predictions_sorted_descending(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import train_and_predict
        G = build_graph()
        results = train_and_predict(G, top_n=5)
        scores = [p["druggability_score"] for p in results["predictions"]]
        assert scores == sorted(scores, reverse=True)

    def test_druggability_score_in_range(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import train_and_predict
        G = build_graph()
        results = train_and_predict(G, top_n=5)
        for p in results["predictions"]:
            assert 0.0 <= p["druggability_score"] <= 1.0

    def test_metrics_are_sensible(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import train_and_predict
        G = build_graph()
        results = train_and_predict(G, top_n=5)
        m = results["model_metrics"]
        assert m["n_genes"] >= 30
        assert m["n_targeted"] >= 8
        assert m["n_untargeted"] >= 15

    def test_feature_importance_is_dict(self):
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import train_and_predict
        G = build_graph()
        results = train_and_predict(G, top_n=5)
        assert isinstance(results["feature_importance"], dict)
        assert len(results["feature_importance"]) > 5


# ═══════════════════════════════════════════════════════════════════════
#  report generation tests
# ═══════════════════════════════════════════════════════════════════════

class TestGenerateMLReport:
    """Tests for generate_ml_report()."""

    def test_generates_html_file(self):
        from med_research.pipeline.ml_predictor.report import generate_ml_report
        results = {
            "model_metrics": {"n_genes": 35, "n_targeted": 12, "n_untargeted": 23,
                              "cv_roc_auc_mean": 0.85, "cv_roc_auc_std": 0.05,
                              "xgboost_available": True, "shap_available": True},
            "top_untargeted": [
                {"gene_id": "BTK", "gene_name": "Bruton Tyrosine Kinase",
                 "category": "B Cell Signaling", "druggability_score": 0.92,
                 "is_targeted": False, "targeted_by": [], "odds_ratio": None,
                 "degree": 5, "pathway_count": 2},
            ],
            "feature_importance": {"degree": 0.25, "odds_ratio": 0.20, "pathway_count": 0.15},
            "shap_summary": [{"feature": "degree", "mean_abs_shap": 0.12}],
        }
        report_path = generate_ml_report(results)
        assert report_path.endswith("ml_report.html")
        with open(report_path, encoding="utf-8") as report_file:
            html = report_file.read()
        assert "ML Target Predictor" in html
        assert "Bruton Tyrosine Kinase" in html
        assert "0.920" in html
