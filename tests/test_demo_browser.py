"""Browser smoke test for the public read-only demo mode.

Runs a live FastAPI server in demo mode against a fixture-backed immutable
snapshot and walks the flagship public flow in a real browser:

home page with demo banner -> condition search -> claim -> evidence filters
-> provenance -> two-condition Compare preview -> preview export.

It also asserts that mutation-capable requests are never issued by the demo
UI and that blocked endpoints return the ``demo_read_only`` policy contract.
"""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

from med_research.web.dependencies_biomed import reset_biomedical_repository
from med_research.web.main import app

playwright = pytest.importorskip("playwright.sync_api")

Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright

PROJECT_ROOT = Path(__file__).parents[1]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "biomed"

pytestmark = [pytest.mark.slow, pytest.mark.browser]

SUPPORTED_CONDITION_CURIE = "MONDO:0007915"
SUPPORTED_CONDITION_LABEL = "systemic lupus erythematosus"
SECOND_CONDITION_CURIE = "MONDO:0004992"
SECOND_CONDITION_LABEL = "autoimmune disease"


@pytest.fixture(scope="session")
def demo_snapshot(tmp_path_factory) -> tuple[Path, Path, str]:
    """Build one disposable fixture-backed snapshot for demo browser tests."""
    from scripts.build_demo_snapshot import build_demo_snapshot, manifest_path_for

    output = tmp_path_factory.mktemp("public-demo-browser") / "biomedical.sqlite3"
    build_demo_snapshot(output, fixture_root=FIXTURES)
    manifest = manifest_path_for(output)
    version = json.loads(manifest.read_text(encoding="utf-8"))["snapshot_version"]
    return output, manifest, version


@pytest.fixture
def demo_browser_env(monkeypatch, demo_snapshot):
    """Configure a valid isolated public-demo environment for one test."""
    output, manifest, version = demo_snapshot
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_SNAPSHOT_PATH", str(output))
    monkeypatch.setenv("DEMO_SNAPSHOT_MANIFEST", str(manifest))
    monkeypatch.setenv("DEMO_SNAPSHOT_VERSION", version)
    reset_biomedical_repository()
    yield
    reset_biomedical_repository()


@pytest.fixture
def demo_server(demo_browser_env) -> str:
    """Live FastAPI server running in demo mode against the snapshot."""
    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        if not thread.is_alive():
            pytest.fail("Demo FastAPI browser fixture exited during startup")
        time.sleep(0.025)
    else:
        pytest.fail("Demo FastAPI browser fixture did not start")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=10)
    reset_biomedical_repository()


@pytest.fixture(scope="session")
def demo_browser():
    with sync_playwright() as playwright_context:
        browser = playwright_context.chromium.launch(headless=True)
        yield browser
        browser.close()


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _discover_claim_id(base: str) -> str:
    claims = _get_json(f"{base}/api/v1/conditions/{SUPPORTED_CONDITION_CURIE}/claims?limit=100")
    items = claims.get("items") or []
    assert items, "Demo snapshot must contain claims for MONDO:0007915"
    for item in items:
        detail = _get_json(f"{base}/api/v1/claims/{item['claim_id']}")
        if detail.get("evidence_summary") == "SUPPORTS":
            return item["claim_id"]
    return items[0]["claim_id"]


def _is_mutation_request(url: str) -> bool:
    if "/preview" in url:
        return False
    return any(
        prefix in url
        for prefix in (
            "/api/jobs",
            "/api/workspace",
            "/api/admin",
            "/api/system/cache",
            "/api/llm",
            "/api/evidence/gather",
            "/api/monitor",
            "/api/agent",
            "/api/v1/nosograph/comparisons/",
        )
    )


def _select_compare_conditions(page: Page) -> None:
    section = page.locator("#condition-comparison")
    control = section.locator(".ts-control input")
    for label in (SUPPORTED_CONDITION_LABEL, SECOND_CONDITION_LABEL):
        control.fill(label)
        expect(section.locator(".ts-dropdown")).to_be_visible()
        section.locator(".option", has_text=label).first.click()


