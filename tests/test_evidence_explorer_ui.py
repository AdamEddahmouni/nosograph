"""Deterministic browser tests for the Evidence Explorer and modal reliability fixes."""

from __future__ import annotations

import json
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

playwright = pytest.importorskip("playwright.sync_api")

Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright

PROJECT_ROOT = Path(__file__).parents[1]
STATIC_DIR = PROJECT_ROOT / "src" / "med_research" / "web" / "static"
BROWSER_ARTIFACT_DIR = PROJECT_ROOT / "test-artifacts" / "browser"

pytestmark = [pytest.mark.slow, pytest.mark.browser]

FIXTURE_CLAIM_ID = "11111111-1111-1111-1111-111111111111"
FIXTURE_SUBJECT_CURIE = "MONDO:0007915"
FIXTURE_OBJECT_CURIE = "HP:000001"


def _claim_detail() -> dict:
    return {
        "claim_id": FIXTURE_CLAIM_ID,
        "predicate": "HAS_PHENOTYPE",
        "subject_curie": FIXTURE_SUBJECT_CURIE,
        "object_curie": FIXTURE_OBJECT_CURIE,
        "subject_label": "systemic lupus erythematosus",
        "object_label": "All",
        "qualifiers": {},
        "evidence_summary": "SUPPORTS",
        "supporting_count": 1,
        "contradictory_count": 1,
        "inconclusive_count": 0,
        "source_count": 2,
        "supporting_evidence": [],
        "contradictory_evidence": [],
        "provenance": [
            {
                "stage": "ingestion",
                "resource_name": "hpoa",
                "snapshot_version": "2026-01-01",
            },
            {"stage": "graph_claim", "resource_name": "biomed_store"},
        ],
        "disclaimer": {"text": "Research use only."},
    }


def _evidence_items() -> list[dict]:
    return [
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "direction": "supporting",
            "summary": "SUPPORTS",
            "snapshot_id": "33333333-3333-3333-3333-333333333333",
            "source_record_id": "PMID:123456",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/123456/",
            "source_name": "hpoa",
            "evidence_type": "clinical annotation",
            "population": "human cohort",
            "confidence": 0.82,
            "confidence_explanation": "clinical annotation confidence 0.820 from hpoa_import",
            "rationale": "Fixture supporting evidence",
            "publication_date": "2024-01-01",
            "limitations": [],
            "quality": {
                "species_context": "human",
                "study_design": "unknown",
                "sample_size": None,
                "sample_size_context": "unknown",
                "origin_class": "SOURCE_DERIVED",
                "source_quality": "imported",
            },
            "provenance": [{"stage": "source_snapshot", "resource_name": "hpoa"}],
        },
        {
            "id": "44444444-4444-4444-4444-444444444444",
            "direction": "contradictory",
            "summary": "CONTRADICTS",
            "snapshot_id": "55555555-5555-5555-5555-555555555555",
            "source_record_id": "synthetic_test_fixture:contradiction",
            "source_url": "",
            "source_name": "synthetic_test_fixture",
            "evidence_type": "synthetic",
            "population": "mouse model",
            "confidence": None,
            "confidence_explanation": "No numeric confidence score recorded for this evidence item.",
            "rationale": "Synthetic contradictory fixture",
            "publication_date": "",
            "limitations": ["synthetic_test_fixture = true"],
            "quality": {
                "species_context": "animal",
                "study_design": "unknown",
                "sample_size": None,
                "sample_size_context": "unknown",
                "origin_class": "UNKNOWN_ORIGIN_CLASS",
                "source_quality": "unknown",
            },
            "provenance": [],
        },
    ]


