"""Browser-level regression tests for the fixture-backed Evidence Workspace.

These tests deliberately serve only the dashboard's static assets and intercept every
API/WebSocket request with deterministic fixtures. They therefore exercise the real
browser DOM, authentication/review handlers, graph interactions, WebSocket lifecycle,
polling fallback, and download/popup behavior without Redis, Celery, credentials, or
live biomedical APIs.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

playwright = pytest.importorskip("playwright.sync_api")

# Importing through a local alias keeps optional Playwright collection explicit.
Browser = playwright.Browser
Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright

PROJECT_ROOT = Path(__file__).parents[1]
STATIC_DIR = PROJECT_ROOT / "src" / "med_research" / "web" / "static"
BROWSER_ARTIFACT_DIR = PROJECT_ROOT / "test-artifacts" / "browser"

pytestmark = [pytest.mark.slow]


def _fixture_dossier() -> dict:
    return {
        "run_id": "ew-browser-fixture-001",
        "request": {"question": "Find JAK interventions for SLE", "disease_id": "sle"},
        "manifest": {
            "provenance": {"fingerprint": "sha256-browser-fixture-001", "cache_or_live": "fixture"}
        },
        "source_statuses": [
            {"source": "pubmed", "status": "ok", "records_found": 2, "retrieval_mode": "fixture"},
            {
                "source": "clinical_trials",
                "status": "error",
                "records_found": 0,
                "retrieval_mode": "fixture",
                "warning": "Fixture trial source unavailable",
            },
        ],
        "evidence": [
            {"evidence_id": "ev-pubmed-1", "quality_tier": "tier_1", "quality_score": 0.9},
            {"evidence_id": "ev-pubmed-2", "quality_tier": "tier_2", "quality_score": 0.7},
        ],
        "claims": [
            {
                "claim_id": "claim-support",
                "relationship": "supports",
                "subject_name": "Tofacitinib",
                "text": "JAK inhibition reduced inflammatory signaling in the fixture evidence.",
                "supporting_snippet": "Fixture abstract: reduced inflammatory signaling.",
                "confidence": 0.9,
                "evidence_ids": ["ev-pubmed-1"],
                "citations": [
                    {"native_id": "PMID:123456", "url": "https://pubmed.ncbi.nlm.nih.gov/123456/"}
                ],
            },
            {
                "claim_id": "claim-contradiction",
                "relationship": "contradicts",
                "subject_name": "Tofacitinib",
                "text": "The fixture evidence reports a safety limitation.",
                "supporting_snippet": "Fixture abstract: safety limitation observed.",
                "confidence": 0.6,
                "evidence_ids": ["ev-pubmed-2"],
                "citations": [{"native_id": "NCT000123", "url": "javascript:alert(1)"}],
            },
        ],
        "drug_rankings": [
            {
                "candidate_id": "drug-tofacitinib",
                "name": "Tofacitinib",
                "score": 87.5,
                "confidence_band": "high",
                "explanation": "Strong mechanistic and evidence support.",
                "component_scores": {"evidence_quality": 8.8, "recency": 7.2},
                "supporting_claim_ids": ["claim-support"],
                "contradicting_claim_ids": ["claim-contradiction"],
                "graph_explanation_ids": ["path-tofacitinib"],
            }
        ],
        "target_rankings": [
            {
                "candidate_id": "target-jak1",
                "name": "JAK1",
                "score": 81.0,
                "confidence_band": "moderate",
                "component_scores": {"evidence_quality": 8.1},
                "supporting_claim_ids": [],
                "contradicting_claim_ids": [],
                "graph_explanation_ids": [],
            }
        ],
        "graph_explanations": [
            {
                "explanation_id": "path-tofacitinib",
                "candidate_id": "drug-tofacitinib",
                "status": "found",
                "path_labels": ["Tofacitinib", "JAK1", "SLE"],
            }
        ],
        "warnings": ["ClinicalTrials.gov fixture source was unavailable."],
        "limitations": ["Fixture data is not a substitute for live source validation."],
        "disclaimer": "For research purposes only. Not medical advice.",
    }


class _StaticHandler(SimpleHTTPRequestHandler):
    """Serve dashboard assets and the repository's local vis-network library."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def translate_path(self, path):
        parsed_path = urlsplit(path).path
        if parsed_path.startswith("/lib/"):
            return str(PROJECT_ROOT / parsed_path.lstrip("/"))
        return super().translate_path(path)

    def log_message(self, _format, *_args):
        return


