"""
Unit tests for the Lupus Bioinformatics Report Generator.

Tests cover:
  - escape_html(): HTML entity escaping
  - generate_bioinformatics_report(): output file creation, content validation
  - Section builders with various input combinations
"""

from pathlib import Path

import pytest


class TestEnrichmentDotPlot:
    """Tests for _generate_enrichment_dotplot()."""

    def test_returns_base64_png(self):
        from bioinformatics.report import _generate_enrichment_dotplot

        enrichment = {
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
                ],
                "total_significant": 1,
            },
            "KEGG_2021_Human": {
                "library": "KEGG_2021_Human",
                "terms": [
                    {
                        "term": "NF-kappa B signaling pathway",
                        "adj_p_value": 0.02,
                        "genes": ["TNFAIP3"],
                        "odds_ratio": 6.0,
                        "overlap": "1/30",
                        "p_value": 0.03,
                        "combined_score": 40.0,
                    },
                ],
                "total_significant": 1,
            },
        }

        result = _generate_enrichment_dotplot(enrichment)

        # Should return a non-empty base64 string
        assert isinstance(result, str)
        assert len(result) > 100
        # Verify it's valid base64 (decode/re-encode roundtrip)
        import base64
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_returns_empty_for_empty_results(self):
        from bioinformatics.report import _generate_enrichment_dotplot

        result = _generate_enrichment_dotplot({})
        assert result == ""

    def test_returns_empty_for_no_terms(self):
        from bioinformatics.report import _generate_enrichment_dotplot

        enrichment = {
            "GO_Biological_Process_2023": {
                "library": "GO_Biological_Process_2023",
                "terms": [],
                "total_significant": 0,
            },
        }

        result = _generate_enrichment_dotplot(enrichment)
        assert result == ""

    def test_handles_zero_p_value(self):
        """Zero adj_p_value should be clamped to avoid math domain error."""
        from bioinformatics.report import _generate_enrichment_dotplot

        enrichment = {
            "GO_Biological_Process_2023": {
                "library": "GO_Biological_Process_2023",
                "terms": [
                    {
                        "term": "test pathway",
                        "adj_p_value": 0.0,
                        "genes": ["GENE1", "GENE2"],
                        "odds_ratio": 5.0,
                        "overlap": "2/10",
                        "p_value": 0.0,
                        "combined_score": 50.0,
                    },
                ],
                "total_significant": 1,
            },
        }

        result = _generate_enrichment_dotplot(enrichment)
        assert isinstance(result, str)
        assert len(result) > 100


class TestEscapeHtml:
    """Tests for escape_html()."""

    def test_ampersand(self):
        from bioinformatics.report import escape_html
        assert escape_html("A & B") == "A &amp; B"

    def test_less_than(self):
        from bioinformatics.report import escape_html
        assert escape_html("x < 5") == "x &lt; 5"

    def test_greater_than(self):
        from bioinformatics.report import escape_html
        assert escape_html("x > 5") == "x &gt; 5"

    def test_double_quote(self):
        from bioinformatics.report import escape_html
        assert escape_html('He said "hello"') == "He said &quot;hello&quot;"

    def test_combined(self):
        from bioinformatics.report import escape_html
        assert escape_html('<a href="x&y">') == "&lt;a href=&quot;x&amp;y&quot;&gt;"

    def test_no_special_chars(self):
        from bioinformatics.report import escape_html
        text = "Hello, world 2026!"
        assert escape_html(text) == text

    def test_none_input(self):
        from bioinformatics.report import escape_html
        assert escape_html(None) == ""

    def test_empty_string(self):
        from bioinformatics.report import escape_html
        assert escape_html("") == ""


