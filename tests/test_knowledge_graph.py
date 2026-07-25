"""
Unit tests for the Lupus Knowledge Graph Builder.

Tests cover:
  - build_graph(): node counts, node types, edge types, specific nodes
  - export_for_web(): JSON structure, element counts
  - analyze_graph(): smoke test (doesn't crash)
"""

import json

import networkx as nx
import pytest


class TestBuildGraph:
    """Tests for build_graph()."""

    def test_graph_is_multidigraph(self, sample_graph):
        assert isinstance(sample_graph, nx.MultiDiGraph)

    def test_node_count(self, sample_graph):
        # Use >= to avoid fragile exact-count assertions
        assert sample_graph.number_of_nodes() >= 40

    def test_edge_count(self, sample_graph):
        assert sample_graph.number_of_edges() >= 50

    def test_node_types_present(self, sample_graph):
        types = set()
        for _, data in sample_graph.nodes(data=True):
            types.add(data.get("type"))
        assert types == {"disease", "gene", "drug", "pathway"}

    def test_disease_node_exists(self, sample_graph):
        node = sample_graph.nodes["Lupus (SLE)"]
        assert node["type"] == "disease"
        assert "Systemic Lupus Erythematosus" in node["label"]
        assert node["prevalence"] == "~5 million worldwide"

    def test_gene_nodes_have_required_fields(self, sample_graph):
        for node, data in sample_graph.nodes(data=True):
            if data.get("type") == "gene":
                assert "label" in data
                assert "chromosome" in data
                assert "category" in data

    def test_drug_nodes_have_required_fields(self, sample_graph):
        for node, data in sample_graph.nodes(data=True):
            if data.get("type") == "drug":
                assert "label" in data
                assert "target" in data

    def test_pathway_nodes_have_required_fields(self, sample_graph):
        for node, data in sample_graph.nodes(data=True):
            if data.get("type") == "pathway":
                assert "label" in data
                assert "description" in data

    def test_key_genes_present(self, sample_graph):
        gene_ids = {
            n for n, d in sample_graph.nodes(data=True) if d.get("type") == "gene"
        }
        expected = {
            "HLA-DRB1", "IRF5", "STAT4", "BLK", "TNFAIP3",
            "ITGAM", "BANK1", "PTPN22", "TNFSF4", "FCGR2A",
            "FCGR3A", "TLR7", "TLR9", "BAFF", "IFNAR1",
            "JAK1", "TYK2", "BTK",
        }
        assert expected.issubset(gene_ids)

    def test_key_drugs_present(self, sample_graph):
        drug_ids = {
            n for n, d in sample_graph.nodes(data=True) if d.get("type") == "drug"
        }
        expected = {
            "belimumab", "anifrolumab", "voclosporin", "hydroxychloroquine",
            "mycophenolate", "cyclophosphamide", "rituximab", "prednisone",
            "tacrolimus", "azathioprine", "baricitinib", "obinutuzumab",
        }
        assert expected.issubset(drug_ids)

    def test_edge_types_present(self, sample_graph):
        types = set()
        for _, _, data in sample_graph.edges(data=True):
            types.add(data.get("type"))
        expected = {"TARGETS", "PARTICIPATES_IN", "MODULATES", "DRIVES", "ASSOCIATED_WITH", "TREATS"}
        assert types == expected

    def test_treats_edges_exist(self, sample_graph):
        """Verify FDA-approved therapies have TREATS edges to the disease node."""
        treats_edges = []
        for u, v, data in sample_graph.edges(data=True):
            if data.get("type") == "TREATS" and v == "Lupus (SLE)":
                treats_edges.append(u)
        assert "belimumab" in treats_edges
        assert "anifrolumab" in treats_edges
        assert "hydroxychloroquine" in treats_edges

    def test_target_edges_exist(self, sample_graph):
        """Verify drug -> target edges exist."""
        targets = set()
        for u, v, data in sample_graph.edges(data=True):
            if data.get("type") == "TARGETS":
                targets.add((u, v))
        assert ("belimumab", "BAFF") in targets
        assert ("anifrolumab", "IFNAR1") in targets
        assert ("baricitinib", "JAK1") in targets

    def test_participates_in_edges_exist(self, sample_graph):
        """Verify gene -> pathway edges exist."""
        edges = set()
        for u, v, data in sample_graph.edges(data=True):
            if data.get("type") == "PARTICIPATES_IN":
                edges.add((u, v))
        assert ("IRF5", "type1-ifn") in edges
        assert ("BTK", "bcell-signaling") in edges
        assert ("TNFAIP3", "nfkb") in edges

    def test_drives_edges_exist(self, sample_graph):
        """Verify pathway -> disease edges exist."""
        edges = set()
        for u, v, data in sample_graph.edges(data=True):
            if data.get("type") == "DRIVES" and v == "Lupus (SLE)":
                edges.add(u)
        assert "type1-ifn" in edges
        assert "bcell-signaling" in edges
        assert "jak-stat" in edges
        assert "tlr-sensing" in edges
        assert "nfkb" in edges
        assert "complement" in edges
        assert "tcell-costim" in edges

    def test_associated_with_edges_exist(self, sample_graph):
        """Verify gene -> disease association edges exist."""
        edges = set()
        for u, v, data in sample_graph.edges(data=True):
            if data.get("type") == "ASSOCIATED_WITH" and v == "Lupus (SLE)":
                edges.add(u)
        expected = {"HLA-DRB1", "IRF5", "STAT4", "ITGAM", "TNFAIP3"}
        assert expected.issubset(edges)

    def test_disease_node_is_isolated_target(self, sample_graph):
        """Disease node should not have outgoing edges (it's the ultimate target)."""
        out_edges = list(sample_graph.out_edges("Lupus (SLE)"))
        assert len(out_edges) == 0