@pytest.fixture(scope="session")
def static_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StaticHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.fixture(scope="session")
def browser() -> Browser:
    with sync_playwright() as playwright_context:
        browser = playwright_context.chromium.launch(headless=True)
        yield browser
        browser.close()


class _FixtureBackend:
    def __init__(self, mode: str):
        self.mode = mode
        self.post_count = 0
        self.poll_count = 0
        self.post_payload = None
        self.job_id = "browser-fixture-job-001"
        self.dossier = _fixture_dossier()
        self.html = "<html><body><h1>Fixture Evidence Dossier</h1></body></html>"
        self.authenticated = False
        self.login_payload = None
        self.review_request = None
        self.review_bundle = b"PK\\x03\\x04fixture-review-bundle"
        self.review_response = {
            "run_id": self.dossier["run_id"],
            "researcher_id": "fixture-researcher",
            "candidate_id": "drug-tofacitinib",
            "candidate_type": "drug",
            "candidate_name": "Tofacitinib",
            "decision": "pinned",
            "rationale": "Fixture rationale",
            "notes": "Fixture review notes",
            "tags": ["follow-up"],
            "changed_my_mind": "Fixture evidence changed my mind",
            "provenance_fingerprint": "sha256-browser-fixture-001",
            "created_at": "2026-08-10T00:00:00Z",
            "updated_at": "2026-08-10T00:00:00Z",
        }
        self.graph_payload = {
            "run_id": self.dossier["run_id"],
            "researcher_id": "fixture-researcher",
            "nodes": [
                {
                    "id": "candidate:drug-tofacitinib",
                    "type": "candidate",
                    "label": "Tofacitinib",
                    "subtitle": "drug candidate",
                    "description": "Fixture candidate detail",
                    "metadata": {"decision": "pinned"},
                },
                {
                    "id": "claim:claim-support",
                    "type": "claim",
                    "label": "Supports JAK inhibition",
                    "subtitle": "supporting claim",
                    "metadata": {"confidence": 0.9},
                },
                {
                    "id": "citation:PMID-123456",
                    "type": "citation",
                    "label": "PMID:123456",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/123456/",
                },
            ],
            "edges": [
                {
                    "id": "edge-1",
                    "source": "candidate:drug-tofacitinib",
                    "target": "claim:claim-support",
                    "type": "supports",
                    "label": "supports",
                },
                {
                    "id": "edge-2",
                    "source": "claim:claim-support",
                    "target": "citation:PMID-123456",
                    "type": "citation",
                    "label": "cited by",
                },
            ],
        }
        self.history_runs = [
            {
                "run_id": "history-left",
                "disease_id": "sle",
                "question": "<img src=x onerror=alert(1)> historical question",
                "status": "SUCCESS",
                "evidence_count": 4,
                "claim_count": 2,
                "drug_count": 1,
                "target_count": 1,
                "updated_at": "2026-08-01T00:00:00Z",
            },
            {
                "run_id": "history-right",
                "disease_id": "sle",
                "question": "Which JAK intervention changed?",
                "status": "SUCCESS",
                "evidence_count": 6,
                "claim_count": 3,
                "drug_count": 1,
                "target_count": 1,
                "updated_at": "2026-08-02T00:00:00Z",
            },
        ]
        self.compare_payload = {
            "left_run_id": "history-left",
            "right_run_id": "history-right",
            "left": {},
            "right": {},
            "drug_changes": [
                {
                    "name": "<img src=x onerror=alert(1)>",
                    "left_score": 80.0,
                    "right_score": 72.0,
                    "score_delta": -8.0,
                }
            ],
            "target_changes": [],
            "evidence_changes": {},
            "review_changes": [],
            "summary": {"changed": 1},
        }
        self.trend_payload = {
            "runs": [
                {
                    "run_id": "history-left",
                    "question": "first",
                    "timestamp": "2026-08-01T00:00:00Z",
                    "evidence_count": 4,
                    "claim_count": 2,
                    "warning_count": 0,
                },
                {
                    "run_id": "history-right",
                    "question": "second",
                    "timestamp": "2026-08-02T00:00:00Z",
                    "evidence_count": 6,
                    "claim_count": 3,
                    "warning_count": 1,
                },
            ],
            "drug_series": [
                {
                    "candidate_id": "drug-1",
                    "name": "<svg onload=alert(1)>",
                    "points": [
                        {
                            "run_id": "history-left",
                            "timestamp": "2026-08-01T00:00:00Z",
                            "score": 80,
                            "rank": 1,
                            "confidence_band": "high",
                            "present": True,
                        },
                        {
                            "run_id": "history-right",
                            "timestamp": "2026-08-02T00:00:00Z",
                            "score": 72,
                            "rank": 2,
                            "confidence_band": "moderate",
                            "present": True,
                        },
                    ],
                }
            ],
            "target_series": [
                {
                    "candidate_id": "target-1",
                    "name": "JAK1",
                    "points": [
                        {
                            "run_id": "history-left",
                            "timestamp": "2026-08-01T00:00:00Z",
                            "score": 70,
                            "rank": 2,
                            "confidence_band": "moderate",
                            "present": True,
                        },
                        {
                            "run_id": "history-right",
                            "timestamp": "2026-08-02T00:00:00Z",
                            "score": 75,
                            "rank": 1,
                            "confidence_band": "high",
                            "present": True,
                        },
                    ],
                }
            ],
        }

    @staticmethod
    def _fulfill(route, payload):
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    def http(self, route):
        request = route.request
        path = urlsplit(request.url).path
        if path == "/api/auth/me" and request.method == "GET":
            self._fulfill(
                route,
                {
                    "authenticated": self.authenticated,
                    "researcher_id": "fixture-researcher" if self.authenticated else None,
                },
            )
            return
        if path == "/api/auth/login" and request.method == "POST":
            self.login_payload = json.loads(request.post_data or "{}")
            self.authenticated = True
            self._fulfill(route, {"authenticated": True, "researcher_id": "fixture-researcher"})
            return
        if path == "/api/auth/logout" and request.method == "POST":
            self.authenticated = False
            self._fulfill(route, {"authenticated": False})
            return
        if path == "/api/jobs/workspace" and request.method == "POST":
            self.post_count += 1
            self.post_payload = json.loads(request.post_data or "{}")
            self._fulfill(
                route, {"job_id": self.job_id, "status": "PENDING", "module": "workspace"}
            )
            return
        if path == f"/api/jobs/{self.job_id}" and request.method == "GET":
            self.poll_count += 1
            payload = (
                {"status": "SUCCESS", "result": {"dossier": self.dossier, "html": self.html}}
                if self.mode == "fallback"
                else {"status": "PENDING"}
            )
            self._fulfill(route, payload)
            return
        if (
            path == f"/api/workspace/runs/{self.dossier['run_id']}/reviews"
            and request.method == "GET"
        ):
            self._fulfill(
                route,
                {
                    "run_id": self.dossier["run_id"],
                    "reviews": [self.review_response] if self.review_request else [],
                },
            )
            return
        if (
            path == f"/api/workspace/runs/{self.dossier['run_id']}/reviews"
            and request.method == "PUT"
        ):
            self.review_request = json.loads(request.post_data or "{}")
            self.review_response.update(self.review_request)
            self._fulfill(route, self.review_response)
            return
        if (
            path == f"/api/workspace/runs/{self.dossier['run_id']}/graph"
            and request.method == "GET"
        ):
            self._fulfill(route, self.graph_payload)
            return
        if (
            path == f"/api/workspace/runs/{self.dossier['run_id']}/review-bundle"
            and request.method == "GET"
        ):
            route.fulfill(
                status=200,
                content_type="application/zip",
                body=self.review_bundle,
                headers={
                    "Content-Disposition": f'attachment; filename="workspace-{self.dossier["run_id"]}-review.zip"'
                },
            )
            return
        if path == "/api/workspace/notifications" and request.method == "GET":
            self._fulfill(
                route,
                {
                    "researcher_id": "fixture-researcher",
                    "email": "",
                    "email_enabled": True,
                    "slack_configured": False,
                    "slack_enabled": True,
                    "score_drop_threshold": 0,
                    "rank_change_threshold": 0,
                    "evidence_quality_change_threshold": 0,
                    "weekly_digest_enabled": False,
                    "weekly_digest_weekday": 0,
                    "weekly_digest_hour": 9,
                    "weekly_digest_minute": 0,
                    "weekly_digest_timezone": "UTC",
                    "delivery": {},
                    "digest_delivery": {},
                },
            )
            return
        if path == "/api/workspace/alerts" and request.method == "GET":
            self._fulfill(route, {"alerts": [], "unread_count": 0, "limit": 20, "offset": 0})
            return
        if path == "/api/workspace/compare" and request.method == "GET":
            self._fulfill(route, self.compare_payload)
            return
        if path == "/api/workspace/runs/history-left" and request.method == "GET":
            self._fulfill(
                route,
                {
                    "run_id": "history-left",
                    "status": "SUCCESS",
                    "request": self.dossier["request"],
                    "dossier": self.dossier,
                    "html": self.html,
                    "created_at": "2026-08-01T00:00:00Z",
                    "updated_at": "2026-08-01T00:00:00Z",
                },
            )
            return
        if path.startswith("/api/v1/biomed/structures/"):
            self._fulfill(
                route,
                {
                    "uniprot_id": "P01375",
                    "pdb_id": "1ABC",
                    "chains": ["A"],
                    "viewer_payload": {"atoms": []},
                },
            )
            return
        responses = {
            "/api/system/diseases": {
                "diseases": [{"id": "sle", "name": "Systemic Lupus Erythematosus"}]
            },
            "/api/health": {"status": "ok"},
            "/api/stats": {"kg_nodes": 1, "genes": 1, "candidates": 1, "kg_edges": 0},
            "/api/kg/graph": {"elements": []},
            "/api/export/modules": {"modules": []},
            "/api/workspace/runs": {"runs": self.history_runs if self.mode == "history" else []},
            "/api/workspace/trends": self.trend_payload
            if self.mode == "history"
            else {"runs": [], "drug_series": [], "target_series": []},
        }
        if path not in responses:
            route.fulfill(
                status=404,
                content_type="application/json",
                body=json.dumps({"detail": path}),
            )
            return
        self._fulfill(route, responses[path])

    def websocket(self, websocket):
        if self.mode in {"success", "review"}:
            websocket.send(
                json.dumps(
                    {"status": "SUCCESS", "result": {"dossier": self.dossier, "html": self.html}}
                )
            )
        elif self.mode in {"failure", "error", "timeout"}:
            status = {"failure": "FAILURE", "error": "ERROR", "timeout": "TIMEOUT"}[self.mode]
            websocket.send(
                json.dumps(
                    {
                        "status": status,
                        "error": "<img src=x onerror=alert(1)>",
                    }
                )
            )
        elif self.mode == "fallback":
            websocket.close(code=1000, reason="fixture fallback")
        elif self.mode == "pending":
            # Leave the stream open so the test can observe the disabled state.
            return


