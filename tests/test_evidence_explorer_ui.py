"""Deterministic browser tests for the Evidence Explorer and modal reliability fixes."""

from __future__ import annotations

import json
import re
import socket
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import uvicorn

from med_research.biomed.identifiers import (
    claim_evidence_uuid,
    claim_uuid,
    entity_revision_uuid,
    entity_uuid,
    snapshot_uuid,
)
from med_research.biomed.imports.models import ImportBundle
from med_research.biomed.imports.service import ImportService
from med_research.biomed.models import (
    Claim,
    ClaimEvidence,
    Entity,
    EntityRevision,
    EntityType,
    EvidenceDirection,
    Predicate,
    ResourceSnapshot,
)
from med_research.biomed.repository import BiomedicalRepository
from med_research.web.dependencies_biomed import get_biomedical_repository
from med_research.web.main import app

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
COMPARE_RUN_ID = "66666666-6666-6666-6666-666666666666"
COMPARE_NEGATED_CLAIM_ID = FIXTURE_CLAIM_ID
COMPARE_CONDITIONS = (
    ("MONDO:0000001", "Condition One"),
    ("MONDO:0000002", "Condition Two"),
    ("MONDO:0000003", "Condition Three"),
)


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


def _comparison_result(dimensions: list[str] | None = None) -> dict:
    condition_curies = [item[0] for item in COMPARE_CONDITIONS]
    labels = dict(COMPARE_CONDITIONS)
    coverage = {
        curie: {
            "positive_claim_count": 1,
            "negated_claim_count": 1 if curie == condition_curies[1] else 0,
            "claim_count": 2 if curie == condition_curies[1] else 1,
            "evidence_count": 1,
            "source_count": 1,
            "snapshot_count": 1,
            "snapshot_ids": ["77777777-7777-7777-7777-777777777777"],
            "source_names": ["playwright-fixture"],
        }
        for curie in condition_curies
    }
    phenotype = {
        "dimension": "phenotype",
        "shared_by_all": ["HP:000001"],
        "shared_by_subset": [],
        "unique_by_condition": {
            condition_curies[0]: ["HP:000002"],
            condition_curies[1]: [],
            condition_curies[2]: [],
        },
        "entities": [
            {
                "entity_curie": "HP:000001",
                "entity_label": "Shared phenotype",
                "states": {curie: "PRESENT" for curie in condition_curies},
                "claim_ids_by_condition": {
                    curie: [f"88888888-8888-8888-8888-88888888888{index}"]
                    for index, curie in enumerate(condition_curies, start=1)
                },
            },
            {
                "entity_curie": "HP:000002",
                "entity_label": "Stateful phenotype",
                "states": {
                    condition_curies[0]: "PRESENT",
                    condition_curies[1]: "KNOWN_ABSENT",
                    condition_curies[2]: "NOT_RECORDED",
                },
                "claim_ids_by_condition": {
                    condition_curies[0]: ["99999999-9999-9999-9999-999999999999"],
                    condition_curies[1]: [COMPARE_NEGATED_CLAIM_ID],
                    condition_curies[2]: [],
                },
            },
        ],
        "coverage_by_condition": coverage,
        "warnings": [],
    }
    gene = {
        "dimension": "gene",
        "shared_by_all": [],
        "shared_by_subset": [],
        "unique_by_condition": {curie: [] for curie in condition_curies},
        "entities": [],
        "coverage_by_condition": coverage,
        "warnings": [],
    }
    selected = dimensions or ["phenotype", "gene"]
    dimension_results = [item for item in (phenotype, gene) if item["dimension"] in selected]
    return {
        "run_id": COMPARE_RUN_ID,
        "status": "comparable",
        "condition_curies": condition_curies,
        "condition_labels": labels,
        "dimensions": [item["dimension"] for item in dimension_results],
        "dimension_results": dimension_results,
        "curation_warnings": [],
        "snapshot_ids": ["77777777-7777-7777-7777-777777777777"],
        "claim_set_fingerprint": "playwright-fixture-fingerprint",
        "algorithm_id": "nosograph-compare-v2",
        "algorithm_version": "2.0.0",
        "disclaimer": {"text": "Research use only.", "schema_version": "1.0"},
    }


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
        if path == "/api/v1/conditions/search":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "items": [
                            {"curie": curie, "label": label, "entity_type": "condition"}
                            for curie, label in COMPARE_CONDITIONS
                        ],
                        "total": len(COMPARE_CONDITIONS),
                        "limit": 20,
                        "offset": 0,
                    }
                ),
            )
            return
        if path == "/api/v1/nosograph/comparisons" and request.method == "POST":
            payload = json.loads(request.post_data or "{}")
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(_comparison_result(payload.get("dimensions"))),
            )
            return
        if path == f"/api/v1/nosograph/comparisons/{COMPARE_RUN_ID}/exports/json":
            route.fulfill(
                status=200,
                content_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="nosograph-comparison-{COMPARE_RUN_ID}.json"'
                },
                body=json.dumps(_comparison_result(), sort_keys=True) + "\n",
            )
            return
        if path == f"/api/v1/nosograph/comparisons/{COMPARE_RUN_ID}/exports/markdown":
            route.fulfill(
                status=200,
                content_type="text/markdown",
                headers={
                    "Content-Disposition": f'attachment; filename="nosograph-comparison-{COMPARE_RUN_ID}.md"'
                },
                body="# NosoGraph comparison\n",
            )
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


