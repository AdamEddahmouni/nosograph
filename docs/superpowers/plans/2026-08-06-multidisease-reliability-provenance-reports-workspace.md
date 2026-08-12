# Multi-Disease Reliability, Provenance, Reports, and Workspace Implementation Plan

> **Status: Historical plan with partial completion.** Test-boundary, provenance, disease-aware report, dashboard, and validation work described here has landed in the current tree, but the document also contains future hardening and curation ideas that remain follow-up work. Do not treat unchecked items as a current runtime contract; use `README.md`, `docs/evidence-workspace.md`, and `docs/api-reference.md` for live behavior.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Original goal:** Make the existing seven-disease platform verifiable, reproducible, disease-aware in its reports, and pleasant to use through the existing Evidence Workspace dashboard.

**Architecture:** Preserve the current pipeline APIs and uncommitted work. First make the test boundary explicit so offline tests cannot accidentally run live integrations. Then introduce one small provenance contract used by workspace dossiers and report metadata, thread disease labels through report generators, and finally polish the already-present workspace dashboard without adding a new frontend framework or database migration. Each phase ends with focused verification and a code review.

**Tech Stack:** Python 3.10+, pytest, Ruff, Pydantic v2, FastAPI/Celery, existing vanilla HTML/CSS/JavaScript dashboard, SQLite workspace history, NetworkX.

## Global Constraints

- Do not discard, stage, overwrite, or reformat unrelated pre-existing working-tree changes.
- Default tests must not require live APIs, Redis, LLM credentials, or optional visualization packages.
- Preserve backwards-compatible defaults where existing public tests depend on them; new disease-aware paths must be explicit and validated.
- Reports must describe computational prioritization, not efficacy or medical advice.
- Every user-visible disease name and identifier must come from the request/config/result context, never a fixed SLE label.
- Provenance must retain source, native identifier, retrieval time, query/filter context, package/module version, and scoring/configuration inputs when available.
- Use existing dependencies and vanilla browser APIs; do not install packages.

---

## Phase 1: Full-suite reliability and deterministic test boundaries

### Task 1.1: Map the test suite and isolate external integrations

**Files:**
- Modify only the smallest necessary test/config files: `tests/conftest.py`, `pytest.ini`, `.github/workflows/test.yml`, `Makefile`.
- Test/inspect: all `tests/` files with `slow`, `integration`, subprocess, HTTP, Celery, or external API markers.

- [x] Collect baseline without changing code: `python -m pytest tests/ -m "not slow" -q --tb=line`; record exit code, failure count, and duration.
- [x] Collect collection/runtime data without live slow tests: `python -m pytest --collect-only -q`; identify tests incorrectly classified as unit.
- [x] Inspect `tests/conftest.py`, `pytest.ini`, CI workflow, and all tests that invoke external calls or subprocesses.
- [x] Keep live API tests under `slow`; mark any unmarked live/integration test explicitly rather than globally disabling it.
- [x] Add a deterministic CI command that excludes `slow` and runs the complete offline suite with a bounded per-command timeout in the workflow.
- [x] Add a separate CI job for `slow` tests with its existing extended timeout, preserving visibility without blocking the offline gate.
- [x] Run the offline suite again and compare failures against the baseline; do not claim full reliability until the full offline command exits zero.

### Task 1.2: Add a test-slice command for efficient diagnosis

**Files:**
- Modify: `Makefile`.
- Modify only if required: `pytest.ini`.

- [x] Add `test-fast` for `python -m pytest tests/ -m "not slow and not integration" -q --tb=line`.
- [x] Add `test-offline` for `python -m pytest tests/ -m "not slow" -q --tb=short`.
- [x] Add `test-slow` for `python -m pytest tests/ -m slow -v --tb=short`.
- [x] Keep existing targets backwards compatible and document that `test-offline` is the default CI reliability gate.
- [x] Run all three commands when practical; report any live/infrastructure limitation separately.

---

## Phase 2: Provenance and reproducibility contract

### Task 2.1: Define a reusable provenance metadata model

**Files:**
- Modify: `src/med_research/pipeline/evidence_workspace/schemas.py`.
- Create or modify: `src/med_research/pipeline/provenance.py` only if a shared module is justified by existing report callsites.
- Test: `tests/test_evidence_workspace_schemas.py`, new `tests/test_provenance.py` if needed.