@pytest.fixture
def dashboard_page(browser: Browser, static_server: str, request):
    context = browser.new_context(accept_downloads=True)
    context.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    context.route("https://fonts.gstatic.com/**", lambda route: route.abort())
    page = context.new_page()
    console_messages = []
    failed_requests = []
    page.on("console", lambda message: console_messages.append(f"{message.type}: {message.text}"))
    page.on(
        "requestfailed",
        lambda failed: failed_requests.append(f"{failed.method} {failed.url} — {failed.failure}"),
    )
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    yield page, static_server
    failed = any(
        getattr(request.node, phase, None) is not None and getattr(request.node, phase).failed
        for phase in ("rep_setup", "rep_call", "rep_teardown")
    )
    trace_path = None
    try:
        if failed:
            BROWSER_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
            test_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.nodeid)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            prefix = BROWSER_ARTIFACT_DIR / f"{test_name}-{timestamp}"
            trace_path = f"{prefix}.trace.zip"
            try:
                page.screenshot(path=f"{prefix}.png", full_page=True)
            except Exception as screenshot_error:  # pragma: no cover - crash diagnostics
                console_messages.append(f"screenshot failed: {screenshot_error}")
            (Path(f"{prefix}.console.log")).write_text(
                "\\n".join(console_messages) + "\\n", encoding="utf-8"
            )
            (Path(f"{prefix}.network.log")).write_text(
                "\\n".join(failed_requests) + "\\n", encoding="utf-8"
            )
        context.tracing.stop(path=trace_path) if trace_path else context.tracing.stop()
    finally:
        for ws in context.pages:
            ws.close()
        context.close()


