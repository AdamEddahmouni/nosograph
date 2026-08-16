from __future__ import annotations

from fastapi.testclient import TestClient

from med_research.pipeline.knowledge_graph.network_analytics import build_multi_disease_network
from med_research.web.main import app

client = TestClient(app)


def test_build_multi_disease_network_basic():
    """Verify merged multi-disease graph structure, node types, and degree centrality."""
    net = build_multi_disease_network(["sle", "ra", "ms", "ibd"])

    assert "elements" in net
    assert "summary" in net
    nodes = net["elements"]["nodes"]
    edges = net["elements"]["edges"]

    assert len(nodes) > 0
    assert len(edges) > 0
    assert net["summary"]["disease_count"] == 4
    assert net["summary"]["total_nodes"] == len(nodes)

    # Check for disease nodes
    disease_nodes = [n for n in nodes if n["data"]["type"] == "disease"]
    assert len(disease_nodes) == 4

    # Check node attributes
    for n in nodes:
        d = n["data"]
        assert "id" in d
        assert "label" in d
        assert "type" in d
        assert "degree" in d
        assert "size" in d


def test_build_multi_disease_network_shared_only():
    """Verify shared-only filtering returns only disease nodes, shared hubs, and repurposing bridges."""
    net_all = build_multi_disease_network(["sle", "ra", "ms", "ibd"], include_shared_only=False)
    net_shared = build_multi_disease_network(["sle", "ra", "ms", "ibd"], include_shared_only=True)

    assert len(net_shared["elements"]["nodes"]) <= len(net_all["elements"]["nodes"])
    for n in net_shared["elements"]["nodes"]:
        d = n["data"]
        assert d["type"] == "disease" or d.get("is_shared_hub") is True or d.get("is_repurposing_bridge") is True


def test_api_multi_network_endpoint():
    """Verify /api/kg/multi-network returns 200 with valid Cytoscape JSON payload."""
    res = client.get("/api/kg/multi-network?diseases=sle,ra&shared_only=false")
    assert res.status_code == 200
    data = res.json()
    assert "elements" in data
    assert "summary" in data
    assert data["summary"]["disease_count"] == 2
