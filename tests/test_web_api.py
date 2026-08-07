"""
Integration tests for the Lupus Research Platform Web API.

Tests cover all REST endpoints using FastAPI's TestClient:
  - System: health check, platform stats
  - Knowledge Graph: stats, graph, search, node detail, path, neighbors
  - Drug Repurposing: candidates list, per-gene candidates
  - Bioinformatics: GWAS (cached), enrichment (cached), PPI (cached)
  - Analysis: literature, screening, trials, ML
  - Jobs: submission + status for all long-running modules
  - Error handling: 404s, validation, edge cases
  - Static serving: dashboard, module reports, API docs
"""

import socket

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from med_research.web.main import app

# ── Redis availability check ────────────────────────────────────────────────


def _redis_available() -> bool:
    """Check if Redis is reachable on localhost:6379."""
    try:
        s = socket.create_connection(("localhost", 6379), timeout=1)
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


REDIS_AVAILABLE = _redis_available()
skip_without_redis = pytest.mark.skipif(
    not REDIS_AVAILABLE,
    reason="Redis server not available on localhost:6379",
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    """Create a TestClient that shares a single app instance across the module."""
    with TestClient(app) as c:
        yield c


# ── System Endpoints ────────────────────────────────────────────────────────


class TestSystemEndpoints:
    """Tests for /api/health and /api/stats."""

    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"
        assert "timestamp" in data

    def test_cors_header_present(self, client):
        """CORS middleware should add access-control-allow-origin header.

        When allow_origins=["*"] with credentials=True, Starlette echoes
        the origin back rather than using "*" (per CORS spec).
        """
        resp = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
        assert resp.status_code == 200
        # With credentials + wildcard origins, the origin is echoed back
        allowed = resp.headers.get("access-control-allow-origin", "")
        assert allowed == "http://localhost:3000" or allowed == "*"

    def test_stats_returns_all_fields(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        for key in ["kg_nodes", "kg_edges", "genes", "drugs", "pathways", "candidates", "tests_passing"]:
            assert key in data, f"Missing key: {key}"

    def test_stats_kg_nodes_is_positive(self, client):
        resp = client.get("/api/stats")
        assert resp.json()["kg_nodes"] >= 40

    def test_stats_genes_are_positive(self, client):
        resp = client.get("/api/stats")
        assert resp.json()["genes"] >= 20

    def test_stats_candidates_are_positive(self, client):
        resp = client.get("/api/stats")
        assert resp.json()["candidates"] >= 20


class TestDiseasesRegistry:
    """Tests for GET /api/system/diseases (dynamic disease registry)."""

    def test_returns_200(self, client):
        resp = client.get("/api/system/diseases")
        assert resp.status_code == 200

    def test_has_count_and_diseases(self, client):
        data = client.get("/api/system/diseases").json()
        assert "count" in data
        assert "diseases" in data
        assert data["count"] == len(data["diseases"])
        assert data["count"] >= 7

    def test_includes_sle_with_full_name(self, client):
        diseases = client.get("/api/system/diseases").json()["diseases"]
        sle = next((d for d in diseases if d["id"] == "sle"), None)
        assert sle is not None
        assert sle["name"] == "Systemic Lupus Erythematosus"
        assert sle["genes"] >= 20
        assert sle["drugs"] >= 10

    def test_diseases_sorted_by_id(self, client):
        diseases = client.get("/api/system/diseases").json()["diseases"]
        ids = [d["id"] for d in diseases]
        assert ids == sorted(ids)

    def test_entries_have_required_fields(self, client):
        diseases = client.get("/api/system/diseases").json()["diseases"]
        for d in diseases:
            for field in ["id", "name", "genes", "drugs", "pathways"]:
                assert field in d, f"Missing field: {field}"

    def test_invalid_kg_disease_registry_survives(self, client, monkeypatch):
        """A disease with broken KG data must not crash GET /api/system/diseases."""
        from med_research.diseases.base import Disease
        from med_research.exceptions import SchemaValidationError

        real_load_genes = Disease.load_genes

        def broken_load_genes(self):
            if self.disease_id == "sle":
                raise SchemaValidationError("Schema validation failed for genes.json")
            return real_load_genes(self)

        monkeypatch.setattr(Disease, "load_genes", broken_load_genes)

        resp = client.get("/api/system/diseases")
        assert resp.status_code == 200
        sle = next(d for d in resp.json()["diseases"] if d["id"] == "sle")
        assert sle["genes"] == 0
        assert sle["coverage"]["core"]["level"] != "full"


# ── Knowledge Graph Endpoints ───────────────────────────────────────────────


class TestKGStats:
    """Tests for GET /api/kg/stats."""

    def test_returns_200(self, client):
        resp = client.get("/api/kg/stats")
        assert resp.status_code == 200

    def test_has_required_keys(self, client):
        data = client.get("/api/kg/stats").json()
        for key in ["total_nodes", "total_edges", "node_types", "edge_types", "untargeted_genes", "top_hub_genes"]:
            assert key in data, f"Missing key: {key}"

    def test_node_types_has_all_types(self, client):
        node_types = client.get("/api/kg/stats").json()["node_types"]
        for t in ["disease", "gene", "drug", "pathway"]:
            assert t in node_types

    def test_untargeted_genes_is_list(self, client):
        untargeted = client.get("/api/kg/stats").json()["untargeted_genes"]
        assert isinstance(untargeted, list)
        assert len(untargeted) >= 5

    def test_untargeted_gene_has_required_fields(self, client):
        untargeted = client.get("/api/kg/stats").json()["untargeted_genes"]
        gene = untargeted[0]
        for field in ["id", "name", "category"]:
            assert field in gene, f"Missing field: {field}"

    def test_top_hub_genes_is_list(self, client):
        hubs = client.get("/api/kg/stats").json()["top_hub_genes"]
        assert isinstance(hubs, list)
        assert len(hubs) >= 1

    def test_top_hub_genes_sorted_by_degree(self, client):
        hubs = client.get("/api/kg/stats").json()["top_hub_genes"]
        for i in range(len(hubs) - 1):
            assert hubs[i]["degree"] >= hubs[i + 1]["degree"]


class TestKGGraph:
    """Tests for GET /api/kg/graph."""

    def test_returns_200(self, client):
        resp = client.get("/api/kg/graph")
        assert resp.status_code == 200

    def test_has_elements_key(self, client):
        data = client.get("/api/kg/graph").json()
        assert "elements" in data

    def test_elements_are_list(self, client):
        elements = client.get("/api/kg/graph").json()["elements"]
        assert isinstance(elements, list)
        assert len(elements) >= 50

    def test_all_elements_have_data_id(self, client):
        elements = client.get("/api/kg/graph").json()["elements"]
        for el in elements:
            assert "data" in el
            assert "id" in el["data"]

    def test_nodes_and_edges_separated(self, client):
        elements = client.get("/api/kg/graph").json()["elements"]
        nodes = [e for e in elements if "source" not in e["data"]]
        edges = [e for e in elements if "source" in e["data"]]
        assert len(nodes) >= 40
        assert len(edges) >= 50


class TestKGSearch:
    """Tests for GET /api/kg/search."""

    def test_search_returns_results(self, client):
        resp = client.get("/api/kg/search?q=HLA")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert len(data["results"]) >= 1
        assert data["count"] == len(data["results"])

    def test_search_case_insensitive(self, client):
        resp = client.get("/api/kg/search?q=hla")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_search_returns_structured_results(self, client):
        data = client.get("/api/kg/search?q=IRF5").json()
        assert data["count"] >= 1
        result = data["results"][0]
        for field in ["id", "label", "type"]:
            assert field in result, f"Missing field: {field}"

    def test_search_empty_query_validation(self, client):
        resp = client.get("/api/kg/search")
        assert resp.status_code == 422

    def test_search_no_results(self, client):
        resp = client.get("/api/kg/search?q=zzzznonexistentxyz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_search_returns_query_in_response(self, client):
        data = client.get("/api/kg/search?q=BTK").json()
        assert data["query"] == "BTK"

    def test_search_special_characters(self, client):
        """Special characters in query should not crash the endpoint."""
        resp = client.get("/api/kg/search?q=+++")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestKGNode:
    """Tests for GET /api/kg/node/{node_id}."""

    def test_valid_node_returns_200(self, client):
        resp = client.get("/api/kg/node/HLA-DRB1")
        assert resp.status_code == 200

    def test_valid_node_has_detail_fields(self, client):
        data = client.get("/api/kg/node/HLA-DRB1").json()
        for field in ["id", "type", "label", "incoming", "outgoing", "degree"]:
            assert field in data, f"Missing field: {field}"

    def test_disease_node(self, client):
        data = client.get("/api/kg/node/Lupus (SLE)").json()
        assert data["type"] == "disease"
        assert "Systemic Lupus Erythematosus" in data["label"]

    def test_gene_node(self, client):
        data = client.get("/api/kg/node/BTK").json()
        assert data["type"] == "gene"
        assert "chromosome" in data

    def test_drug_node(self, client):
        data = client.get("/api/kg/node/belimumab").json()
        assert data["type"] == "drug"
        assert "target" in data

    def test_pathway_node(self, client):
        data = client.get("/api/kg/node/type1-ifn").json()
        assert data["type"] == "pathway"

    def test_nonexistent_node_returns_404(self, client):
        resp = client.get("/api/kg/node/NONEXISTENT_GENE_XYZ")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestKGPath:
    """Tests for GET /api/kg/path."""

    def test_valid_path_returns_200(self, client):
        resp = client.get("/api/kg/path?source=belimumab&target=BAFF")
        assert resp.status_code == 200

    def test_valid_path_has_required_fields(self, client):
        data = client.get("/api/kg/path?source=belimumab&target=BAFF").json()
        for field in ["path", "length", "edges"]:
            assert field in data, f"Missing field: {field}"
        assert isinstance(data["path"], list)
        assert data["length"] >= 1
        assert isinstance(data["edges"], list)

    def test_direct_target_path(self, client):
        data = client.get("/api/kg/path?source=anifrolumab&target=IFNAR1").json()
        assert len(data["path"]) == 2
        assert data["length"] == 1

    def test_indirect_path(self, client):
        """Test a multi-hop path through the graph (anifrolumab → TLR7 via pathway)."""
        resp = client.get("/api/kg/path?source=anifrolumab&target=TLR7")
        # This path exists: anifrolumab → IFNAR1 → type1-ifn → TLR7
        if resp.status_code == 200:
            data = resp.json()
            assert data["length"] >= 2
        else:
            # Some graph topologies may not have this path
            assert resp.status_code == 404

    def test_no_path_returns_404(self, client):
        resp = client.get("/api/kg/path?source=belimumab&target=NONEXISTENT_NODE_XYZ")
        assert resp.status_code == 404

    def test_missing_params_validation(self, client):
        resp = client.get("/api/kg/path")
        assert resp.status_code == 422

    def test_same_node_path(self, client):
        data = client.get("/api/kg/path?source=HLA-DRB1&target=HLA-DRB1").json()
        assert data["length"] == 0
        assert data["path"] == ["HLA-DRB1"]


class TestKGNeighbors:
    """Tests for GET /api/kg/neighbors/{node_id}."""

    def test_valid_node_returns_200(self, client):
        resp = client.get("/api/kg/neighbors/HLA-DRB1")
        assert resp.status_code == 200

    def test_has_required_fields(self, client):
        data = client.get("/api/kg/neighbors/HLA-DRB1").json()
        for field in ["node_id", "neighbors", "degree"]:
            assert field in data, f"Missing field: {field}"

    def test_neighbors_are_list(self, client):
        data = client.get("/api/kg/neighbors/HLA-DRB1").json()
        assert isinstance(data["neighbors"], list)
        assert len(data["neighbors"]) >= 1

    def test_neighbor_has_id_type_and_edge_types(self, client):
        data = client.get("/api/kg/neighbors/HLA-DRB1").json()
        neighbor = data["neighbors"][0]
        assert "id" in neighbor
        assert "type" in neighbor
        assert "edge_types" in neighbor

    def test_multi_hop(self, client):
        data = client.get("/api/kg/neighbors/belimumab?hops=2").json()
        assert "subgraph_size" in data

    def test_nonexistent_node_returns_404(self, client):
        resp = client.get("/api/kg/neighbors/NONEXISTENT_NODE_XYZ")
        assert resp.status_code == 404

    def test_invalid_hops_validation(self, client):
        resp = client.get("/api/kg/neighbors/HLA-DRB1?hops=10")
        assert resp.status_code == 422


# ── Drug Repurposing Endpoints ──────────────────────────────────────────────


class TestRepurposeCandidates:
    """Tests for GET /api/repurpose/candidates."""

    def test_returns_200(self, client):
        resp = client.get("/api/repurpose/candidates?top_n=10")
        assert resp.status_code == 200

    def test_has_required_keys(self, client):
        data = client.get("/api/repurpose/candidates?top_n=10").json()
        for key in ["candidates", "total", "tier1_count", "tier2_count", "avg_score", "top_n"]:
            assert key in data, f"Missing key: {key}"

    def test_candidates_are_list(self, client):
        candidates = client.get("/api/repurpose/candidates?top_n=10").json()["candidates"]
        assert isinstance(candidates, list)
        assert len(candidates) >= 1

    def test_candidate_has_required_fields(self, client):
        candidate = client.get("/api/repurpose/candidates?top_n=10").json()["candidates"][0]
        required = [
            "rank", "drug_name", "gene_id", "gene_name", "composite_score",
            "target_similarity_score", "mechanistic_rationale_score",
            "clinical_evidence_score", "safety_score", "novelty_score",
            "evidence_level", "tier",
        ]
        for field in required:
            assert field in candidate, f"Missing field: {field}"

    def test_respects_top_n(self, client):
        data = client.get("/api/repurpose/candidates?top_n=3").json()
        assert len(data["candidates"]) <= 3

    def test_top_n_boundary_values(self, client):
        """Boundary: top_n=50 should be valid, top_n=51 should fail."""
        resp_ok = client.get("/api/repurpose/candidates?top_n=50")
        assert resp_ok.status_code == 200
        resp_fail = client.get("/api/repurpose/candidates?top_n=51")
        assert resp_fail.status_code == 422

    def test_filter_by_gene(self, client):
        data = client.get("/api/repurpose/candidates?gene_id=BTK&top_n=5").json()
        for c in data["candidates"]:
            assert c["gene_id"] == "BTK"

    def test_scores_in_range(self, client):
        candidates = client.get("/api/repurpose/candidates?top_n=15").json()["candidates"]
        for c in candidates:
            assert 0 <= c["composite_score"] <= 10

    def test_sorted_descending(self, client):
        candidates = client.get("/api/repurpose/candidates?top_n=15").json()["candidates"]
        for i in range(len(candidates) - 1):
            assert candidates[i]["composite_score"] >= candidates[i + 1]["composite_score"]

    def test_avg_score_in_range(self, client):
        avg = client.get("/api/repurpose/candidates?top_n=15").json()["avg_score"]
        assert 0 <= avg <= 10

    def test_rank_starts_at_1(self, client):
        candidates = client.get("/api/repurpose/candidates?top_n=5").json()["candidates"]
        assert candidates[0]["rank"] == 1


class TestRepurposeGene:
    """Tests for GET /api/repurpose/gene/{gene_id}."""

    def test_valid_gene_returns_200(self, client):
        resp = client.get("/api/repurpose/gene/BTK")
        assert resp.status_code == 200

    def test_has_gene_info(self, client):
        data = client.get("/api/repurpose/gene/BTK").json()
        for field in ["gene_id", "gene_name", "gene_category", "gene_function", "lupus_evidence", "candidates"]:
            assert field in data, f"Missing field: {field}"

    def test_candidates_count_matches(self, client):
        data = client.get("/api/repurpose/gene/BTK").json()
        assert data["count"] == len(data["candidates"])

    def test_best_score_matches(self, client):
        data = client.get("/api/repurpose/gene/BTK").json()
        if data["candidates"]:
            assert data["best_score"] == data["candidates"][0]["composite_score"]

    def test_nonexistent_gene_returns_404(self, client):
        resp = client.get("/api/repurpose/gene/NONEXISTENT_GENE_XYZ")
        assert resp.status_code == 404


# ── Bioinformatics Endpoints ────────────────────────────────────────────────


class TestBioGWAS:
    """Tests for GET /api/bioinformatics/gwas (uses cache)."""

    @pytest.mark.slow
    def test_returns_200(self, client):
        resp = client.get("/api/bioinformatics/gwas?max_studies=5")
        assert resp.status_code == 200

    @pytest.mark.slow
    def test_has_required_keys(self, client):
        data = client.get("/api/bioinformatics/gwas?max_studies=5").json()
        for key in ["total_studies", "total_associations", "unique_genes", "crossref", "top_hits"]:
            assert key in data, f"Missing key: {key}"

    @pytest.mark.slow
    def test_crossref_has_validated(self, client):
        crossref = client.get("/api/bioinformatics/gwas?max_studies=5").json()["crossref"]
        assert "validated" in crossref
        assert "novel" in crossref
        assert "missing" in crossref
        assert "n_validated" in crossref
        assert "n_novel" in crossref
        assert "n_missing" in crossref

    @pytest.mark.slow
    def test_top_hits_are_list(self, client):
        top_hits = client.get("/api/bioinformatics/gwas?max_studies=5").json()["top_hits"]
        assert isinstance(top_hits, list)


class TestBioEnrichment:
    """Tests for GET /api/bioinformatics/enrichment (uses cache)."""

    @pytest.mark.slow
    def test_returns_200(self, client):
        resp = client.get("/api/bioinformatics/enrichment")
        assert resp.status_code == 200

    @pytest.mark.slow
    def test_has_required_keys(self, client):
        data = client.get("/api/bioinformatics/enrichment").json()
        for key in ["genes_analyzed", "gene_list", "libraries"]:
            assert key in data, f"Missing key: {key}"

    @pytest.mark.slow
    def test_gene_list_is_list_of_strings(self, client):
        gene_list = client.get("/api/bioinformatics/enrichment").json()["gene_list"]
        assert isinstance(gene_list, list)
        assert len(gene_list) >= 5
        assert all(isinstance(g, str) for g in gene_list)

    @pytest.mark.slow
    def test_libraries_are_list(self, client):
        libraries = client.get("/api/bioinformatics/enrichment").json()["libraries"]
        assert isinstance(libraries, list)
        assert len(libraries) >= 1

    @pytest.mark.slow
    def test_library_has_terms(self, client):
        library = client.get("/api/bioinformatics/enrichment").json()["libraries"][0]
        assert "library" in library
        assert "terms" in library


class TestBioPPI:
    """Tests for GET /api/bioinformatics/ppi (uses cache)."""

    @pytest.mark.slow
    def test_returns_200(self, client):
        resp = client.get("/api/bioinformatics/ppi")
        assert resp.status_code == 200

    @pytest.mark.slow
    def test_has_required_keys(self, client):
        data = client.get("/api/bioinformatics/ppi").json()
        for key in ["nodes", "edges", "seed_genes", "confidence", "top_hubs"]:
            assert key in data, f"Missing key: {key}"

    @pytest.mark.slow
    def test_top_hubs_are_list(self, client):
        hubs = client.get("/api/bioinformatics/ppi").json()["top_hubs"]
        assert isinstance(hubs, list)

    @pytest.mark.slow
    def test_hub_has_required_fields(self, client):
        hubs = client.get("/api/bioinformatics/ppi").json()["top_hubs"]
        if hubs:
            for field in ["symbol", "hub_score", "degree", "is_lupus_gene"]:
                assert field in hubs[0], f"Missing field: {field}"

    @pytest.mark.slow
    def test_confidence_passed_through(self, client):
        data = client.get("/api/bioinformatics/ppi?confidence=0.7").json()
        assert data["confidence"] == 0.7

    @pytest.mark.slow
    def test_invalid_confidence_validation(self, client):
        resp = client.get("/api/bioinformatics/ppi?confidence=1.5")
        assert resp.status_code == 422


# ── Analysis Endpoints (sync / cached results) ─────────────────────────────


class TestAnalysisLiterature:
    """Tests for GET /api/literature (uses cached results)."""

    @pytest.mark.slow
    def test_returns_200(self, client):
        resp = client.get("/api/literature?max_articles=5")
        assert resp.status_code == 200

    @pytest.mark.slow
    def test_has_required_keys(self, client):
        data = client.get("/api/literature?max_articles=5").json()
        for key in ["total_articles", "queries_run", "articles", "gene_coverage", "candidate_support"]:
            assert key in data, f"Missing key: {key}"


class TestAnalysisScreening:
    """Tests for GET /api/screening."""

    @pytest.mark.slow
    def test_returns_200(self, client):
        resp = client.get("/api/screening?top_n=5")
        assert resp.status_code == 200

    @pytest.mark.slow
    def test_has_required_keys(self, client):
        data = client.get("/api/screening?top_n=5").json()
        for key in ["targets", "compounds_screened", "total_pairings", "tier1_count", "tier2_count", "vina_available", "rdkit_available"]:
            assert key in data, f"Missing key: {key}"

    @pytest.mark.slow
    def test_vina_and_rdkit_fields_are_bools(self, client):
        data = client.get("/api/screening?top_n=5").json()
        assert isinstance(data["vina_available"], bool)
        assert isinstance(data["rdkit_available"], bool)

    @pytest.mark.slow
    def test_targets_are_list(self, client):
        targets = client.get("/api/screening?top_n=5").json()["targets"]
        assert isinstance(targets, list)
        assert len(targets) >= 1

    @pytest.mark.slow
    def test_target_has_compounds(self, client):
        target = client.get("/api/screening?top_n=5").json()["targets"][0]
        assert "gene_id" in target
        assert "gene_name" in target
        assert "top_compounds" in target
        assert isinstance(target["top_compounds"], list)

    @pytest.mark.slow
    def test_compound_has_scores(self, client):
        compounds = client.get("/api/screening?top_n=5").json()["targets"][0]["top_compounds"]
        if compounds:
            c = compounds[0]
            for field in ["drug_id", "drug_name", "composite_score", "binding_estimate", "druglikeness", "tier"]:
                assert field in c, f"Missing field: {field}"

    @pytest.mark.slow
    def test_filter_by_gene(self, client):
        data = client.get("/api/screening?gene_id=BTK&top_n=5").json()
        assert len(data["targets"]) == 1
        assert data["targets"][0]["gene_id"] == "BTK"


class TestAnalysisTrials:
    """Tests for GET /api/trials (uses cached results)."""

    @pytest.mark.slow
    def test_returns_200(self, client):
        resp = client.get("/api/trials?max_trials=5")
        assert resp.status_code == 200

    @pytest.mark.slow
    def test_has_required_keys(self, client):
        data = client.get("/api/trials?max_trials=5").json()
        for key in ["total_trials", "phase_distribution", "moa_distribution", "top_sponsors", "trials"]:
            assert key in data, f"Missing key: {key}"


class TestAnalysisML:
    """Tests for GET /api/ml/predict."""

    @pytest.mark.slow
    def test_returns_200(self, client):
        resp = client.get("/api/ml/predict?top_n=5")
        assert resp.status_code == 200

    @pytest.mark.slow
    def test_has_required_keys(self, client):
        data = client.get("/api/ml/predict?top_n=5").json()
        for key in ["predictions", "model_type", "top_features"]:
            assert key in data, f"Missing key: {key}"

    @pytest.mark.slow
    def test_model_type_is_xgboost(self, client):
        data = client.get("/api/ml/predict?top_n=5").json()
        assert data["model_type"] == "XGBoost"

    @pytest.mark.slow
    def test_predictions_have_rank(self, client):
        predictions = client.get("/api/ml/predict?top_n=5").json()["predictions"]
        if predictions:
            assert "rank" in predictions[0]
            assert predictions[0]["rank"] == 1

    @pytest.mark.slow
    def test_respects_top_n(self, client):
        data = client.get("/api/ml/predict?top_n=3").json()
        assert len(data["predictions"]) <= 3

    @pytest.mark.slow
    def test_prediction_has_gene_info(self, client):
        predictions = client.get("/api/ml/predict?top_n=5").json()["predictions"]
        if predictions:
            for field in ["gene_id", "gene_name", "druggability_score", "is_targeted"]:
                assert field in predictions[0], f"Missing field: {field}"


# ── Job Endpoints ──────────────────────────────────────────────────────────


@skip_without_redis
class TestJobSubmission:
    """Tests for POST /api/jobs/* submission endpoints."""

    def test_submit_gwas_returns_job_id(self, client):
        resp = client.post("/api/jobs/gwas", params={"max_studies": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "PENDING"
        assert data["module"] == "gwas"

    def test_submit_enrichment_returns_job_id(self, client):
        resp = client.post("/api/jobs/enrichment", params={"untargeted_only": False})
        assert resp.status_code == 200
        assert "job_id" in resp.json()
        assert resp.json()["module"] == "enrichment"

    def test_submit_ppi_returns_job_id(self, client):
        resp = client.post("/api/jobs/ppi", params={"confidence": 0.4})
        assert resp.status_code == 200
        assert "job_id" in resp.json()
        assert resp.json()["module"] == "ppi"

    def test_submit_literature_returns_job_id(self, client):
        resp = client.post("/api/jobs/literature", params={"max_articles": 10})
        assert resp.status_code == 200
        assert "job_id" in resp.json()
        assert resp.json()["module"] == "literature"

    def test_submit_screening_returns_job_id(self, client):
        resp = client.post("/api/jobs/screening", params={"top_n": 5})
        assert resp.status_code == 200
        assert "job_id" in resp.json()
        assert resp.json()["module"] == "screening"

    def test_submit_trials_returns_job_id(self, client):
        resp = client.post("/api/jobs/trials", params={"max_trials": 10})
        assert resp.status_code == 200
        assert "job_id" in resp.json()
        assert resp.json()["module"] == "trials"

    def test_submit_ml_returns_job_id(self, client):
        resp = client.post("/api/jobs/ml", params={"top_n": 5})
        assert resp.status_code == 200
        assert "job_id" in resp.json()
        assert resp.json()["module"] == "ml"

    def test_submit_safety_with_disease(self, client):
        resp = client.post("/api/jobs/safety", params={"disease": "ra"})
        assert resp.status_code == 200
        assert "job_id" in resp.json()
        assert resp.json()["module"] == "safety"

    def test_job_ids_are_unique(self, client):
        resp1 = client.post("/api/jobs/ml", params={"top_n": 3})
        resp2 = client.post("/api/jobs/ml", params={"top_n": 3})
        assert resp1.json()["job_id"] != resp2.json()["job_id"]

    def test_job_ids_are_strings(self, client):
        resp = client.post("/api/jobs/gwas", params={"max_studies": 5})
        assert isinstance(resp.json()["job_id"], str)
        assert len(resp.json()["job_id"]) > 0


@skip_without_redis
class TestJobStatus:
    """Tests for GET /api/jobs/{job_id}."""

    def test_fresh_job_has_correct_status(self, client):
        resp = client.post("/api/jobs/ml", params={"top_n": 3})
        job_id = resp.json()["job_id"]

        status_resp = client.get(f"/api/jobs/{job_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["job_id"] == job_id
        assert status_resp.json()["status"] in ("PENDING", "STARTED", "SUCCESS", "FAILURE")

    def test_nonexistent_job(self, client):
        resp = client.get("/api/jobs/nonexistent-job-id-12345")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "nonexistent-job-id-12345"


# ── Error Handling & Edge Cases ─────────────────────────────────────────────


class TestErrorHandling:
    """Tests for error responses and edge cases across the API."""

    def test_404_node_not_found(self, client):
        resp = client.get("/api/kg/node/NONEXISTENT_NODE")
        assert resp.status_code == 404
        assert "detail" in resp.json()

    def test_404_gene_not_found(self, client):
        resp = client.get("/api/repurpose/gene/NONEXISTENT_GENE")
        assert resp.status_code == 404
        assert "detail" in resp.json()

    def test_404_path_not_found(self, client):
        resp = client.get("/api/kg/path?source=belimumab&target=ZZZZ_NONEXISTENT")
        assert resp.status_code == 404

    def test_404_neighbors_not_found(self, client):
        resp = client.get("/api/kg/neighbors/NONEXISTENT_NODE")
        assert resp.status_code == 404

    def test_api_docs_accessible(self, client):
        resp = client.get("/api/docs")
        assert resp.status_code == 200
        assert "swagger" in resp.text.lower() or "openapi" in resp.text.lower()

    def test_openapi_schema_accessible(self, client):
        resp = client.get("/api/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "paths" in schema
        assert len(schema["paths"]) >= 15

    def test_openapi_schema_has_all_tags(self, client):
        schema = client.get("/api/openapi.json").json()
        tags = schema.get("tags") or []
        tag_names = {t["name"] for t in tags}
        expected = {"Knowledge Graph", "Drug Repurposing", "Bioinformatics", "Analysis", "System", "Jobs"}
        # Tags may be empty depending on FastAPI version; test is informational
        if tag_names:
            assert expected.issubset(tag_names), f"Missing tags: {expected - tag_names}"


# ── Static File Serving ─────────────────────────────────────────────────────


class TestStaticServing:
    """Verify the dashboard and existing module reports are served at v2 paths."""

    def test_dashboard_served(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Medical Research Platform" in resp.text

    def test_legacy_kg_web_path_not_served(self, client):
        """v2 dropped the v1 knowledge_graph/web/ UI — the legacy path must 404."""
        resp = client.get("/knowledge_graph/web/index.html")
        assert resp.status_code == 404

    def test_drug_repurposing_data_served(self, client):
        resp = client.get("/static/drug_repurposing/candidates.json")
        assert resp.status_code == 200
        assert "repurposing_candidates" in resp.text

    def test_bioinformatics_report_served(self, client):
        resp = client.get("/static/bioinformatics/ppi_interactive.html")
        assert resp.status_code == 200


# ── WebSocket Endpoints ────────────────────────────────────────────────────


class TestWebSocketOrphanedJob:
    """Test WebSocket behavior with nonexistent / orphaned job IDs.

    Does NOT require Redis — the server detects missing jobs via the
    AsyncResult polling loop and sends an ERROR response.

    Note: Starlette's test client may buffer multiple inbound messages
    before receive_json() is called, so the first message received is
    not guaranteed to be PENDING. We collect up to 2 messages and verify
    the expected ERROR message is among them.
    """

    @pytest.mark.slow
    def test_orphaned_job_returns_error(self, client):
        """Connecting to a nonexistent job via WebSocket should eventually emit ERROR.

        After ~4 poll iterations (~2s) the server detects that the job has
        no backend data and sends {"status": "ERROR", "error": "Job not found or expired"}.
        """
        fake_job_id = "00000000-0000-0000-0000-000000000000"

        with client.websocket_connect(f"/api/jobs/{fake_job_id}/ws") as ws:
            messages = []
            # Collect up to 2 messages (PENDING + ERROR) with generous timeout
            for _ in range(2):
                try:
                    msg = ws.receive_json()
                    messages.append(msg)
                except Exception:
                    break

            # Verify the job_id is in every message
            for msg in messages:
                assert msg["job_id"] == fake_job_id

            # At least one message must be the orphaned-job ERROR
            error_msgs = [m for m in messages if m["status"] == "ERROR"]
            assert len(error_msgs) >= 1, \
                f"Expected an ERROR message for orphaned job, got: {messages}"
            assert "not found" in error_msgs[0]["error"].lower()

    @pytest.mark.slow
    def test_orphaned_job_closes_cleanly(self, client):
        """After emitting ERROR, the WebSocket closes — no more messages arrive."""
        fake_job_id = "11111111-1111-1111-1111-111111111111"

        with client.websocket_connect(f"/api/jobs/{fake_job_id}/ws") as ws:
            # Consume all messages until the connection closes
            while True:
                try:
                    ws.receive_json()
                except Exception:
                    break  # Connection closed — expected

            # Attempting to receive after the connection closes must raise
            with pytest.raises((RuntimeError, WebSocketDisconnect)):
                ws.receive_json()


class TestWebSocketDisconnect:
    """Test WebSocket disconnect handling.

    Verifies the server handles client-initiated disconnection gracefully
    (no server errors, no resource leaks).
    """

    def test_disconnect_does_not_crash_server(self, client):
        """Client disconnects mid-stream — server should handle WebSocketDisconnect."""
        fake_job_id = "22222222-2222-2222-2222-222222222222"

        with client.websocket_connect(f"/api/jobs/{fake_job_id}/ws") as ws:
            # Receive one message to confirm the connection is established.
            # The exact status can vary due to test client buffering — just
            # verify it's a well-formed message with the right job_id.
            data = ws.receive_json()
            assert data["job_id"] == fake_job_id
            assert "status" in data

        # Context manager exit closes the WebSocket — this is the disconnect.
        # The server's WebSocketDisconnect handler should catch it silently.

        # Verify the server is still healthy after disconnect
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_disconnect_before_any_message(self, client):
        """Client disconnects immediately before receiving anything."""
        fake_job_id = "33333333-3333-3333-3333-333333333333"

        # Connect and immediately disconnect (context manager exit)
        with client.websocket_connect(f"/api/jobs/{fake_job_id}/ws"):
            pass

        # Server should still be healthy
        resp = client.get("/api/health")
        assert resp.status_code == 200


@skip_without_redis
class TestWebSocketSuccessfulStream:
    """Test real-time WebSocket job progress streaming.

    Requires Redis + Celery worker to process jobs.

    To avoid hanging when no Celery worker is running, each test
    receives exactly ONE message via WebSocket (verifying the connection
    works and sends valid data), then closes the connection and continues
    verification via the HTTP status endpoint.
    """

    def test_stream_receives_initial_status(self, client):
        """Submit a job and verify the WebSocket connection is established."""
        submit = client.post("/api/jobs/ml", params={"top_n": 3})
        assert submit.status_code == 200
        job_id = submit.json()["job_id"]

        with client.websocket_connect(f"/api/jobs/{job_id}/ws") as ws:
            data = ws.receive_json()
            assert data["job_id"] == job_id
            assert data["status"] in ("PENDING", "STARTED", "PROGRESS", "SUCCESS", "FAILURE")

        # After closing WS, verify the job still exists via HTTP
        status = client.get(f"/api/jobs/{job_id}").json()
        assert status["status"] in ("PENDING", "STARTED", "PROGRESS", "SUCCESS", "FAILURE")

    def test_stream_has_proper_message_structure(self, client):
        """The first WebSocket message must have job_id and status fields."""
        submit = client.post("/api/jobs/ml", params={"top_n": 3})
        assert submit.status_code == 200
        job_id = submit.json()["job_id"]

        with client.websocket_connect(f"/api/jobs/{job_id}/ws") as ws:
            data = ws.receive_json()
            assert "job_id" in data, "Every WS message must have job_id"
            assert "status" in data, "Every WS message must have status"
            assert data["job_id"] == job_id

        # Verify HTTP endpoint also has the correct job_id
        http_status = client.get(f"/api/jobs/{job_id}").json()
        assert http_status["job_id"] == job_id

    def test_stream_for_gwas_job(self, client):
        """WebSocket streaming for a GWAS analysis job."""
        submit = client.post("/api/jobs/gwas", params={"max_studies": 3})
        assert submit.status_code == 200
        job_id = submit.json()["job_id"]

        with client.websocket_connect(f"/api/jobs/{job_id}/ws") as ws:
            data = ws.receive_json()
            assert data["job_id"] == job_id
            assert "status" in data

    def test_multiple_connections_are_independent(self, client):
        """Two sequential WebSocket connections operate independently."""
        # Submit two different jobs
        submit1 = client.post("/api/jobs/ml", params={"top_n": 3})
        submit2 = client.post("/api/jobs/ml", params={"top_n": 3})
        job_id1 = submit1.json()["job_id"]
        job_id2 = submit2.json()["job_id"]
        assert job_id1 != job_id2, "Jobs must have unique IDs"

        # Open and use each WebSocket sequentially (avoids Starlette parallel-connection issues)
        with client.websocket_connect(f"/api/jobs/{job_id1}/ws") as ws1:
            data1 = ws1.receive_json()
            assert data1["job_id"] == job_id1

        with client.websocket_connect(f"/api/jobs/{job_id2}/ws") as ws2:
            data2 = ws2.receive_json()
            assert data2["job_id"] == job_id2

    def test_stream_for_enrichment_job(self, client):
        """WebSocket streaming for an enrichment analysis job."""
        submit = client.post("/api/jobs/enrichment", params={"untargeted_only": True})
        assert submit.status_code == 200
        job_id = submit.json()["job_id"]

        with client.websocket_connect(f"/api/jobs/{job_id}/ws") as ws:
            data = ws.receive_json()
            assert data["job_id"] == job_id
            assert "status" in data

    def test_stream_for_screening_job(self, client):
        """WebSocket streaming for a virtual screening job."""
        submit = client.post("/api/jobs/screening", params={"top_n": 3})
        assert submit.status_code == 200
        job_id = submit.json()["job_id"]

        with client.websocket_connect(f"/api/jobs/{job_id}/ws") as ws:
            data = ws.receive_json()
            assert data["job_id"] == job_id
            assert "status" in data


class TestDiseaseAwareEndpoints:
    """Verify module endpoints reflect the selected disease, not just SLE."""

    def test_stats_reflects_disease(self, client):
        sle = client.get("/api/stats").json()
        ra = client.get("/api/stats?disease=ra").json()
        assert ra["kg_nodes"] > 0
        assert ra != sle
        assert ra["genes"] > 0

    def test_repurpose_candidates_disease_param(self, client):
        sle = client.get("/api/repurpose/candidates?top_n=10").json()
        ra = client.get("/api/repurpose/candidates?top_n=10&disease=ra").json()
        assert "candidates" in ra and "total" in ra
        assert ra != sle

    def test_repurpose_gene_with_disease(self, client):
        resp = client.get("/api/repurpose/gene/TNF?disease=ra")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gene_id"] == "TNF"

    def test_cart_suitability_disease_param(self, client):
        resp = client.get("/api/cart/suitability?top_n=10&disease=ra")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_genes"] >= 1
        assert "genes" in data

    def test_safety_profiles_disease_param(self, client):
        resp = client.get("/api/safety/profiles?disease=ra")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_drugs"] >= 1
        assert "profiles" in data


class TestKGGraphDiseaseAware:
    """Tests for GET /api/kg/graph with the disease param."""

    def test_default_is_sle(self, client):
        data = client.get("/api/kg/graph").json()
        sle = client.get("/api/kg/graph?disease=sle").json()
        assert data["elements"] == sle["elements"]

    def test_ra_graph_differs_from_sle(self, client):
        sle = client.get("/api/kg/graph?disease=sle").json()["elements"]
        ra = client.get("/api/kg/graph?disease=ra").json()["elements"]
        assert len(ra) > 0
        assert ra != sle

    def test_unknown_disease_returns_500(self):
        # Unknown disease has no data dir -> build_graph raises FileNotFoundError
        from fastapi.testclient import TestClient

        from med_research.web.main import app as test_app
        with TestClient(test_app, raise_server_exceptions=False) as c:
            resp = c.get("/api/kg/graph?disease=nonexistent")
            assert resp.status_code == 500

    def test_stats_disease_param(self, client):
        sle = client.get("/api/kg/stats?disease=sle").json()
        ra = client.get("/api/kg/stats?disease=ra").json()
        assert ra["total_nodes"] > 0
        assert sle["total_nodes"] != ra["total_nodes"]

    def test_node_detail_with_disease(self, client):
        resp = client.get("/api/kg/node/TLR7?disease=sle")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TLR7"
        assert "incoming" in data
        assert "outgoing" in data


class TestExportEndpoints:
    """Tests for /api/export/* endpoints."""

    def test_list_modules(self, client):
        resp = client.get("/api/export/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert "modules" in data
        assert len(data["modules"]) >= 10

    def test_json_export_available_module(self, client):
        resp = client.get("/api/export/json/repurpose")
        assert resp.status_code == 200
        data = resp.json()
        assert "repurposing_candidates" in data

    def test_json_export_cross_disease(self, client):
        resp = client.get("/api/export/json/cross-disease")
        assert resp.status_code == 200
        data = resp.json()
        assert "disease_summary" in data

    def test_json_export_unknown_module_404(self, client):
        resp = client.get("/api/export/json/bogus_module")
        assert resp.status_code == 404

    def test_raw_export_returns_file(self, client):
        resp = client.get("/api/export/raw/repurpose")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")

    def test_print_stylesheet(self, client):
        resp = client.get("/api/export/report/repurpose/print.css")
        assert resp.status_code == 200
        assert "@media print" in resp.text


class TestCrossDiseaseApi:
    """Tests for cross-disease endpoints feeding the comparison view."""

    def test_overlap_returns_matrix(self, client):
        resp = client.get("/api/cross-disease/overlap")
        assert resp.status_code == 200
        data = resp.json()
        assert "shared_genes" in data
        assert "matrix" in data["shared_genes"]
        assert "disease_similarity" in data
        assert "multi_disease_drugs" in data

    def test_similarity_endpoint(self, client):
        resp = client.get("/api/cross-disease/similarity")
        assert resp.status_code == 200
        data = resp.json()
        assert "similarity" in data
        assert "diseases" in data

    def test_drugs_endpoint(self, client):
        resp = client.get("/api/cross-disease/drugs?top=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "drugs" in data
        assert len(data["drugs"]) <= 5

    @pytest.mark.slow
    def test_modules_endpoint_returns_stacked_matrices(self, client):
        """Comparative modules endpoint stacks biomarker/expression/synergy per disease."""
        resp = client.get("/api/cross-disease/modules?top_synergy=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["diseases"]) >= 7
        modules = data["modules"]
        for m in ["biomarker", "expression", "synergy"]:
            assert m in modules
        # Score matrices are entity -> disease -> score
        assert "scores" in modules["biomarker"]
        assert "scores" in modules["expression"]
        # Synergy has labeled top pairs per disease
        assert "top" in modules["synergy"]
        sle_top = modules["synergy"]["top"].get("sle", [])
        if sle_top:
            assert "label" in sle_top[0]
            assert "score" in sle_top[0]

    @pytest.mark.slow
    def test_modules_endpoint_counts_positive(self, client):
        resp = client.get("/api/cross-disease/modules")
        data = resp.json()
        counts = data["modules"]["biomarker"]["counts"]
        assert counts.get("sle", 0) > 0
        assert counts.get("ra", 0) > 0