def _open_dashboard(page: Page, base_url: str, backend: _FixtureBackend):
    page.route("**/api/**", backend.http)
    # For fallback coverage, deliberately leave the socket unrouted: the static
    # fixture server has no WebSocket endpoint, so the browser exercises the real
    # error/close path before polling the mocked HTTP status endpoint.
    if backend.mode != "fallback":
        page.route_web_socket("**/api/jobs/*/ws", backend.websocket)
    page.goto(base_url)
    expect(page.locator("#workspace-submit")).to_be_visible()
    expect(page.locator("#disease-selector")).to_have_value("sle")


def _submit_workspace(page: Page):
    page.locator("#workspace-question").fill("Find JAK interventions for SLE")
    page.get_by_role("button", name=re.compile("Run workspace")).click()


def test_workspace_browser_submission_renders_fixture_result(dashboard_page):
    page, base_url = dashboard_page
    backend = _FixtureBackend("success")
    _open_dashboard(page, base_url, backend)
    _submit_workspace(page)
    expect(page.locator("#workspace-result")).to_contain_text("Dossier ready")
    expect(page.locator("#workspace-submit-status")).to_have_text("Workspace dossier ready.")
    expect(page.locator("#workspace-submit")).to_be_enabled()
    assert backend.post_count == 1
    assert backend.post_payload["sources"] == ["pubmed", "clinical_trials"]
    assert backend.post_payload["disease_id"] == "sle"


