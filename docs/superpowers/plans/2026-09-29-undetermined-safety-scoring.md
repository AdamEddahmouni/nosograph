# Undetermined Safety Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Prevent drugs explicitly classified as `undetermined_risk` from receiving numeric safety scores, while preserving catalog visibility and correctly excluding them from rankings and numeric summaries.

**Architecture:** Derive undetermined drug identifiers from the active disease's own adverse-event payload during profile materialization. Carry `score_status` and nullable score dimensions through existing result contracts, summary, service, and Pydantic model boundaries; make CLI and HTML output status-aware and show counts. Keep source disease files, tier classification, and existing determinate scoring untouched.

**Tech Stack:** Python 3.11+, TypedDict, Pydantic 2, FastAPI, Jinja2, vanilla JavaScript, pytest, Ruff, mypy.

## Global Constraints

- Do not edit or regenerate disease `config.py` or `data/adverse_events.json` files.
- Do not change classification heuristics or assign any conservative substitute score.
- Do not commit or deploy as part of this task.
- Preserve the existing staged index; make this implementation unstaged and do not alter `.pytest_basetemp/` scratch data.
- Retain every catalog drug in returned profiles and reports; unknown scores are `None`, never zero or a fabricated fallback.
- Keep determinate profile score behavior unchanged.

---

## File Structure

- `src/med_research/pipeline/adverse_events/profiler.py`: materialize tier status; skip scoring dimensions for insufficient evidence; sort scored rows first; compute null-safe summary; make CLI summary null-safe.
- `src/med_research/pipeline/results.py`: declare nullable score dimensions/composite and explicit status in the adverse-event result contract.
- `src/med_research/web/models/adverse_events.py`: expose nullable score fields, status, and scored/unscored counts at the Pydantic API seam.
- `src/med_research/web/services/adverse_events_service.py`: relay new summary fields and preserve status on individual result serialization.
- `src/med_research/web/static/js/dashboard.js`: include unscored count and safely render a null average.
- `src/med_research/pipeline/adverse_events/report.py` and `src/med_research/templates/reports/adverse_events.html`: summarize scored/unscored counts, rank/highlight scored rows only, and retain all drugs as table rows with explicit insufficient-evidence labels.
- `src/med_research/cli.py`: print status instead of attempting numeric formatting for an insufficient-evidence single-drug result.
- `tests/test_adverse_events.py`, `tests/test_adverse_events_multidisease.py`, and `tests/test_report_provenance.py`: regression coverage for scores, summaries, API serialization, CLI display, and reports. Add tests in these existing focused files rather than creating parallel suites.

## Task 1: Lock the domain behavior with failing regression tests

**Files:**
- Modify: `tests/test_adverse_events.py`
- Modify: `tests/test_adverse_events_multidisease.py`

**Interfaces:**
- Consumes: `load_profiles(disease_id)`, `compute_adverse_event_score(profile, disease_id)`, `score_all_drugs(disease_id)`, `get_safety_summary(disease_id, results)`.
- Produces: `score_status` equal to `"insufficient_evidence"` or `"scored"`; for insufficient profiles, every numeric score key is `None`; summary keys `scored_drugs` and `unscored_drugs`, with null average and extrema and empty rank names when no rows are scored.

- [x] **Step 1: Add unknown-tier and determinate-tier assertions**

In `tests/test_adverse_events_multidisease.py`, import `compute_adverse_event_score` and add a test using `load_profiles("cardiac_arrest")`. Locate catalog drugs by case-insensitive names `amiodarone` and `rocuronium`; assert both have `score_status == "insufficient_evidence"`, retain source/limitations, and have `None` for `disease_symptom_overlap_score`, `disease_overlap_score`, `lupus_symptom_overlap_score`, `severity_burden_score`, `chronic_use_safety_score`, `disease_specific_risk_score`, `dil_risk_score`, and `composite_safety_score`. Also assert an explicit determinate entry remains `"scored"` and numeric. If the cardiac arrest file does not have a suitable determinate explicit drug, use SLE `hydroxychloroquine` for the determinate assertion.

Add a summary test whose input contains two scored records with composite scores `8.0` and `4.0`, plus one insufficient record with null scores; assert total=3, scored=2, unscored=1, average=6.0, safest/riskiest names and values only reference scored records. Add an all-unscored case asserting average and extrema are `None` and rank names are empty.

- [x] **Step 2: Run only the new tests and verify they fail for the missing behavior**

Run: `.venv/Scripts/python.exe -m pytest tests/test_adverse_events_multidisease.py tests/test_adverse_events.py -k 'undetermined or summary_excludes_unscored or summary_with_no_scored' -q -n 0 --basetemp=.pytest-tmp --tb=short`

Expected: failures because tier-derived status is absent, score dimensions are numeric defaults, and summary counts/null semantics are missing. Correct any test setup errors before implementation.

## Task 2: Implement status-aware profile and scoring contracts

**Files:**
- Modify: `src/med_research/pipeline/adverse_events/profiler.py`
- Modify: `src/med_research/pipeline/results.py`
- Modify: `tests/test_adverse_events_multidisease.py`

