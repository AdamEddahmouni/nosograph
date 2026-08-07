"""
Unit tests for the Lupus GWAS Annotation module.

Tests cover:
  - extract_gene_associations(): parsing, aggregation
  - cross_reference_with_kg(): matching logic
  - Data loading functions
"""

import pytest


class TestCrossReferenceWithKG:
    """Tests for cross_reference_with_kg()."""

    @pytest.fixture
    def sample_gwas_results(self):
        return {
            "gene_associations": {
                "HLA-DRB1": {
                    "n_studies": 15,
                    "best_p_value": 1e-50,
                    "studies": [
                        {
                            "accession": "GCST001",
                            "title": "GWAS of SLE in European population",
                            "pubmed_id": "26502338",
                            "p_value": 1e-50,
                        }
                    ],
                },
                "STAT4": {
                    "n_studies": 8,
                    "best_p_value": 1e-20,
                    "studies": [],
                },
                "NOVELGENE": {
                    "n_studies": 5,
                    "best_p_value": 1e-12,
                    "studies": [],
                },
            },
            "total_studies_analyzed": 30,
            "total_associations": 500,
            "study_details": [],
        }

    @pytest.fixture
    def sample_kg_genes(self):
        return {
            "HLA-DRB1": {
                "id": "HLA-DRB1",
                "name": "HLA Class II DR Beta 1",
                "category": "MHC / Antigen Presentation",
                "odds_ratio": 2.5,
                "chromosome": "6p21.32",
            },
            "STAT4": {
                "id": "STAT4",
                "name": "Signal Transducer and Activator of Transcription 4",
                "category": "JAK-STAT Signaling",
                "odds_ratio": 1.5,
                "chromosome": "2q32.2",
            },
            "CD20": {
                "id": "CD20",
                "name": "CD20 (MS4A1)",
                "category": "B Cell Signaling",
                "odds_ratio": None,
                "chromosome": "11q12.2",
            },
            "BANK1": {
                "id": "BANK1",
                "name": "B Cell Scaffold Protein with Ankyrin Repeats 1",
                "category": "B Cell Signaling",
                "odds_ratio": 1.3,
                "chromosome": "4q24",
            },
        }

    def test_validates_known_genes(self, sample_gwas_results, sample_kg_genes):
        from med_research.pipeline.bioinformatics.gwas import cross_reference_with_kg

        crossref = cross_reference_with_kg(sample_gwas_results, sample_kg_genes)

        assert "HLA-DRB1" in crossref["validated"]
        assert "STAT4" in crossref["validated"]
        assert crossref["n_validated"] >= 2

    def test_novel_genes_identified(self, sample_gwas_results, sample_kg_genes):
        from med_research.pipeline.bioinformatics.gwas import cross_reference_with_kg

        crossref = cross_reference_with_kg(sample_gwas_results, sample_kg_genes)

        assert "NOVELGENE" in crossref["novel"]
        assert crossref["n_novel"] >= 1

    def test_missing_kg_genes(self, sample_gwas_results, sample_kg_genes):
        from med_research.pipeline.bioinformatics.gwas import cross_reference_with_kg

        crossref = cross_reference_with_kg(sample_gwas_results, sample_kg_genes)

        # BANK1 is in KG but not in GWAS results
        assert "BANK1" in crossref["missing"]

    def test_drug_target_genes_excluded_from_missing(self, sample_gwas_results, sample_kg_genes):
        from med_research.pipeline.bioinformatics.gwas import cross_reference_with_kg

        crossref = cross_reference_with_kg(sample_gwas_results, sample_kg_genes)

        # CD20 is a drug target gene — should not appear in missing
        missing_ids = set(crossref["missing"].keys())
        assert "CD20" not in missing_ids

    def test_validated_has_extra_fields(self, sample_gwas_results, sample_kg_genes):
        from med_research.pipeline.bioinformatics.gwas import cross_reference_with_kg

        crossref = cross_reference_with_kg(sample_gwas_results, sample_kg_genes)
        validated = crossref["validated"]

        for _, info in validated.items():
            assert "n_gwas_studies" in info
            assert "gwas_best_p" in info
            assert "category" in info
            assert "gene_id" in info

    def test_counts_are_correct(self, sample_gwas_results, sample_kg_genes):
        from med_research.pipeline.bioinformatics.gwas import cross_reference_with_kg

        crossref = cross_reference_with_kg(sample_gwas_results, sample_kg_genes)

        assert crossref["n_validated"] == len(crossref["validated"])
        assert crossref["n_novel"] == len(crossref["novel"])
        assert crossref["n_missing"] == len(crossref["missing"])

    def test_empty_gwas(self, sample_kg_genes):
        from med_research.pipeline.bioinformatics.gwas import cross_reference_with_kg

        empty_gwas = {"gene_associations": {}, "total_studies_analyzed": 0, "total_associations": 0, "study_details": []}
        crossref = cross_reference_with_kg(empty_gwas, sample_kg_genes)

        assert crossref["n_validated"] == 0
        assert crossref["n_novel"] == 0
        assert crossref["n_missing"] >= 1  # BANK1 is in KG but not GWAS

    def test_case_insensitive_matching(self, sample_kg_genes):
        from med_research.pipeline.bioinformatics.gwas import cross_reference_with_kg

        # GWAS uses lowercase gene names
        gwas = {
            "gene_associations": {
                "hla-drb1": {
                    "n_studies": 15,
                    "best_p_value": 1e-50,
                    "studies": [],
                },
            },
            "total_studies_analyzed": 30,
            "total_associations": 500,
            "study_details": [],
        }

        crossref = cross_reference_with_kg(gwas, sample_kg_genes)
        assert crossref["n_validated"] >= 1
        # HLA-DRB1 should match despite case difference
        assert "hla-drb1" in crossref["validated"]


class TestExtractGeneAssociations:
    """Tests for extract_gene_associations()."""

    def test_empty_studies(self):
        from med_research.pipeline.bioinformatics.gwas import extract_gene_associations

        result = extract_gene_associations([])
        assert result["total_studies_analyzed"] == 0
        assert result["total_associations"] == 0
        assert result["gene_associations"] == {}

    def test_result_structure(self):
        from med_research.pipeline.bioinformatics.gwas import extract_gene_associations

        result = extract_gene_associations([])
        for key in ["gene_associations", "total_studies_analyzed", "total_associations", "study_details"]:
            assert key in result

    def test_disease_search_terms_resolution(self):
        from med_research.pipeline.bioinformatics.gwas import disease_search_terms

        # RA reads its own GWAS_SEARCH_TERMS config
        ra = disease_search_terms("ra")
        assert "rheumatoid arthritis" in ra
        assert "RA" in ra

        # Unknown disease has no valid search scope and must not query SLE.
        assert disease_search_terms("no_such_disease") == []