def test_workspace_browser_blocks_duplicate_submission_while_running(dashboard_page):
    page, base_url = dashboard_page
    backend = _FixtureBackend("pending")
    _open_dashboard(page, base_url, backend)
    _submit_workspace(page)
    page.locator("#workspace-form").dispatch_event("submit")
    expect(page.locator("#workspace-submit")).to_be_disabled()
    expect(page.locator("#workspace-submit-status")).to_contain_text(
        "duplicate submissions are disabled"
    )
    assert backend.post_count == 1
    assert backend.post_payload["sources"] == ["pubmed", "clinical_trials"]


@pytest.mark.parametrize(
    ("mode", "status_label", "escaped_error"),
    [
        ("failure", "Job failed:", True),
        ("error", "Stream error:", True),
        ("timeout", "Timeout:", True),
    ],
)
def test_workspace_browser_terminal_errors_reenable_form_and_escape_messages(
    dashboard_page, mode, status_label, escaped_error
):
    page, base_url = dashboard_page
    backend = _FixtureBackend(mode)
    _open_dashboard(page, base_url, backend)
    _submit_workspace(page)

    result = page.locator("#workspace-result")
    expect(result).to_contain_text(status_label)
    if escaped_error:
        assert "&lt;img" in result.inner_html() or "onerror=alert(1)" not in result.inner_html()
    expect(result.locator("img")).to_have_count(0)
    expect(page.locator("#workspace-submit")).to_be_enabled()
    expect(page.locator("#workspace-form")).to_have_attribute("aria-busy", "false")
    expect(page.locator("#workspace-submit")).to_have_attribute("aria-busy", "false")
    expect(result).not_to_have_attribute("aria-busy", "true")


