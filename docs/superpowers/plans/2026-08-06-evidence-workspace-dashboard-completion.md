# Evidence Workspace Dashboard Completion Implementation Plan

> **Status: Implemented (historical plan).** This plan records the work completed on 2026-08-06. The live usage and API contract are maintained in `docs/evidence-workspace.md` and `docs/api-reference.md`; checklist items below are retained as an implementation record rather than an active task queue.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with review checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the fixture-backed Evidence-to-Hypothesis Workspace flow with reliable dashboard state, explainable results, independent source outcomes, provenance visibility, and cited exports.

**Architecture:** Preserve the existing evidence workspace schemas, source adapters, orchestration, SQLite store, and Celery job contract. Add narrow frontend rendering/state fixes and fixture-backed regression tests; live adapters remain available but are never required by the default test path.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, FastAPI/Celery, vanilla HTML/CSS/JavaScript, NetworkX, existing project dependencies only.

## Global Constraints

- Fixture-backed default tests must not access live network services, Redis, Celery workers, or LLM credentials.
- Preserve existing public workspace schemas and backwards-compatible dashboard behavior.
- Do not change the ranking algorithm; expose existing component scores and claim/citation references.
- Source failures are isolated and must remain visible beside successful sources.
- Never render unescaped API-provided text or unsafe citation URLs.
- JSON/HTML exports consume the already-built dossier; the browser must not recompute rankings.
- Do not overwrite unrelated pre-existing working-tree changes.
- Do not commit unless explicitly requested.

---

### Task 1: Lock the fixture-backed acceptance contract

**Files:**
- Modify: `tests/test_evidence_workspace_dashboard.py`
- Modify: `tests/test_evidence_workspace.py`
- Inspect: `src/med_research/pipeline/evidence_workspace/*`, `src/med_research/web/tasks/analysis_tasks.py`

**Interfaces:**
- Use `run_workspace(request, sources=..., graph=...) -> EvidenceDossier`.
- Use `task_run_workspace.run(...) -> {"dossier": dict, "html": str}`.
- Keep fixtures injectable through `PubMedSource`, `ClinicalTrialsSource`, and a NetworkX graph.

- [ ] Add a fixture-backed acceptance test with one PubMed record, one ClinicalTrials.gov record, one supporting claim, one contradictory claim, one drug ranking, one target ranking, one found graph path, and one no-path explanation.
- [ ] Assert every claim has at least one `evidence_id`, every citation native ID is retained, source statuses are independent, and the manifest contains a non-empty provenance fingerprint.
- [ ] Add a test that serializes the task result with `json.dumps` and asserts generated HTML is present without making a network request.
- [ ] Run `python -m pytest tests/test_evidence_workspace.py tests/test_evidence_workspace_dashboard.py -q`; expected new assertions fail only where the current fixture payload lacks the required acceptance detail.
- [ ] Adjust only fixtures/assertions needed to express the approved contract; do not alter production code in this task.
- [ ] Rerun the focused tests and record the exact failing behavior before implementation.

### Task 2: Make workspace submission state terminal-aware

**Files:**
- Modify: `src/med_research/web/static/js/dashboard.js`
- Test: `tests/test_evidence_workspace_dashboard.py`

**Interfaces:**
- `submitWorkspace(event)` remains the inline form handler.
- `streamJob(module, resultEl, params)` remains the async job submission/streaming function.
- Add a small state helper such as `setWorkspaceSubmissionState(state)` without changing the backend API.

- [ ] Add source-level contract assertions for a workspace submission state helper, `streamJob(...).finally`/terminal cleanup, duplicate-submit guard, `aria-busy`, and re-enable-on-failure behavior.
- [ ] Run the dashboard test and verify the new assertions fail against the current script.
- [ ] Add `let workspaceSubmissionActive = false` and a `setWorkspaceSubmissionState` helper that updates the submit button, form `aria-busy`, result `aria-busy`, and an optional status node.
- [ ] Guard `submitWorkspace` when a run is already active; validate that at least one source is selected before submission.
- [ ] Keep the submit button disabled until the stream/poll reaches success, failure, timeout, or stream error. Do not re-enable it in an outer `finally` that executes immediately after starting `streamJob`.
- [ ] Make `streamJob` return a promise that resolves/rejects after the job reaches a terminal state, while retaining existing rendering behavior for other modules.
- [ ] Run `python -m pytest tests/test_evidence_workspace_dashboard.py -q` and confirm green.

### Task 3: Render source statuses and provenance independently

**Files:**
- Modify: `src/med_research/web/static/index.html` only if a status/provenance anchor is missing.
- Modify: `src/med_research/web/static/js/dashboard.js`
- Modify: `src/med_research/web/static/css/dashboard.css`
- Test: `tests/test_evidence_workspace_dashboard.py`