- [x] Write failing tests for a normalized metadata payload containing `schema_version`, `run_id`, `disease_id`, package version, module name/version, source names, query/filter inputs, retrieval timestamps, cache/live mode, model information, and scoring/configuration inputs.
- [x] Implement a typed, JSON-safe provenance contract with stable key names and redaction of secrets/prompts.
- [x] Ensure timestamps are UTC ISO-8601 and lists/dicts are deterministic where order is not semantic.
- [x] Preserve existing `EvidenceDossier.manifest` JSON compatibility by nesting or merging the new metadata without deleting existing keys.
- [x] Add a deterministic fingerprint over normalized request/source/filter/configuration inputs; exclude run timestamps, random run IDs, secrets, and response bodies.
- [x] Run focused provenance/schema tests.

### Task 2.2: Populate workspace provenance end to end

**Files:**
- Modify: `src/med_research/pipeline/evidence_workspace/workspace.py`.
- Modify: `src/med_research/pipeline/evidence_workspace/report.py`.
- Modify: `src/med_research/web/services/workspace_store.py` only if stored summaries omit required metadata.
- Test: `tests/test_evidence_workspace.py`, `tests/test_evidence_workspace_report.py`, `tests/test_evidence_workspace_storage.py`.

- [x] Add tests asserting dossier provenance records disease, normalized question, sources, date filters, candidate type, evidence limit, LLM requested/status/model, package/module versions, search terms, source counts, cache/live mode, and ranking configuration.
- [x] Populate the manifest from the normalized request and adapter/source statuses; never write secrets or full LLM prompts.
- [x] Ensure fixture-backed runs with the same inputs produce the same reproducibility fingerprint even when run IDs/timestamps differ.
- [x] Render a concise provenance/reproducibility section in JSON and HTML, including source status and ranking heuristic disclosure.
- [x] Verify stored and reloaded dossiers preserve the exact manifest.

### Task 2.3: Add provenance metadata to report generators without rewriting report algorithms

**Files:**
- Modify only report entrypoints that are currently called by disease-aware CLI/web paths: `src/med_research/pipeline/adverse_events/report.py`, `clinical_trials/report.py`, `literature_mining/report.py`, `drug_repurposing/report.py`, `bioinformatics/report.py`, `virtual_screening/report.py`, `car_t_predictor/report.py`, `biomarker_discovery/report.py`.
- Test: existing report tests plus a focused provenance/report metadata test module.

- [x] Add optional keyword-only `disease_id`, `provenance`, or a normalized metadata object to each entrypoint while retaining existing positional call compatibility.
- [x] Include disease, generated-at time, source/cache mode, and scoring/configuration metadata in report context/footer where available.
- [x] Ensure report calls from CLI/services pass the active disease and metadata; do not infer a non-SLE disease from result labels.
- [x] Add tests that generate at least one non-SLE report and assert its title, disease label, and provenance block.

---

## Phase 3: Fully disease-aware report content

### Task 3.1: Centralize display labels and disease context

**Files:**
- Modify: `src/med_research/diseases/base.py` only if a display-label helper is missing.
- Create/modify a small helper module such as `src/med_research/web/report_context.py` or `src/med_research/pipeline/reporting.py` after checking existing conventions.
- Test: new `tests/test_report_context.py`.

- [x] Write tests for all seven disease IDs: stable short label, full profile name, URL-safe ID, and escaped display values.
- [x] Implement one helper that accepts `disease_id` and returns profile-derived display context; use `Disease` discovery/config rather than a hardcoded SLE map for report text.
- [x] Keep `SLE` as the default only for backwards-compatible CLI defaults; never use it when an explicit non-SLE disease is supplied.

### Task 3.2: Replace SLE-only labels and semantic keys in reports/templates

**Files:**
- Modify report modules/templates identified by searches: bioinformatics, adverse events, virtual screening, biomarker discovery, CAR-T, drug synergy, semantic search, and any other report with static SLE/Lupus copy.
- Modify data/result keys only when compatibility aliases can be retained.
- Test: existing report tests and new parameterized disease-label tests.