def test_workspace_browser_uses_http_polling_when_websocket_closes(dashboard_page):
    page, base_url = dashboard_page
    backend = _FixtureBackend("fallback")
    _open_dashboard(page, base_url, backend)
    _submit_workspace(page)
    expect(page.locator("#workspace-result")).to_contain_text(
        "falling back to polling", timeout=5_000
    )
    expect(page.locator("#workspace-result")).to_contain_text("Dossier ready", timeout=15_000)
    assert backend.post_count == 1
    assert backend.poll_count >= 1


def test_workspace_browser_shows_source_statuses_and_ranking_explanation(dashboard_page):
    page, base_url = dashboard_page
    backend = _FixtureBackend("success")
    _open_dashboard(page, base_url, backend)
    _submit_workspace(page)
    result = page.locator("#workspace-result")
    expect(result).to_contain_text("PubMed")
    expect(result).to_contain_text("ClinicalTrials.gov")
    expect(result).to_contain_text("sha256-browser-fixture-001")
    expect(result).to_contain_text("Tofacitinib")
    explanation = result.locator("summary", has_text="Why this ranked").first
    expect(explanation).to_be_visible()
    explanation.click()
    expect(result).to_contain_text("supporting evidence:")
    expect(result).to_contain_text("contradicting evidence:")
    expect(result).to_contain_text("Tofacitinib → JAK1 → SLE")
    expect(result.locator('a[href^="https://pubmed.ncbi.nlm.nih.gov/"]')).to_have_count(2)
    expect(result.locator('a[href^="javascript:"]')).to_have_count(0)


def test_workspace_browser_exposes_accessible_workspace_regions(dashboard_page):
    page, base_url = dashboard_page
    backend = _FixtureBackend("success")
    _open_dashboard(page, base_url, backend)
    expect(page.locator("#workspace-form")).to_have_attribute(
        "aria-describedby", "workspace-submit-status"
    )
    expect(page.locator("#workspace-sources")).to_have_attribute("aria-label", "Evidence sources")
    expect(page.locator("#workspace-result")).to_have_attribute("role", "region")
    expect(page.locator("#workspace-submit-status")).to_have_attribute("aria-live", "polite")
    expect(page.locator("#workspace-trend-status")).to_have_attribute("role", "status")
    expect(page.locator("#workspace-graph-status")).to_have_attribute("role", "status")


def test_workspace_browser_history_compare_trends_and_safe_dynamic_values(dashboard_page):
    page, base_url = dashboard_page
    backend = _FixtureBackend("history")
    _open_dashboard(page, base_url, backend)

    history = page.locator("#workspace-history-list")
    expect(history.locator(".workspace-compare-check")).to_have_count(2)
    expect(history.locator("img")).to_have_count(0)
    expect(history).to_contain_text("historical question")

    history.locator(".workspace-compare-check").nth(0).check()
    history.locator(".workspace-compare-check").nth(1).check()
    history.get_by_role("button", name="Compare selected runs").click()
    comparison = page.locator("#workspace-compare")
    expect(comparison).to_contain_text("Run comparison")
    expect(comparison.locator("img")).to_have_count(0)
    expect(comparison).to_contain_text("-8.0")

    trend_status = page.locator("#workspace-trend-status")
    expect(trend_status).to_contain_text("2 successful runs")
    expect(page.locator("#workspace-trend-chart svg")).to_have_count(1)
    expect(page.locator("#workspace-trend-chart svg")).to_have_attribute("role", "img")
    page.locator("#workspace-trend-kind").select_option("target")
    expect(trend_status).to_contain_text("1 target series")
    expect(page.locator("#workspace-trend-candidate option")).to_have_count(2)
    expect(page.locator("#workspace-trend-chart svg[onload]")).to_have_count(0)
    expect(page.locator("#workspace-trend-chart script")).to_have_count(0)
    trend_table = page.locator("#workspace-trend-table table")
    expect(trend_table).to_have_count(1)
    expect(trend_table.locator("caption")).to_contain_text("candidate scores")
    expect(trend_table.locator("thead th")).to_have_count(3)
    expect(trend_table.locator("tbody th")).to_contain_text("JAK1")
    expect(trend_table.locator("tbody td").first).to_contain_text("70.0")
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Download CSV").click()
    trend_download = download_info.value
    assert trend_download.suggested_filename == "workspace-target-trends.csv"
    trend_csv = Path(trend_download.path()).read_text(encoding="utf-8")
    assert "candidate_type" in trend_csv
    assert '"target","target-1","JAK1"' in trend_csv
    assert '"history-right"' in trend_csv

    history.get_by_role("button", name=re.compile("Open saved run history-left")).click()
    expect(page.locator("#workspace-result")).to_contain_text("Dossier ready")


