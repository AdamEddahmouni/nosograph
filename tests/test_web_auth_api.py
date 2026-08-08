import json

from fastapi.testclient import TestClient

from med_research.web.services.workspace_store import WorkspaceRunStore


def test_local_login_binds_workspace_requests_to_session(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("LOCAL_AUTH_USERS", json.dumps({"alice": "secret"}))
    monkeypatch.setenv("AUTH_SESSION_SECRET", "api-test-secret")

    import med_research.web.routers.workspace as workspace_router
    from med_research.web.main import app

    monkeypatch.setattr(workspace_router, "WORKSPACE_DB_PATH", tmp_path / "workspace.sqlite3")
    WorkspaceRunStore(tmp_path / "workspace.sqlite3")

    with TestClient(app) as client:
        before = client.get("/api/auth/me")
        login = client.post("/api/auth/login", json={"username": "alice", "password": "secret"})
        settings = client.get("/api/workspace/notifications")
        client.post("/api/auth/logout")
        after = client.get("/api/auth/me")

    assert before.json() == {"authenticated": False, "researcher_id": None}
    assert login.status_code == 200
    assert login.json() == {"authenticated": True, "researcher_id": "alice"}
    assert settings.status_code == 200
    assert settings.json()["researcher_id"] == "alice"
    assert after.json() == {"authenticated": False, "researcher_id": None}