- [x] Replace visible labels such as “Lupus Genes,” “SLE/Lupus studies,” “Lupus Seed Genes,” “drug-induced lupus,” and static disease titles with context-derived wording.
- [x] Replace internal report fallback lookups such as `lupus_symptom_overlap_score` with disease-neutral keys first, retaining legacy aliases for old cached results.
- [x] Replace hardcoded examples in user-facing UI copy with the active disease or a neutral example when no disease context exists.
- [x] Preserve scientifically meaningful disease-specific scoring dimensions by labeling them as configured heuristics, not pretending they are universal.
- [x] Add tests covering report generation for RA, MS, SS, SSc, T1D, and IBD with assertions that no unrelated SLE/Lupus labels appear in visible report text.

### Task 3.3: Thread disease context through remaining report callsites

**Files:**
- Modify: `src/med_research/cli.py`, relevant web services/tasks/routers, and pipeline `main()` wrappers found by reference search.
- Test: CLI, web API, and report tests.

- [x] Search every modified report symbol and update all explicit references.
- [x] Ensure report filenames/output locations do not overwrite another disease's report when disease-specific persistence is expected; preserve legacy SLE paths if compatibility requires it.
- [x] Verify CLI and web calls for each supported disease pass the same disease ID to computation and rendering.

---

## Phase 4: Evidence Workspace UI completion and browser verification

### Task 4.1: Fix workspace request state and accessible form behavior

**Files:**
- Modify: `src/med_research/web/static/index.html`, `src/med_research/web/static/js/dashboard.js`, `src/med_research/web/static/css/dashboard.css`.
- Test: `tests/test_evidence_workspace_dashboard.py`; new browser test only if the repository's browser tooling is configured.

- [x] Write tests for defaulting the workspace disease to the selected disease, serializing multi-select sources as an array accepted by the API, disabling duplicate submission while a workspace job is active, and restoring controls after terminal job state.
- [x] Fix the current workspace job invocation so it passes `params` instead of an undefined variable and uses the JSON body expected by `/api/jobs/workspace`.
- [x] Add clear loading/progress/success/error/empty states with `aria-live`, visible keyboard focus, and non-color-only status indicators.
- [x] Escape all dynamic values inserted into workspace result/history/trend markup, including inline handler identifiers or replace inline handlers with event delegation where practical.
- [x] Make the history, compare, export, and trend controls work for zero, one, and many saved runs.

### Task 4.2: Polish responsive visual hierarchy and research workflow

**Files:**
- Modify: `src/med_research/web/static/index.html`, `src/med_research/web/static/css/dashboard.css`, `src/med_research/web/static/js/dashboard.js`.

- [x] Use a focused visual system for the workspace: research-question-first layout, source-status chips, compact evidence-quality summary, candidate ranking panels, and provenance disclosure.
- [x] Add responsive layouts for narrow screens, readable tables/scroll regions, reduced-motion support, and visible focus rings.
- [x] Add a “why this ranked” interaction that reveals component scores, supporting/contradicting claims, citations, and graph-path status without forcing a new page.
- [x] Add a copyable run fingerprint and a clear “research use only” notice near the run controls and results.
- [x] Keep the broader dashboard functional and avoid unrelated visual rewrites.

### Task 4.3: Browser-level smoke verification

**Files:**
- Modify only if verification finds a concrete defect.
- Test: `tests/test_evidence_workspace_dashboard.py` and browser/preview checks.

- [x] Start the existing web app using the repository's documented command and an unused local port; do not kill other listeners.
- [x] Verify disease selection, workspace form submission shape, progress state, result rendering, history open/delete/compare, JSON download, HTML open, and trend controls with fixture/mocked responses where possible.
- [x] Capture console/network errors and fix only defects introduced by this work.
- [x] Respect reduced motion and keyboard navigation in the verification pass.

---

## Final verification and review gate

- [x] Run focused tests for each changed subsystem.
- [x] Run `python -m compileall -q src/med_research`.
- [x] Run `python -m ruff check` on changed source/tests; distinguish pre-existing unrelated findings.
- [x] Run `python -m pytest tests/ -m "not slow" -q --tb=line` with a fresh timeout and record exact results.
- [x] Run `python -m pytest tests/test_evidence_workspace*.py tests/test_multidisease_reliability.py -q`.
- [x] Run `git diff --check` and inspect `git diff --stat` plus targeted diffs; do not include unrelated initial working-tree changes in any final accounting.
- [x] Spawn a code reviewer to inspect reliability boundaries, provenance completeness, disease labels, UI behavior, and compatibility.
- [x] Fix verified review findings and rerun affected checks.
