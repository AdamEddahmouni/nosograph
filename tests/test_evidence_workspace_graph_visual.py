from pathlib import Path

import pytest

from med_research.pipeline.evidence_workspace.schemas import Citation, Claim, GraphExplanation
from med_research.web.services.workspace_graph import build_workspace_graph

from .test_evidence_workspace_reviews import _dossier, _save

pytestmark = pytest.mark.unit


def _graph_dossier(run_id: str = "ew-graph"):
    dossier = _dossier(run_id, 82.0)
    dossier.claims.append(
        Claim(
            claim_id="claim-pathway",
            subject_id="pathway-tnf",
            subject_type="pathway",
            subject_name="TNF Signaling Pathway",
            relationship="participates_in",
            text="The candidate participates in TNF pathway biology.",
            evidence_ids=["pmid-1"],
            citations=[
                Citation(
                    source="pubmed",
                    native_id="pmid-1",
                    title="JAK intervention study",
                    url="https://pubmed.ncbi.nlm.nih.gov/123/",
                )
            ],
            confidence=0.75,
            extraction_method="rules",
        )
    )
    dossier.drug_rankings[0].supporting_claim_ids.append("claim-pathway")
    dossier.graph_explanations = [
        GraphExplanation(
            explanation_id="graph:tofacitinib",
            candidate_id="tofacitinib",
            status="found",
            path_node_ids=["tofacitinib", "pathway-tnf", "disease-sle"],
            path_labels=["Tofacitinib", "TNF Signaling Pathway", "Systemic lupus erythematosus"],
            relationship_labels=["MODULATES", "DRIVES"],
        )
    ]
    return dossier


def test_graph_projection_connects_candidates_claims_citations_pathways_and_reviews():
    dossier = _graph_dossier()
    review = {
        "candidate_id": "tofacitinib",
        "candidate_type": "drug",
        "candidate_name": "Tofacitinib",
        "decision": "pinned",
        "rationale": "Prioritize mechanistic follow-up",
        "notes": "Check safety next",
        "tags": ["priority"],
        "changed_my_mind": "New pathway evidence",
        "provenance_fingerprint": "fp-graph",
        "researcher_id": "alice",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    graph = build_workspace_graph(
        {"run_id": dossier.run_id, "dossier": dossier.model_dump(mode="json")},
        [review],
        "alice",
    )

    nodes = {node["id"]: node for node in graph["nodes"]}
    edge_types = {edge["type"] for edge in graph["edges"]}
    node_types = {node["type"] for node in graph["nodes"]}
    assert {"candidate", "claim", "citation", "pathway", "decision"}.issubset(node_types)
    assert "candidate:drug:tofacitinib" in nodes
    assert nodes["candidate:drug:tofacitinib"]["metadata"]["decision"] == "pinned"
    assert {"supports", "evidence", "citation", "decision", "knowledge_graph"}.issubset(edge_types)
    assert any(node["type"] == "pathway" and "TNF" in node["label"] for node in graph["nodes"])


def test_dashboard_contains_interactive_evidence_graph_controls():
    root = Path(__file__).parents[1] / "src/med_research/web/static"
    index = (root / "index.html").read_text(encoding="utf-8")
    script = (root / "js/dashboard.js").read_text(encoding="utf-8")
    styles = (root / "css/dashboard.css").read_text(encoding="utf-8")

    assert 'id="workspace-evidence-graph"' in index
    assert "loadWorkspaceEvidenceGraph" in script
    assert "new vis.Network" in script
    assert "/graph`" in script
    assert "workspace-graph-detail" in styles


def test_graph_api_scopes_review_decisions_to_researcher(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    import med_research.web.routers.workspace as workspace_router
    from med_research.web.main import app
    from med_research.web.services.workspace_store import WorkspaceRunStore

    db_path = tmp_path / "workspace.sqlite3"
    store = WorkspaceRunStore(db_path)
    dossier = _graph_dossier("ew-graph-api")
    _save(store, dossier)
    store.upsert_review(
        "ew-graph-api",
        "tofacitinib",
        "drug",
        "Tofacitinib",
        "pinned",
        "Alice rationale",
        "",
        [],
        "",
        "fp-graph-api",
        researcher_id="alice",
    )
    monkeypatch.setattr(workspace_router, "WORKSPACE_DB_PATH", db_path)

    with TestClient(app) as client:
        alice = client.get(
            "/api/workspace/runs/ew-graph-api/graph",
            headers={"X-Researcher-ID": "alice"},
        )
        bob = client.get(
            "/api/workspace/runs/ew-graph-api/graph",
            headers={"X-Researcher-ID": "bob"},
        )

    assert alice.status_code == 200
    assert alice.json()["researcher_id"] == "alice"
    assert any(node["type"] == "decision" for node in alice.json()["nodes"])
    assert bob.status_code == 200
    assert not any(node["type"] == "decision" for node in bob.json()["nodes"])
