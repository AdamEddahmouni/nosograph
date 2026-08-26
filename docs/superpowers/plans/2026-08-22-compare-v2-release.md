# Compare V2 v0.2.0 Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate the Compare V2 audit, verify Milestone 1, and publish the merged result as signed release v0.2.0.

**Architecture:** Keep comparison semantics at algorithm version `2.0.0` while adding an explicit `2.0` result-schema contract to persisted payloads and deterministic fingerprints. Preserve all conflicting claim provenance, test the real FastAPI/browser seam, and update canonical current-release metadata without rewriting historical release records.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, SQLite-backed `BiomedicalRepository`, vanilla JavaScript/CSS, pytest, Playwright, Ruff, MkDocs, GitHub Actions, GitHub Releases.

## Global Constraints

- Work on `codex/fix-dependabot-redis-constraint`; merge through a pull request to `master`.
- Do not force-push, bypass hooks, push directly to `master`, or tag a feature-branch commit.
- Keep Compare algorithm ID `nosograph-compare-v2` and algorithm version `2.0.0`.
- Use result schema version `2.0` independently of application and algorithm versions.
- Preserve historical v0.1.0 release records and DOI claims; do not invent a v0.2.0 Zenodo DOI.
- Use `.venv\Scripts\python.exe` and repository Makefile-equivalent checks on Windows.

---

### Task 1: Version the persisted Compare result contract

**Files:**
- Modify: `src/med_research/biomed/nosograph_compare/models.py`
- Modify: `src/med_research/biomed/nosograph_compare/service.py`
- Modify: `tests/biomed/nosograph_compare/test_v2_engine.py`
- Modify: `tests/fixtures/golden/nosograph_compare_v2.json`

**Interfaces:**
- Produces: `COMPARE_RESULT_SCHEMA_VERSION = "2.0"`
- Produces: `CompareV2Result.result_schema_version: str`
- Consumes: `ResearchRunCreate.parameters`, which participates in deterministic run fingerprinting.

- [ ] **Step 1: Write the failing schema and replay tests**

Add assertions that a new result exposes `result_schema_version == "2.0"`, that the persisted run parameters contain the same value, and that changing the module contract constant before a second identical request yields a different run ID. Keep the existing identical-input replay assertion.

```python
assert first.result_schema_version == "2.0"
run = compare_v2_repository.get_research_run(first.run_id)
assert run is not None
assert run.parameters["result_schema_version"] == "2.0"
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/biomed/nosograph_compare/test_v2_engine.py -n 0 -q --basetemp=.audit-pytest-schema -p no:cacheprovider`

Expected: FAIL because the model and payload do not expose `result_schema_version`.

- [ ] **Step 3: Implement the result contract boundary**

Define the constant in `models.py`, add the field to `CompareV2Result`, include it in `claim_set_fingerprint`, `ResearchRunCreate.parameters`, and the persisted result payload, and deserialize absent historical values as `"1.0"`.

```python
COMPARE_RESULT_SCHEMA_VERSION = "2.0"

class CompareV2Result(BaseModel):
    result_schema_version: str = COMPARE_RESULT_SCHEMA_VERSION
```

- [ ] **Step 4: Refresh the golden response and verify GREEN**

Run the focused test with `UPDATE_GOLDEN=1` only if the fixture helper supports it; otherwise update the single new canonical JSON field with `apply_patch`. Re-run the command from Step 2 and expect all tests to pass.

### Task 2: Preserve complete conflict provenance

**Files:**
- Modify: `src/med_research/biomed/nosograph_compare/engine.py`
- Modify: `tests/biomed/nosograph_compare/test_v2_engine.py`
- Modify: `tests/fixtures/golden/nosograph_compare_v2.json`

**Interfaces:**
- Produces: deterministic `EntityStateRow.claim_ids_by_condition` containing every assertion that establishes a conflict.

- [ ] **Step 1: Change the existing conflict assertion to require both directions**