**Interfaces:**
- Consume `dossier.source_statuses`, `dossier.manifest.provenance`, `dossier.manifest.fingerprint`, `dossier.warnings`, and `dossier.limitations`.
- Keep `renderWorkspaceResult(element, payload)` as the single dossier presentation entrypoint.

- [ ] Add assertions for independent PubMed/ClinicalTrials status labels, fingerprint, cache/live mode, warnings, and limitations.
- [ ] Run the dashboard test and verify the assertions fail before rendering changes.
- [ ] Render each requested source status as its own escaped chip, including status, record count, retrieval mode, and warning text when present; do not collapse source errors into a global failure.
- [ ] Render a provenance panel with run ID, disease, question, fingerprint, retrieval mode, source count, and a copyable fingerprint control with a safe fallback when clipboard access is unavailable.
- [ ] Render warnings and limitations in separate sections and add responsive/focus-visible styles for the new controls.
- [ ] Escape every dynamic text value and avoid injecting untrusted values into executable inline attributes.
- [ ] Run focused dashboard tests and existing report tests.

### Task 4: Add “why this ranked” and provenance-backed claim views

**Files:**
- Modify: `src/med_research/web/static/js/dashboard.js`
- Modify: `src/med_research/web/static/css/dashboard.css`
- Test: `tests/test_evidence_workspace_dashboard.py`

**Interfaces:**
- Consume `RankedCandidate.component_scores`, `supporting_claim_ids`, `contradicting_claim_ids`, `citation_ids`, and `graph_explanation_ids`.
- Consume `Claim.citations`, `Claim.supporting_snippet`, `Claim.evidence_ids`, and `GraphExplanation` fields.

- [ ] Add fixture assertions requiring visible strings for “Why this ranked”, support, contradiction, component scores, PMID/NCT identifiers, and graph path/no-path output.
- [ ] Run the dashboard test and verify it fails before implementation.
- [ ] Add renderer helpers for candidate explanations, score components, claim lookup, citation lookup, and safe HTTP(S) citation links.
- [ ] Replace the current one-line ranking explanation with an expandable `<details>` panel showing bounded component scores and linked support/contradiction claims.
- [ ] Show snippets, confidence, evidence IDs, citation titles, source identifiers, and safe links. If a claim ID cannot be resolved, show a neutral missing-provenance notice instead of fabricating a citation.
- [ ] Keep evidence and claim sections compact by limiting the initial visible rows and allowing expansion.
- [ ] Run focused dashboard tests and confirm green.

### Task 5: Verify exact JSON/HTML exports and fixture E2E behavior

**Files:**
- Modify: `tests/test_evidence_workspace_report.py` only if a missing acceptance assertion is discovered.
- Modify: `tests/test_evidence_workspace_dashboard.py`
- Modify production files only for verified defects found by tests.

**Interfaces:**
- `downloadWorkspaceJson()` downloads `window.lastWorkspaceDossier`.
- `openWorkspaceHtml()` opens `window.lastWorkspaceHtml`.
- Backend `dossier_to_json` and `render_html` remain the canonical export implementations.

- [ ] Add assertions that dashboard script stores both dossier and generated HTML, has JSON download behavior, has HTML open behavior, and exposes the fingerprint in the rendered result.
- [ ] Add/retain a Python fixture E2E test asserting JSON round-trip preserves native source IDs, claim evidence IDs, citation URLs, manifest fingerprint, and HTML disclaimer.
- [ ] Run `python -m pytest tests/test_evidence_workspace*.py -q`; expected output is all focused tests passing.
- [ ] Run `python -m compileall -q src/med_research`.
- [ ] Run `python -m ruff check src/med_research/pipeline/evidence_workspace tests/test_evidence_workspace*.py` and `python -m ruff format --check src/med_research/pipeline/evidence_workspace tests/test_evidence_workspace*.py`.
- [ ] Run `git diff --check` and inspect targeted diffs; leave unrelated working-tree files untouched.

### Task 6: Browser-level verification and review gate

**Files:**
- Modify only if browser verification identifies a concrete defect.
- Review: all files changed by Tasks 1–5.

**Interfaces:**
- Use the existing dashboard served by `med_research.web.main:app`.
- Use fixture/mocked responses where possible; do not turn the smoke test into a live-source test.

- [ ] Start the existing local app only if no conflicting listener exists; use an unused loopback port.
- [ ] Verify keyboard submission, disabled duplicate-submit state, progress state, terminal recovery, source chips, ranking explanation expansion, provenance fingerprint, JSON download, and HTML opening.
- [ ] Capture browser console/network errors and fix only introduced defects.
- [ ] Spawn `code-reviewer-luna` to review provenance guarantees, escaping, failure isolation, and state lifecycle.
- [ ] Run the focused workspace suite and relevant web tests again after review fixes.
- [ ] Run the final regression command `python -m pytest tests/test_evidence_workspace*.py tests/test_web_api.py -q --tb=short` and report exact results.