class TestExportForWeb:
    """Tests for export_for_web()."""

    @pytest.fixture
    def web_export(self, sample_graph, tmp_path):
        from med_research.pipeline.knowledge_graph.builder import export_for_web
        out_path = tmp_path / "graph_data.json"
        export_for_web(sample_graph, str(out_path))
        return json.loads(out_path.read_text(encoding="utf-8"))

    def test_export_has_elements_key(self, web_export):
        assert "elements" in web_export

    def test_elements_are_list(self, web_export):
        assert isinstance(web_export["elements"], list)

    def test_all_elements_have_data_key(self, web_export):
        for el in web_export["elements"]:
            assert "data" in el
            assert "id" in el["data"]

    def test_nodes_have_type(self, web_export):
        nodes = [e for e in web_export["elements"] if "source" not in e["data"]]
        for node in nodes:
            assert "type" in node["data"]

    def test_edges_have_source_target(self, web_export):
        edges = [e for e in web_export["elements"] if "source" in e["data"]]
        for edge in edges:
            assert "source" in edge["data"]
            assert "target" in edge["data"]
            assert "type" in edge["data"]

    def test_node_edge_counts_match(self, web_export, sample_graph):
        nodes = [e for e in web_export["elements"] if "source" not in e["data"]]
        edges = [e for e in web_export["elements"] if "source" in e["data"]]
        assert len(nodes) == sample_graph.number_of_nodes()
        assert len(edges) == sample_graph.number_of_edges()

    def test_exported_ids_are_unique(self, web_export):
        all_ids = [e["data"]["id"] for e in web_export["elements"]]
        assert len(all_ids) == len(set(all_ids))


class TestAnalyzeGraph:
    """Smoke test for analyze_graph() — just ensure no exceptions."""

    def test_analyze_does_not_crash(self, sample_graph, capsys):
        from med_research.pipeline.knowledge_graph.builder import analyze_graph
        analyze_graph(sample_graph)
        captured = capsys.readouterr()
        assert "KNOWLEDGE GRAPH ANALYSIS" in captured.out
        assert "DRUG" in captured.out
        assert "DRUG REPURPOSING INSIGHTS" in captured.out
        assert "Analysis complete" in captured.out