```python
qualifiers = [
    compare_v2_repository.get_claim_by_id(claim_id).claim.qualifiers
    for claim_id in conflict_claims
]
assert any(item.get("negated") is True for item in qualifiers)
assert any(item.get("negated") is not True for item in qualifiers)
```

- [ ] **Step 2: Run the one test and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/biomed/nosograph_compare/test_v2_engine.py::test_compare_many_partitions_memberships_and_preserves_absence_semantics -n 0 -q --basetemp=.audit-pytest-conflict -p no:cacheprovider`

Expected: FAIL because PRESENT currently selects only positive claim IDs.

- [ ] **Step 3: Merge positive and negated IDs only for conflicting rows**

Build the row claim list from both maps when `positive and negated`; otherwise retain the state-specific map. Deduplicate and sort with `key=str`.

- [ ] **Step 4: Re-run the focused test and full Compare engine file**

Expected: PASS with deterministic claim ordering and updated golden data.

### Task 3: Close accessibility findings

**Files:**
- Modify: `src/med_research/web/static/js/dashboard.js`
- Modify: `src/med_research/web/static/css/dashboard.css`
- Modify: `tests/web/test_universal_comparison_dashboard.py`

**Interfaces:**
- Produces: named comparison regions, semantic panel headings, scoped column headers, and `.condition-comparison-number` tabular numerals.

- [ ] **Step 1: Add failing static-contract assertions**

Require generated markup to contain `<h3`, `aria-labelledby`, `scope="col"`, and `condition-comparison-number`; require CSS to contain `font-variant-numeric: tabular-nums`.

- [ ] **Step 2: Run the dashboard static tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/web/test_universal_comparison_dashboard.py -n 0 -q --basetemp=.audit-pytest-a11y -p no:cacheprovider`

- [ ] **Step 3: Implement minimal semantic markup and numeric styling**

Use stable heading IDs, point each panel section at its heading with `aria-labelledby`, add `scope="col"` to generated table headers, and apply the numeric class only to coverage counts.

- [ ] **Step 4: Re-run the dashboard static tests**

Expected: PASS.

### Task 4: Test the browser-to-FastAPI comparison seam

**Files:**
- Modify: `tests/test_evidence_explorer_ui.py`
- Reuse: `tests/biomed/nosograph_compare/conftest.py`
- Reuse: `src/med_research/web/main.py`

**Interfaces:**
- Produces: a Playwright test whose Compare POST reaches the actual FastAPI router and service.

- [ ] **Step 1: Add a live application fixture and failing smoke scenario**

Start a thread-based local Uvicorn server on an ephemeral loopback port. Override `get_biomedical_repository` with a deterministic temporary repository containing two conditions and shared phenotype data. Do not register `page.route` for `/api/v1/nosograph/comparisons`.

The scenario selects two conditions, clicks Compare, waits for the POST response, asserts HTTP 200 and `algorithm_version == "2.0.0"`, then asserts the Shared panel renders the shared phenotype.

- [ ] **Step 2: Run only the live seam scenario and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_evidence_explorer_ui.py -k live_compare_api -n 0 -q --basetemp=.audit-pytest-live-browser -p no:cacheprovider`

Expected: initial failure until the server fixture and repository override are complete.

- [ ] **Step 3: Complete fixture lifecycle and cross-origin-safe page loading**

Poll the loopback health endpoint until ready, yield its base URL, and shut down Uvicorn in fixture teardown. Serve the dashboard from FastAPI itself so requests remain same-origin.

- [ ] **Step 4: Run all Compare browser scenarios**

Run: `.venv\Scripts\python.exe -m pytest tests/test_evidence_explorer_ui.py -k compare -n 0 -q --basetemp=.audit-pytest-browser -p no:cacheprovider`

Expected: all mocked product-state tests and the live seam test pass.

### Task 5: Prepare canonical v0.2.0 release metadata

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/med_research/__init__.py`
- Modify: `codemeta.json`
- Modify: `CITATION.cff`
- Modify: `CHANGELOG.md`
- Create: `docs/release-notes/v0.2.0.md`
- Modify: `README.md`, `ROADMAP.md`, and current-version documentation surfaces enumerated by `scripts/check_public_metadata.py`
- Modify: `scripts/check_public_metadata.py`
- Test: `tests/test_public_metadata.py`

