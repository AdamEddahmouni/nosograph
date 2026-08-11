"""Unit tests for the disease-aware drug repurposing report generator.

Tests cover:
  - escape_html(): HTML entity escaping
  - generate_html_report(): output file creation, content validation
"""

from pathlib import Path

import pytest


class TestEscapeHtml:
    """Tests for escape_html()."""

    def test_ampersand(self):
        from med_research.pipeline.drug_repurposing.report import escape_html
        assert escape_html("A & B") == "A &amp; B"

    def test_less_than(self):
        from med_research.pipeline.drug_repurposing.report import escape_html
        assert escape_html("x < 5") == "x &lt; 5"

    def test_greater_than(self):
        from med_research.pipeline.drug_repurposing.report import escape_html
        assert escape_html("x > 5") == "x &gt; 5"

    def test_double_quote(self):
        from med_research.pipeline.drug_repurposing.report import escape_html
        assert escape_html('He said "hello"') == "He said &quot;hello&quot;"

    def test_combined(self):
        from med_research.pipeline.drug_repurposing.report import escape_html
        assert escape_html('<a href="x&y">') == "&lt;a href=&quot;x&amp;y&quot;&gt;"

    def test_no_special_chars(self):
        from med_research.pipeline.drug_repurposing.report import escape_html
        text = "Hello, world 2026!"
        assert escape_html(text) == text

    def test_none_input(self):
        from med_research.pipeline.drug_repurposing.report import escape_html
        assert escape_html(None) == ""

    def test_empty_string(self):
        from med_research.pipeline.drug_repurposing.report import escape_html
        assert escape_html("") == ""


class TestGenerateHtmlReport:
    """Tests for generate_html_report()."""

    @pytest.fixture
    def scored(self, sample_graph, sample_genes, sample_candidates):
        from med_research.pipeline.drug_repurposing.engine import (
            identify_untargeted_genes,
            score_candidates,
        )

        untargeted = identify_untargeted_genes(sample_graph)
        untargeted_ids = {g["id"] for g in untargeted}
        scored = score_candidates(sample_graph, sample_candidates, sample_genes)
        return [c for c in scored if c["gene_id"] in untargeted_ids]

    @pytest.fixture
    def untargeted(self, sample_graph):
        from med_research.pipeline.drug_repurposing.engine import identify_untargeted_genes
        return identify_untargeted_genes(sample_graph)

    def test_creates_output_file(self, scored, untargeted, sample_genes, sample_graph, tmp_path, monkeypatch):
        """Test report generation to a temp directory."""
        import med_research.pipeline.drug_repurposing.report as report_module

        out_path = tmp_path / "report.html"

        # Patch the output_path in generate_html_report to use tmp_path
        original_path = report_module.Path

        class PatchedPath(type(original_path)):
            def __new__(cls, *args, **kwargs):
                return original_path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_html_report(scored, untargeted, sample_genes, sample_graph)
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_report_is_valid_html(self, scored, untargeted, sample_genes, sample_graph, tmp_path, monkeypatch):
        import med_research.pipeline.drug_repurposing.report as report_module

        out_path = tmp_path / "report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_html_report(scored, untargeted, sample_genes, sample_graph)
        content = out_path.read_text(encoding="utf-8")

        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "<head>" in content
        assert "<body>" in content
        assert "</html>" in content

    def test_report_contains_key_sections(self, scored, untargeted, sample_genes, sample_graph, tmp_path, monkeypatch):
        import med_research.pipeline.drug_repurposing.report as report_module

        out_path = tmp_path / "report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_html_report(scored, untargeted, sample_genes, sample_graph)
        content = out_path.read_text(encoding="utf-8")

        assert "Lupus Drug Repurposing Report" in content
        assert "Top Repurposing Candidates" in content
        assert "Per-Gene Analysis" in content
        assert "Methodology" in content

    def test_report_contains_tier1_candidate(self, scored, untargeted, sample_genes, sample_graph, tmp_path, monkeypatch):
        import med_research.pipeline.drug_repurposing.report as report_module

        out_path = tmp_path / "report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_html_report(scored, untargeted, sample_genes, sample_graph)
        content = out_path.read_text(encoding="utf-8")

        assert "Fenebrutinib" in content
        assert "Deucravacitinib" in content

    def test_report_has_stats(self, scored, untargeted, sample_genes, sample_graph, tmp_path, monkeypatch):
        import med_research.pipeline.drug_repurposing.report as report_module

        out_path = tmp_path / "report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_html_report(scored, untargeted, sample_genes, sample_graph)
        content = out_path.read_text(encoding="utf-8")

        assert "Tier 1 Candidates" in content
        assert "Average Composite Score" in content
        assert "Untargeted Lupus Genes" in content

    def test_report_contains_disclaimer(self, scored, untargeted, sample_genes, sample_graph, tmp_path, monkeypatch):
        import med_research.pipeline.drug_repurposing.report as report_module

        out_path = tmp_path / "report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_html_report(scored, untargeted, sample_genes, sample_graph)
        content = out_path.read_text(encoding="utf-8")

        assert "Disclaimer" in content
        assert "computational predictions" in content

    def test_report_escapes_special_chars(self, scored, untargeted, sample_genes, sample_graph, tmp_path, monkeypatch):
        """Verify the HTML doesn't contain unescaped raw special characters in data values."""
        import re

        import med_research.pipeline.drug_repurposing.report as report_module

        out_path = tmp_path / "report.html"

        class PatchedPath(type(Path)):
            def __new__(cls, *args, **kwargs):
                return Path(out_path)

        monkeypatch.setattr(report_module, "Path", PatchedPath)

        report_module.generate_html_report(scored, untargeted, sample_genes, sample_graph)
        content = out_path.read_text(encoding="utf-8")

        # Remove all HTML tags and check remaining text for raw < or >
        text_only = re.sub(r'<[^>]+>', '', content)
        assert '<' not in text_only


