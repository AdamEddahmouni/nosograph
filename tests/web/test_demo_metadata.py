"""Public demo metadata and readiness surface."""

DEMO_READ_ONLY = {
    "code": "demo_read_only",
    "detail": "This operation is disabled in the public read-only demo.",
}


def test_demo_mode_metadata_endpoint_exists(demo_client):
    response = demo_client.get("/api/demo_mode")
    assert response.status_code == 200
    body = response.json()
    assert body["demo_mode"] is True, body
    assert body["snapshot_version"]
    assert body["snapshot_path"].endswith("biomedical.sqlite3")


def test_demo_mode_metadata_outside_demo_mode(client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    response = client.get("/api/demo_mode")
    assert response.status_code == 200
    body = response.json()
    assert body["demo_mode"] is False
    assert body["snapshot_version"] == ""


def test_ready_includes_demo_fields_when_demo_mode_is_on(demo_client, demo_snapshot):
    response = demo_client.get("/api/ready")
    assert response.status_code == 200
    body = response.json()
    demo = body["demo"]
    assert demo["demo_mode"] is True
    assert demo["snapshot_version"]
    assert demo["dataset_date"]
    assert (
        demo["dataset_date"]
        == __import__("json").loads(demo_snapshot[1].read_text(encoding="utf-8"))["generated_at"]
    )
    assert demo["supported_disease_ids"] == [
        "sle",
        "ra",
        "ibd",
        "ms",
        "ss",
        "ssc",
        "t1d",
        "ad",
    ]
    assert body["components"]["snapshot"]["status"] == "ok"


def test_demo_ready_does_not_probe_self_hosted_dependencies(demo_client, monkeypatch):
    from med_research.web.routers import system

    for name in ("_check_redis", "_check_celery", "_check_workspace_db", "_check_knowledge_graph"):
        monkeypatch.setattr(
            system,
            name,
            lambda dependency=name: (_ for _ in ()).throw(AssertionError(dependency)),
        )

    response = demo_client.get("/api/ready")

    assert response.status_code == 200
    assert response.json()["components"]["snapshot"]["status"] == "ok"


def test_ready_does_not_crash_when_manifest_is_missing(demo_client, monkeypatch):
    monkeypatch.setenv("DEMO_SNAPSHOT_MANIFEST", "nonexistent-manifest.json")
    response = demo_client.get("/api/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["demo"]["demo_mode"] is True
    assert body["components"]["snapshot"]["status"] == "error"
    # Error detail is generic; filesystem paths must not be exposed publicly.
    assert body["components"]["snapshot"]["detail"] == "Demo snapshot validation failed"
    assert "nonexistent-manifest.json" not in response.text


def test_ready_outside_demo_mode_has_no_demo_block(client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    response = client.get("/api/ready")
    assert response.status_code in {200, 503}
    body = response.json()
    assert body["demo"]["demo_mode"] is False


def test_demo_mode_metadata_is_read_only(demo_client):
    response = demo_client.post("/api/demo_mode", json={"demo_mode": False})
    assert response.status_code == 403
    assert response.json() == DEMO_READ_ONLY


def test_manifest_default_follows_custom_snapshot_filename(monkeypatch, tmp_path):
    """A custom DEMO_SNAPSHOT_PATH must not point at a fixed-named manifest."""
    from med_research.web.config import parse_demo_snapshot_manifest

    monkeypatch.delenv("DEMO_SNAPSHOT_MANIFEST", raising=False)
    monkeypatch.setenv("DEMO_SNAPSHOT_PATH", str(tmp_path / "lupus-demo.sqlite3"))
    assert parse_demo_snapshot_manifest() == tmp_path / "lupus-demo.manifest.json"


def test_manifest_explicit_env_wins_over_derived_default(monkeypatch, tmp_path):
    from med_research.web.config import parse_demo_snapshot_manifest

    monkeypatch.setenv("DEMO_SNAPSHOT_PATH", str(tmp_path / "lupus-demo.sqlite3"))
    monkeypatch.setenv("DEMO_SNAPSHOT_MANIFEST", str(tmp_path / "explicit.json"))
    assert parse_demo_snapshot_manifest() == tmp_path / "explicit.json"