@pytest.fixture
def live_compare_server(tmp_path):
    repository = BiomedicalRepository(tmp_path / "compare-browser.sqlite3")
    repository.initialize()
    snapshot = ResourceSnapshot(
        id=snapshot_uuid("compare-browser", "1", "sha256:compare-browser"),
        resource_name="compare-browser",
        version="1",
        checksum="sha256:compare-browser",
        name="Compare browser seam fixture",
        namespace_prefix="MONDO",
    )
    conditions = [
        Entity(
            id=entity_uuid(EntityType.CONDITION, curie),
            primary_curie=curie,
            entity_type=EntityType.CONDITION,
            created_in_snapshot_id=snapshot.id,
        )
        for curie, _ in COMPARE_CONDITIONS
    ]
    phenotype = Entity(
        id=entity_uuid(EntityType.PHENOTYPE, "HP:000001"),
        primary_curie="HP:000001",
        entity_type=EntityType.PHENOTYPE,
        created_in_snapshot_id=snapshot.id,
    )
    revisions = [
        EntityRevision(
            id=entity_revision_uuid(entity.id, snapshot.id),
            entity_id=entity.id,
            snapshot_id=snapshot.id,
            label=label,
        )
        for entity, (_, label) in zip(conditions, COMPARE_CONDITIONS, strict=True)
    ]
    revisions.append(
        EntityRevision(
            id=entity_revision_uuid(phenotype.id, snapshot.id),
            entity_id=phenotype.id,
            snapshot_id=snapshot.id,
            label="Shared phenotype",
        )
    )
    claims = []
    evidence = []
    for index, (curie, _) in enumerate(COMPARE_CONDITIONS, start=1):
        claim = Claim(
            id=claim_uuid(curie, Predicate.HAS_PHENOTYPE, "HP:000001", {}),
            subject_curie=curie,
            predicate=Predicate.HAS_PHENOTYPE,
            object_curie="HP:000001",
        )
        claims.append(claim)
        evidence.append(
            ClaimEvidence(
                id=claim_evidence_uuid(
                    claim.id,
                    snapshot.id,
                    EvidenceDirection.SUPPORTING,
                    f"compare-browser-{index}",
                ),
                claim_id=claim.id,
                snapshot_id=snapshot.id,
                direction=EvidenceDirection.SUPPORTING,
                source_record_id=f"compare-browser-{index}",
            )
        )
    ImportService(repository).import_bundle(
        ImportBundle.build(
            snapshot,
            entities=[*conditions, phenotype],
            revisions=revisions,
            claims=claims,
            evidence=evidence,
        )
    )

    app.dependency_overrides[get_biomedical_repository] = lambda: repository
    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            lifespan="off",
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        if not thread.is_alive():
            pytest.fail("Live FastAPI browser fixture exited during startup")
        time.sleep(0.025)
    else:
        pytest.fail("Live FastAPI browser fixture did not start")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=10)
    app.dependency_overrides.pop(get_biomedical_repository, None)


@pytest.fixture
def live_compare_page(explorer_browser, live_compare_server):
    context = explorer_browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.goto(f"{live_compare_server}/index.html#condition-comparison")
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


def _select_compare_conditions(page: Page) -> None:
    section = page.locator("#condition-comparison")
    control = section.locator(".ts-control input")
    for _, label in COMPARE_CONDITIONS:
        control.fill(label)
        expect(section.locator(".ts-dropdown")).to_be_visible()
        section.locator(".option", has_text=label).first.click()