class _ExplorerFixtureBackend:
    def http(self, route):
        request = route.request
        path = urlsplit(request.url).path
        if path == "/api/health":
            route.fulfill(status=200, content_type="application/json", body='{"status":"ok"}')
            return
        if path == "/api/system/diseases":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {"diseases": [{"id": "sle", "name": "Systemic Lupus Erythematosus"}]}
                ),
            )
            return
        if path == "/api/stats":
            route.fulfill(status=200, content_type="application/json", body='{"kg_nodes":1}')
            return
        if path == "/api/kg/graph":
            route.fulfill(status=200, content_type="application/json", body='{"elements":[]}')
            return
        if path == "/api/export/modules":
            route.fulfill(status=200, content_type="application/json", body='{"modules":[]}')
            return
        if path == f"/api/v1/claims/{FIXTURE_CLAIM_ID}":
            route.fulfill(
                status=200, content_type="application/json", body=json.dumps(_claim_detail())
            )
            return
        if path == f"/api/v1/claims/{FIXTURE_CLAIM_ID}/evidence":
            items = _evidence_items()
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "items": items,
                        "total": len(items),
                        "limit": 100,
                        "offset": 0,
                        "disclaimer": {"text": "Research use only."},
                    }
                ),
            )
            return
        if path == f"/api/v1/claims/{FIXTURE_CLAIM_ID}/related":
            route.fulfill(status=200, content_type="application/json", body="[]")
            return
        if path.startswith("/api/v1/biomed/structures/"):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "uniprot_id": "P01375",
                        "pdb_id": "1ABC",
                        "chains": ["A"],
                        "viewer_payload": {"atoms": []},
                    }
                ),
            )
            return
        route.fulfill(
            status=404, content_type="application/json", body=json.dumps({"detail": path})
        )


class _StaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format, *args):  # noqa: A003
        return


@pytest.fixture(scope="session")
def explorer_static_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StaticHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    server.shutdown()


@pytest.fixture(scope="session")
def explorer_browser():
    with sync_playwright() as playwright_instance:
        browser = playwright_instance.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def explorer_page(explorer_browser, explorer_static_server):
    backend = _ExplorerFixtureBackend()
    context = explorer_browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.route("**/api/**", backend.http)
    page.goto(explorer_static_server)
    yield page
    context.close()


def test_structure_modal_hidden_on_load(explorer_page: Page):
    modal = explorer_page.locator("#structure-modal")
    expect(modal).to_have_class(re.compile(r"hidden"))


def test_evidence_explorer_deep_link_renders_claim(explorer_page: Page, explorer_static_server):
    base = explorer_static_server.replace("/index.html", "")
    explorer_page.goto(f"{base}/index.html?claim_id={FIXTURE_CLAIM_ID}#evidence-explorer")
    expect(explorer_page.locator("#evidence-explorer-title")).to_be_visible()
    expect(explorer_page.locator(".evidence-claim-header h3")).to_contain_text(
        "systemic lupus erythematosus"
    )
    expect(explorer_page.get_by_text("HAS_PHENOTYPE")).to_be_visible()
    expect(explorer_page.get_by_role("heading", name="Supporting evidence")).to_be_visible()
    expect(explorer_page.get_by_role("heading", name="Contradictory evidence")).to_be_visible()
    expect(explorer_page.get_by_text("Fixture supporting evidence")).to_be_visible()
    expect(explorer_page.get_by_text("Synthetic contradictory fixture")).to_be_visible()


def test_evidence_explorer_shows_species_context(explorer_page: Page, explorer_static_server):
    base = explorer_static_server.replace("/index.html", "")
    explorer_page.goto(f"{base}/index.html?claim_id={FIXTURE_CLAIM_ID}#evidence-explorer")
    expect(explorer_page.get_by_text("Species: human")).to_be_visible()
    expect(explorer_page.get_by_text("Species: animal")).to_be_visible()


def test_evidence_explorer_mobile_width_smoke(explorer_page: Page, explorer_static_server):
    explorer_page.set_viewport_size({"width": 390, "height": 844})
    base = explorer_static_server.replace("/index.html", "")
    explorer_page.goto(f"{base}/index.html?claim_id={FIXTURE_CLAIM_ID}#evidence-explorer")
    expect(explorer_page.locator(".evidence-claim-header")).to_be_visible()