def test_workspace_browser_exports_json_and_html(dashboard_page):
    page, base_url = dashboard_page
    backend = _FixtureBackend("success")
    _open_dashboard(page, base_url, backend)
    _submit_workspace(page)
    with page.expect_download() as download_info:
        page.get_by_role("button", name=re.compile("JSON")).click()
    download = download_info.value
    assert download.suggested_filename == "evidence-dossier.json"
    assert (
        json.loads(Path(download.path()).read_text(encoding="utf-8"))["run_id"]
        == backend.dossier["run_id"]
    )
    with page.expect_popup() as popup_info:
        page.get_by_role("button", name=re.compile("HTML")).click()
    popup = popup_info.value
    expect(popup.locator("body")).to_contain_text("Fixture Evidence Dossier")


def test_workspace_browser_researcher_review_graph_and_bundle(dashboard_page):
    page, base_url = dashboard_page
    backend = _FixtureBackend("review")
    _open_dashboard(page, base_url, backend)
    _submit_workspace(page)

    result = page.locator("#workspace-result")
    expect(result).to_contain_text("Dossier ready")
    page.locator("#workspace-auth-username").fill("fixture-user")
    page.locator("#workspace-auth-password").fill("fixture-password")
    page.get_by_role("button", name="Sign in").click()
    expect(page.locator("#workspace-auth-status")).to_have_text("Signed in as fixture-researcher")
    assert backend.login_payload == {"username": "fixture-user", "password": "fixture-password"}

    review = result.locator(".workspace-review-card").first
    review.locator("summary", has_text="Researcher review").click()
    review.locator('[data-review-field="decision"]').select_option("pinned")
    review.locator('[data-review-field="notes"]').fill("Fixture review notes")
    review.get_by_role("button", name="Save review").click()
    expect(review.locator(".workspace-review-status")).to_contain_text("sha256-browser-fixture-001")
    assert backend.review_request == {
        "candidate_id": "drug-tofacitinib",
        "candidate_type": "drug",
        "decision": "pinned",
        "tags": [],
        "rationale": "",
        "notes": "Fixture review notes",
        "changed_my_mind": "",
    }

    graph_status = page.locator("#workspace-graph-status")
    expect(graph_status).to_contain_text("3 nodes · 2 connections · researcher fixture-researcher")
    page.evaluate(
        """() => {
            if (!workspaceEvidenceNetwork) throw new Error('fixture graph was not initialized');
            workspaceEvidenceNetwork.emit('click', {nodes: ['candidate:drug-tofacitinib']});
        }"""
    )
    expect(page.locator("#workspace-graph-detail")).to_contain_text("Tofacitinib")
    expect(page.locator("#workspace-graph-detail")).to_contain_text("pinned")

    with page.expect_download() as download_info:
        page.get_by_role("button", name=re.compile("Review bundle")).click()
    download = download_info.value
    assert download.suggested_filename == "workspace-ew-browser-fixture-001-review.zip"
    assert Path(download.path()).read_bytes().startswith(b"PK")