**Interfaces:**
- Consumes: disease payload `drug_safety_tiers.undetermined_risk`, which may hold labels or structured entries; catalog IDs/names materialized by `load_profiles`.
- Produces: every profile carries `score_status`; `compute_adverse_event_score` short-circuits insufficient profiles, preserving descriptive/provenance fields and setting all score keys to `None`; `score_all_drugs` sorts scored rows by descending score before insufficient rows; `AdverseEventScore` types nullable score fields correctly.

> Implementation note: SLE's curated legacy profiles are also matched by exact normalized `drug_id` or `drug_name` tokens if an SLE payload declares undetermined entries; determinate legacy SLE profiles remain `scored` otherwise.

- [x] **Step 1: Add exact payload-driven status tests before changing the loader**

Extend the Task 1 tests to assert the two unknown records are emitted by `score_all_drugs("cardiac_arrest")`, both have `None` scores, and determinate entries are still ordered by descending numeric score ahead of the unscored tail.

- [x] **Step 2: Verify the scorer regression test fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_adverse_events_multidisease.py -k undetermined -q -n 0 --basetemp=.pytest-tmp --tb=short`

Expected: failure because no profile status is yet materialized and there is no scorer short circuit.

- [x] **Step 3: Derive matching unknown-tier identifiers and names from the disease payload**

Within `load_profiles`, read `payload.get("drug_safety_tiers", {}).get("undetermined_risk", [])`. Normalize strings and structured mapping entries to a set of lowercase tokens using available `drug_id`, `id`, `name`, or `drug` values. Match these tokens against each catalog drug's ID and name; mark matches `score_status="insufficient_evidence"`, and all other materialized profiles `score_status="scored"`. Do not change values from profile JSON or defaults.

At the start of `compute_adverse_event_score`, build the usual shared result metadata, then if status is insufficient return that metadata with the eight score fields set to `None`; preserve existing adverse-event/provenance metadata and counts. On the regular branch include `score_status="scored"`. Sort `score_all_drugs` by `(score_status == "scored", composite_score or -1)` descending so numeric results remain ranked and unknown rows remain visible at the end.

In `AdverseEventScore`, type each of the eight nullable numeric fields `float | None` and add `score_status: str`.

- [x] **Step 4: Verify domain tests pass and nearby existing behavior remains intact**

Run: `.venv/Scripts/python.exe -m pytest tests/test_adverse_events.py tests/test_adverse_events_multidisease.py -q -n 0 --basetemp=.pytest-tmp --tb=short`

Expected: all focused scorer tests pass; existing determinate score ranges remain numeric. Update the previous multi-disease test to require `score_status` on every result and apply the 0–10 bound only to `"scored"` results, while requiring every insufficient composite to be `None`.

## Task 3: Make summaries, API model, and dashboard null-safe

**Files:**
- Modify: `src/med_research/pipeline/adverse_events/profiler.py`
- Modify: `src/med_research/web/services/adverse_events_service.py`
- Modify: `src/med_research/web/models/adverse_events.py`
- Modify: `src/med_research/web/static/js/dashboard.js`
- Modify: `tests/test_adverse_events.py`
- Modify: `tests/test_adverse_events_multidisease.py`

**Interfaces:**
- Consumes: rows with `score_status`, nullable scores, and source profile metadata.
- Produces: summary counts `scored_drugs`, `unscored_drugs`; average and safest/riskiest scores are nullable; rankings consider only `score_status == "scored"`; risk and DIL counts only inspect scored rows; Pydantic contracts allow nullable numbers and expose status/counts.

- [x] **Step 1: Add failing service and schema assertions**

Extend service tests for `run_safety_profiling(disease_id="cardiac_arrest")`: verify counts, at least one insufficient profile, null values, and numeric summary/ranking unaffected by such records. In the single-drug service test, query an unknown-tier catalog drug and assert its status and null composite. Add a direct `SafetySummaryResponse.model_validate(...)` test for an insufficient profile and a summary with null score statistics.

- [x] **Step 2: Run the API-focused regression tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_adverse_events.py tests/test_adverse_events_multidisease.py -k 'safety_profiling or safety_summary or response_model' -q -n 0 --basetemp=.pytest-tmp --tb=short`

Expected: initial failure on missing summary keys and Pydantic float validation for null fields.

- [x] **Step 3: Implement null-safe summary, service fields, and model types**

In `get_safety_summary`, partition scored and unscored rows by explicit status. Calculate average/min/max using scored composites only; if none are scored use `None` for average and numeric extrema and `""` for safest/riskiest names. Keep `total_drugs` as all rows and add `scored_drugs` and `unscored_drugs`. Restrict dimension-dependent risk counts to scored rows. Relay new count fields from service. In models, make nullable all relevant score fields (including aliases), summary numeric fields, and add `score_status`, `scored_drugs`, `unscored_drugs`. In dashboard summary, use a readable em dash for null averages and add an `Unscored (insufficient evidence)` count.

- [x] **Step 4: Verify service and API tests pass**

Run the Task 3 test command again. Expected: all selected tests pass with valid API data for both numeric and null summaries.