class TestGenerateBioinformaticsReport:
    """Tests for generate_bioinformatics_report()."""

    @pytest.fixture
    def sample_enrichment(self):
        return {
            "GO_Biological_Process_2023": {
                "library": "GO_Biological_Process_2023",
                "terms": [
                    {
                        "term": "type I interferon signaling pathway",
                        "adj_p_value": 1e-6,
                        "genes": ["IRF5", "TLR7"],
                        "odds_ratio": 15.0,
                        "overlap": "2/50",
                        "p_value": 1e-8,
                        "combined_score": 100.0,
                    },
                ],
                "total_significant": 1,
            },
            "KEGG_2021_Human": {
                "library": "KEGG_2021_Human",
                "terms": [
                    {
                        "term": "NF-kappa B signaling pathway",
                        "adj_p_value": 0.02,
                        "genes": ["TNFAIP3"],
                        "odds_ratio": 6.0,
                        "overlap": "1/30",
                        "p_value": 0.03,
                        "combined_score": 40.0,
                    },
                ],
                "total_significant": 1,
            },
            "WikiPathway_2023_Human": {
                "library": "WikiPathway_2023_Human",
                "terms": [],
                "total_significant": 0,
            },
        }

    @pytest.fixture
    def sample_gene_list(self):
        return [
            {"gene_id": "IRF5", "symbol": "IRF5", "name": "Interferon Regulatory Factor 5", "category": "Type I Interferon Pathway", "odds_ratio": 1.8, "chromosome": "7q32.1"},
            {"gene_id": "BTK", "symbol": "BTK", "name": "Bruton Tyrosine Kinase", "category": "B Cell Signaling", "odds_ratio": None, "chromosome": "Xq22.1"},
            {"gene_id": "STAT4", "symbol": "STAT4", "name": "Signal Transducer and Activator of Transcription 4", "category": "JAK-STAT Signaling", "odds_ratio": 1.5, "chromosome": "2q32.2"},
        ]

    @pytest.fixture
    def sample_kg_matches(self):
        return {
            "type1-ifn ↔ type I interferon signaling pathway": [
                {
                    "kg_pathway_id": "type1-ifn",
                    "kg_pathway_name": "Type I Interferon Pathway",
                    "enrichment_term": "type I interferon signaling pathway",
                    "library": "GO_Biological_Process_2023",
                    "adj_p_value": 1e-6,
                }
            ],
        }

    @pytest.fixture
    def sample_hub_scores(self):
        return [
            {
                "node_id": "BTK",
                "symbol": "BTK",
                "gene_id": "BTK",
                "is_seed": True,
                "is_lupus_gene": True,
                "degree": 5,
                "degree_centrality": 0.5,
                "betweenness_centrality": 0.3,
                "hub_score": 0.4,
            },
        ]

    @pytest.fixture
    def sample_ppi_crossref(self):
        return {
            "lupus_hubs": [],
            "non_lupus_hubs": [],
            "hub_candidate_matches": [
                {
                    "node_id": "BTK",
                    "symbol": "BTK",
                    "gene_id": "BTK",
                    "is_seed": True,
                    "is_lupus_gene": True,
                    "degree": 5,
                    "degree_centrality": 0.5,
                    "betweenness_centrality": 0.3,
                    "hub_score": 0.4,
                    "n_candidates": 3,
                    "candidates": [
                        {
                            "drug_name": "Fenebrutinib (GDC-0853)",
                            "composite_score": 9.25,
                        }
                    ],
                },
            ],
            "hub_untargeted": [],
            "top_hubs_overall": [],
        }

    def test_creates_output_file_enrichment_only(self, sample_enrichment, sample_gene_list, tmp_path, monkeypatch):
        import bioinformatics.report as report_module

        out_path = tmp_path / "bioinformatics_report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        result = report_module.generate_bioinformatics_report(
            enrichment_results=sample_enrichment,
            gene_list=sample_gene_list,
        )
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_report_is_valid_html(self, sample_enrichment, sample_gene_list, tmp_path, monkeypatch):
        import bioinformatics.report as report_module

        out_path = tmp_path / "bioinformatics_report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_bioinformatics_report(
            enrichment_results=sample_enrichment,
            gene_list=sample_gene_list,
        )
        content = out_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "<head>" in content
        assert "<body>" in content
        assert "</html>" in content

    def test_report_with_enrichment_and_ppi(
        self, sample_enrichment, sample_gene_list, sample_kg_matches,
        sample_hub_scores, sample_ppi_crossref, tmp_path, monkeypatch
    ):
        import bioinformatics.report as report_module

        out_path = tmp_path / "bioinformatics_report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_bioinformatics_report(
            enrichment_results=sample_enrichment,
            gene_list=sample_gene_list,
            kg_matches=sample_kg_matches,
            hub_scores=sample_hub_scores,
            ppi_crossref=sample_ppi_crossref,
        )
        content = out_path.read_text(encoding="utf-8")

        assert "Pathway Enrichment Analysis" in content
        assert "PPI Network Hub Analysis" in content
        assert "Fenebrutinib" in content

    def test_report_with_enrichment_section(self, sample_enrichment, sample_gene_list, tmp_path, monkeypatch):
        import bioinformatics.report as report_module

        out_path = tmp_path / "bioinformatics_report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_bioinformatics_report(
            enrichment_results=sample_enrichment,
            gene_list=sample_gene_list,
        )
        content = out_path.read_text(encoding="utf-8")

        assert "Pathway Enrichment Analysis" in content
        assert "GO_Biological_Process_2023" in content
        assert "KEGG_2021_Human" in content
        assert "Significant Enriched Pathways" in content
        assert "Lupus Genes Analyzed" in content

    def test_report_with_ppi_section(self, sample_hub_scores, sample_ppi_crossref, tmp_path, monkeypatch):
        import bioinformatics.report as report_module

        out_path = tmp_path / "bioinformatics_report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_bioinformatics_report(
            hub_scores=sample_hub_scores,
            ppi_crossref=sample_ppi_crossref,
        )
        content = out_path.read_text(encoding="utf-8")

        assert "PPI Network Hub Analysis" in content
        assert "BTK" in content
        assert "Top Hub Proteins" in content

    def test_report_with_gwas_section(self, tmp_path, monkeypatch):
        import bioinformatics.report as report_module

        gwas_results = {
            "gene_associations": {
                "HLA-DRB1": {
                    "n_studies": 15,
                    "best_p_value": 1e-50,
                    "studies": [],
                },
            },
            "total_studies_analyzed": 30,
            "total_associations": 500,
            "study_details": [],
        }
        gwas_crossref = {
            "validated": {
                "HLA-DRB1": {
                    "gene_id": "HLA-DRB1",
                    "name": "HLA Class II DR Beta 1",
                    "category": "MHC / Antigen Presentation",
                    "odds_ratio": 2.5,
                    "n_gwas_studies": 15,
                    "gwas_best_p": 1e-50,
                    "gwas_studies": [],
                },
            },
            "novel": {},
            "missing": {},
            "n_validated": 1,
            "n_novel": 0,
            "n_missing": 0,
        }

        out_path = tmp_path / "bioinformatics_report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_bioinformatics_report(
            gwas_results=gwas_results,
            gwas_crossref=gwas_crossref,
        )
        content = out_path.read_text(encoding="utf-8")

        assert "GWAS Catalog Annotation" in content
        assert "HLA-DRB1" in content
        assert "Validated" in content

    def test_report_empty_produces_output(self, tmp_path, monkeypatch):
        """Report should still generate even with no data."""
        import bioinformatics.report as report_module

        out_path = tmp_path / "bioinformatics_report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_bioinformatics_report()
        content = out_path.read_text(encoding="utf-8")

        assert "<!DOCTYPE html>" in content
        assert "Lupus Bioinformatics Report" in content
        assert "No data available" in content

    def test_report_contains_disclaimer(self, tmp_path, monkeypatch):
        import bioinformatics.report as report_module

        out_path = tmp_path / "bioinformatics_report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_bioinformatics_report()
        content = out_path.read_text(encoding="utf-8")

        assert "Disclaimer" in content
        assert "Computational predictions" in content

    def test_report_contains_plot(self, sample_enrichment, sample_gene_list, tmp_path, monkeypatch):
        """Report with enrichment data should contain the dot plot image."""
        import bioinformatics.report as report_module

        out_path = tmp_path / "bioinformatics_report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_bioinformatics_report(
            enrichment_results=sample_enrichment,
            gene_list=sample_gene_list,
        )
        content = out_path.read_text(encoding="utf-8")

        assert "enrichment-plot" in content
        assert "data:image/png;base64," in content

    def test_report_contains_nav_links(self, tmp_path, monkeypatch):
        import bioinformatics.report as report_module

        out_path = tmp_path / "bioinformatics_report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_bioinformatics_report()
        content = out_path.read_text(encoding="utf-8")

        assert "Knowledge Graph" in content
        assert "Drug Repurposing Report" in content
        assert "Literature Mining Report" in content