def test_live_compare_api_connects_browser_to_fastapi(live_compare_page: Page) -> None:
    section = live_compare_page.locator("#condition-comparison")
    _select_compare_conditions(live_compare_page)
    for value in ("gene", "pathway", "treatment", "evidence_coverage"):
        section.locator(f'#comparison-dimensions input[value="{value}"]').uncheck()

    with live_compare_page.expect_response(
        lambda response: (
            response.request.method == "POST"
            and response.url.endswith("/api/v1/nosograph/comparisons")
        )
    ) as response_info:
        section.get_by_role("button", name="Compare selected conditions").click()

    response = response_info.value
    assert response.status == 200
    payload = response.json()
    assert payload["algorithm_version"] == "2.0.0"
    assert payload["result_schema_version"] == "2.0"
    expect(section.get_by_role("heading", name="Shared")).to_be_visible()
    expect(section.get_by_text("Shared phenotype", exact=True)).to_be_visible()


def test_compare_product_flow_drills_into_evidence_and_downloads(
    explorer_page: Page, explorer_static_server
):
    base = explorer_static_server.replace("/index.html", "")
    explorer_page.goto(f"{base}/index.html#condition-comparison")
    section = explorer_page.locator("#condition-comparison")
    _select_compare_conditions(explorer_page)
    for value in ("gene", "pathway", "treatment", "evidence_coverage"):
        section.locator(f'#comparison-dimensions input[value="{value}"]').uncheck()
    section.get_by_role("button", name="Compare selected conditions").click()

    expect(section.get_by_role("tab", name="Phenotype")).to_have_attribute("aria-selected", "true")
    expect(section.get_by_text("Shared", exact=True)).to_be_visible()
    expect(section.get_by_text("Distinct", exact=True)).to_be_visible()
    expect(section.get_by_text("Missing data", exact=True)).to_be_visible()
    expect(section.get_by_text("Known absent", exact=True)).to_be_visible()
    expect(section.get_by_text("Not recorded", exact=True)).to_be_visible()
    for _, label in COMPARE_CONDITIONS:
        expect(
            section.locator(".shared .condition-comparison-claim-group", has_text=label)
        ).to_be_visible()
    assert section.locator(".state-not-recorded a").count() == 0

    with explorer_page.expect_download() as json_download:
        section.get_by_role("link", name="Export JSON").click()
    assert json_download.value.suggested_filename == f"nosograph-comparison-{COMPARE_RUN_ID}.json"
    with explorer_page.expect_download() as markdown_download:
        section.get_by_role("link", name="Export Markdown").click()
    assert markdown_download.value.suggested_filename == f"nosograph-comparison-{COMPARE_RUN_ID}.md"

    section.locator(".state-known-absent [data-comparison-claim-id]").click()
    expect(explorer_page.locator("#evidence-explorer-title")).to_be_visible()
    expect(explorer_page.locator(".evidence-claim-header h3")).to_contain_text(
        "systemic lupus erythematosus"
    )


def test_compare_product_flow_is_single_column_on_mobile(
    explorer_page: Page, explorer_static_server
):
    explorer_page.set_viewport_size({"width": 390, "height": 844})
    base = explorer_static_server.replace("/index.html", "")
    explorer_page.goto(f"{base}/index.html#condition-comparison")
    _select_compare_conditions(explorer_page)
    explorer_page.locator("#comparison-run-btn").click()

    panels = explorer_page.locator("#comparison-panel-phenotype .condition-comparison-panel-grid")
    expect(panels).to_be_visible()
    columns = panels.evaluate("element => getComputedStyle(element).gridTemplateColumns")
    assert len(columns.split()) == 1


def test_compare_dimension_tabs_support_keyboard_navigation(
    explorer_page: Page, explorer_static_server
):
    base = explorer_static_server.replace("/index.html", "")
    explorer_page.goto(f"{base}/index.html#condition-comparison")
    _select_compare_conditions(explorer_page)
    for value in ("pathway", "treatment", "evidence_coverage"):
        explorer_page.locator(f'#comparison-dimensions input[value="{value}"]').uncheck()
    explorer_page.locator("#comparison-run-btn").click()

    phenotype = explorer_page.get_by_role("tab", name="Phenotype")
    gene = explorer_page.get_by_role("tab", name="Gene")
    phenotype.focus()
    phenotype.press("ArrowRight")

    expect(gene).to_be_focused()
    expect(gene).to_have_attribute("aria-selected", "true")
    expect(explorer_page.locator("#comparison-panel-gene")).to_be_visible()
    expect(explorer_page.locator("#comparison-panel-phenotype")).to_be_hidden()