## Task 4: Update report and CLI presentation

**Files:**
- Modify: `src/med_research/pipeline/adverse_events/report.py`
- Modify: `src/med_research/templates/reports/adverse_events.html`
- Modify: `src/med_research/pipeline/adverse_events/profiler.py`
- Modify: `src/med_research/cli.py`
- Modify: `tests/test_adverse_events.py`
- Modify: `tests/test_report_provenance.py`

**Interfaces:**
- Consumes: sorted full results where scored entries precede `insufficient_evidence` entries.
- Produces: CLI and HTML rows retain every result; only scored entries appear in rankings, highlights, averages, and extrema; unscored entries use exact text `Insufficient evidence.` and no numeric score formatting.

- [x] **Step 1: Add failing report and CLI rendering tests**

Create a report fixture with one scored result and one insufficient result with all numeric scores set to `None`; call `generate_html_report`, read and delete the generated report using the existing `report_dir` test fixture if available (otherwise follow `test_generate_html_report` cleanup), and assert the page includes both drugs, `Insufficient evidence`, scored/unscored counts, and no `None/10` strings. Extend the CLI single-drug test to run the unknown cardiac-arrest drug and assert the logged output contains `Insufficient evidence` and does not contain `None/10`. Update the provenance report test so it continues to validate metadata on a determinate one-row report.

- [x] **Step 2: Verify report and CLI tests fail before code changes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_adverse_events.py tests/test_report_provenance.py -k 'report or safety_cli_single_drug' -q -n 0 --basetemp=.pytest-tmp --tb=short`

Expected: report formatting raises on null and CLI output lacks explicit status.

- [x] **Step 3: Implement status-aware rendering**

In the report generator, derive `scored_results`; compute average or `None` from those; build top-10 highlights only from scored rows; construct the full table iterating all rows, rendering `Insufficient evidence` for score/dimension cells of unscored rows and numeric values only for scored rows. Provide total, scored, unscored, and average template context values. Update template stats to include an insufficient-evidence count and render average as `—` when null; label the table status/score column in a way that distinguishes unscored rows. Change the report empty guard to reject only no results (and continue rejecting blocked results), not an all-insufficient result set.

In `print_analysis`, rank only scored results, report scored/unscored counts, display a null average as `—`, render no-scored rank summaries as `Insufficient evidence`, and never apply numeric formatting to null. In CLI single drug handling, branch on `score_status` before numeric dimension logs and print `Insufficient evidence.` for the score status.

- [x] **Step 4: Run report, CLI, and provenance tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_adverse_events.py tests/test_report_provenance.py -k 'adverse_events or report or safety_cli_single_drug' -q -n 0 --basetemp=.pytest-tmp --tb=short`

Expected: report output and provenance checks pass, including mixed scored/unscored rows.

## Task 5: Full focused verification and staged-state protection

**Files:**
- Review only: all files listed above plus this plan.

- [x] **Step 1: Run complete focused regression suite**

Run: `.venv/Scripts/python.exe -m pytest tests/test_adverse_events.py tests/test_adverse_events_multidisease.py tests/test_report_provenance.py -q -n 0 --basetemp=.pytest-tmp --tb=short`

Expected: all adverse-event, disease-scope, service, report, CLI, and provenance tests pass.

- [x] **Step 2: Run lint, format check, and project typecheck**

Run: `.venv/Scripts/python.exe -m ruff check src/med_research/pipeline/adverse_events/profiler.py src/med_research/pipeline/results.py src/med_research/web/services/adverse_events_service.py src/med_research/web/models/adverse_events.py src/med_research/cli.py tests/test_adverse_events.py tests/test_adverse_events_multidisease.py tests/test_report_provenance.py`

Run: `.venv/Scripts/python.exe -m ruff format --check src/med_research/pipeline/adverse_events/profiler.py src/med_research/pipeline/results.py src/med_research/web/services/adverse_events_service.py src/med_research/web/models/adverse_events.py src/med_research/cli.py tests/test_adverse_events.py tests/test_adverse_events_multidisease.py tests/test_report_provenance.py`

Run: `make typecheck` when `make` is available; otherwise invoke the venv's mypy on the exact Makefile typecheck list and report any environmental limitation. Expected: no mypy errors for the nullable result contract and its consumers.

- [x] **Step 3: Review only unstaged changes and confirm no disease data, stage/index or scratch changes**

Inspect unstaged diff for the implementation and plan, confirm no disease `config.py` / `data/adverse_events.json` files changed, confirm staged changes remain untouched, and do not stage or commit anything. No deployment command is part of this task.

Verification notes: The focused command completed with `73 passed`. Ruff check, Ruff format check, and mypy all passed; `make typecheck` could not run because `make` is unavailable in this shell, so the exact Makefile mypy source-file list was invoked directly and completed with `Success: no issues found in 165 source files`. The report template and JS dashboard are checked by rendering/pytest and existing static-contract tests, respectively; Ruff is applied only to Python files. Staged changes were not staged, reset, or committed. Pre-existing staged modifications in `src/med_research/pipeline/results.py` and other shared paths remain in the index; this work added only unstaged changes to those files.