def test_demo_browser_public_flow(demo_browser, demo_server) -> None:
    base = demo_server
    claim_id = _discover_claim_id(base)
    mutation_requests: list[str] = []

    context = demo_browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.on(
        "request",
        lambda request: (
            mutation_requests.append(request.url) if _is_mutation_request(request.url) else None
        ),
    )
    try:
        # 1. Home page: demo banner with fixed snapshot identity.
        page.goto(f"{base}/index.html")
        banner = page.locator("#demo-banner")
        expect(banner).to_be_visible()
        expect(banner).to_contain_text("PUBLIC DEMO")
        expect(banner).to_contain_text("FIXED RESEARCH SNAPSHOT")
        expect(banner).to_contain_text("DATA DATE:")
        expect(banner).to_contain_text("SNAPSHOT demo-")
        expect(page.get_by_text("Research use only", exact=False).first).to_be_visible()

        # 2. Condition search for a supported condition.
        page.goto(f"{base}/index.html#condition-explorer")
        page.wait_for_function("document.body.dataset.booted === 'true'")
        search = page.locator("#condition-search-input")
        search.fill("lupus")
        result = page.locator(".condition-result-item", has_text=SUPPORTED_CONDITION_LABEL)
        expect(result).to_be_visible()
        result.click()
        expect(page.locator("#condition-explorer-detail h3")).to_contain_text(
            SUPPORTED_CONDITION_LABEL
        )
        expect(page.locator("#condition-explorer-detail")).to_contain_text("HAS_PHENOTYPE")

        # 3. Claim detail with evidence filters and provenance.
        page.goto(f"{base}/index.html?claim_id={claim_id}#evidence-explorer")
        page.wait_for_function("document.body.dataset.booted === 'true'")
        expect(page.locator("#evidence-explorer-title")).to_be_visible()
        expect(page.locator(".evidence-claim-header h3")).to_contain_text(SUPPORTED_CONDITION_LABEL)
        expect(page.locator("#evidence-explorer-filters")).to_be_visible()
        expect(page.locator(".evidence-card")).to_have_count(1)
        expect(page.locator("#evidence-provenance-title")).to_be_visible()
        expect(page.locator(".evidence-provenance-chain").first).to_contain_text("hpoa")

        # Filter evidence by direction and confirm the list narrows.
        page.select_option("#evidence-filter-direction", "supporting")
        expect(page.locator(".evidence-card")).to_have_count(1)
        page.select_option("#evidence-filter-direction", "contradictory")
        expect(page.locator(".evidence-card")).to_have_count(0)
        expect(page.get_by_text("No contradictory evidence")).to_be_visible()

        # 4. Non-persisting Compare preview for two conditions.
        page.goto(f"{base}/index.html#condition-comparison")
        page.wait_for_function("document.body.dataset.booted === 'true'")
        section = page.locator("#condition-comparison")
        _select_compare_conditions(page)
        with page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and response.url.endswith("/api/v1/nosograph/comparisons/preview")
            )
        ):
            section.get_by_role("button", name="Compare selected conditions").click()
        expect(section.get_by_role("heading", name="Evidence state comparison")).to_be_visible()
        expect(section.locator(".condition-comparison-meta")).to_contain_text(
            "preview (not persisted)"
        )

        # 5. Deterministic preview export.
        with page.expect_download() as download_info:
            section.get_by_role("button", name="Export JSON").click()
        assert download_info.value.suggested_filename == "nosograph-comparison-preview.json"

        # 6. No job, workspace, admin, or persisted-compare write was issued.
        assert mutation_requests == [], (
            f"Mutation-capable requests fired in demo mode: {mutation_requests}"
        )
    finally:
        context.close()


def test_demo_browser_blocks_mutation_endpoints(demo_browser, demo_server) -> None:
    base = demo_server
    context = demo_browser.new_context()
    page = context.new_page()
    try:
        response = page.request.post(
            f"{base}/api/jobs",
            data=json.dumps({"module": "docking", "disease_id": "sle"}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status == 403
        assert response.json()["code"] == "demo_read_only"

        workspace = page.request.post(
            f"{base}/api/workspace/run",
            data=json.dumps({"disease_id": "sle", "question": "x"}),
            headers={"Content-Type": "application/json"},
        )
        assert workspace.status == 403
        assert workspace.json()["code"] == "demo_read_only"

        persisted = page.request.post(
            f"{base}/api/v1/nosograph/comparisons",
            data=json.dumps(
                {
                    "condition_curies": [
                        SUPPORTED_CONDITION_CURIE,
                        SECOND_CONDITION_CURIE,
                    ],
                    "dimensions": ["phenotype"],
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        assert persisted.status == 403
        assert persisted.json()["code"] == "demo_read_only"
    finally:
        context.close()