**Interfaces:**
- Produces: runtime and package version `0.2.0` and release notes suitable for the GitHub release body.

- [ ] **Step 1: Add a failing metadata test for pre-archive releases**

Require the checker to accept canonical v0.2.0 surfaces with the concept DOI and a clearly historical v0.1.0 version DOI, while rejecting a preferred citation that claims the historical DOI is the v0.2.0 DOI.

- [ ] **Step 2: Run public metadata tests and verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests/test_public_metadata.py -n 0 -q --basetemp=.audit-pytest-metadata -p no:cacheprovider`

- [ ] **Step 3: Update the checker and canonical release surfaces**

Set `0.2.0` in package/runtime/current metadata. Keep the v0.1.0 DOI explicitly historical and use the concept DOI for the current preferred citation until Zenodo mints a v0.2.0 record. Move Compare V2 from pending release to released in roadmap/status documents and add the v0.2.0 changelog and release-notes sections.

- [ ] **Step 4: Run metadata validation and documentation build**

Run:

```powershell
.venv\Scripts\python.exe scripts/check_public_metadata.py
.venv\Scripts\python.exe -m mkdocs build --strict
```

Expected: both exit 0.

### Task 6: Verify and commit the milestone

**Files:** All Compare V2 implementation, tests, exports, documentation, plan, and release metadata files confirmed by `git status --short`.

- [ ] **Step 1: Run focused milestone verification**

Run the Compare engine, export, API, dashboard, and browser suites serially with a workspace-local base temp directory.

- [ ] **Step 2: Run repository release gates**

Run Ruff check/format, import checks, lock verification, public metadata and font checks, strict MkDocs build, and `make test-offline` or its Windows-equivalent pytest command.

- [ ] **Step 3: Review the final diff and requirement matrix**

Run `git diff --check`, inspect `git diff --stat`, scan for secrets, confirm no audit temporary directories remain, and verify every Milestone 1 bullet maps to code and tests.

- [ ] **Step 4: Stage only confirmed paths and commit**

Use explicit `git add -- <paths>` groups. Commit the coherent milestone as `feat(compare): ship Compare V2 product workflow`, followed by a release metadata commit only if separation improves reviewability.

### Task 7: Push, merge, tag, and publish

**Files:** No source changes unless hosted checks reveal a defect.

- [ ] **Step 1: Synchronize safely and push the feature branch**

Fetch `origin`, confirm the branch contains current `origin/master`, then `git push -u origin codex/fix-dependabot-redis-constraint` without force.

- [ ] **Step 2: Create or reuse the non-draft milestone PR**

Base `master`, head `codex/fix-dependabot-redis-constraint`, title `feat(compare): release Compare V2 in v0.2.0`, and include the release verification matrix in the body.

- [ ] **Step 3: Wait for required checks and merge**

Inspect all review threads and checks. Repair failures on the branch. Merge using the repository's merge-commit convention only when required checks are successful.

- [ ] **Step 4: Verify the merged commit before tagging**

Fetch `origin/master`, verify the PR state is merged, confirm the merge commit contains version `0.2.0`, and inspect post-merge Actions checks. Do not tag if any required post-merge check fails.

- [ ] **Step 5: Create and push a signed annotated tag**

Create `v0.2.0` at the verified merge commit using the configured signing identity, verify its signature locally, and push that exact tag.

- [ ] **Step 6: Publish and verify the GitHub release**

Create a non-prerelease GitHub release for `v0.2.0` using `docs/release-notes/v0.2.0.md`. Verify the public tag, release URL, target commit, assets, and release status. If Zenodo archives the release during this session, record its minted version DOI in a follow-up reviewed metadata commit; otherwise report the archive as pending without fabricating a DOI.
