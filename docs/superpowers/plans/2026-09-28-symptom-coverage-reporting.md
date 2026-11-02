# Symptom Coverage Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Report whether empty disease symptom lists are awaiting curation, have no source annotations, lack an available local source, or cannot be queried because the registry identifiers are unresolved.

**Architecture:** Keep tier calculation, `symptom_count`, `symptoms_populated`, and the existing optional `symptom_source` values unchanged. Add local-only source inspection in the symptom data boundary and classify each corpus row as one of five `symptom_coverage` states, then count those states in the aggregate. Source inspection must not invoke the resolver's live API fallback and must not write module data.

**Tech Stack:** Python 3.12, pytest, sqlite3 read-only access, existing `OpenTargetsBulkStore`, Ruff, mypy.

## Global Constraints

- Existing report keys, tier computation, readiness behavior, and legacy `symptom_source` values remain unchanged.
- Existing non-empty lists use `populated`; do not claim they were manually curated.
- Source checks and queries are local and read-only; no network calls and no config writes.
- `identifier_unresolved` means neither a MONDO nor EFO id is present in the local registry entry.
- If all supported local sources are unusable, classify `source_unavailable`; do not call that “no annotations.”
- Aggregate counts must include all five states, including zero values.

---

## File Structure

- Modify `src/med_research/diseases/symptom_harvester.py`: expose a small local-source availability/status probe, keeping the actual HPOA and Open Targets lookup logic close to existing source readers.
- Modify `src/med_research/diseases/corpus_status.py`: read registry ids without online resolution, assign each per-disease coverage state, and aggregate counts.
- Modify `tests/test_symptom_harvester.py`: verify the local HPOA and phenotype-table availability probe distinguishes missing/inactive source from an available source.
- Modify `tests/test_corpus_status.py`: cover the five states, aggregate counts, legacy field compatibility, and absence of writes/network lookups.

## Task 1: Expose Local Symptom Source Availability

**Files:**
- Modify: `src/med_research/diseases/symptom_harvester.py`
- Test: `tests/test_symptom_harvester.py`

**Interfaces:**
- Produces `local_symptom_source_availability(store: OpenTargetsBulkStore | None = None, biomedical_db_path: Path | None = None) -> dict[str, bool]`.
- Result keys are exactly `biomed_hpoa` and `ot_phenotype`.
- `biomed_hpoa` is true only when the configured/read-only SQLite database contains `active_snapshots`, `claims`, and `claim_evidence`, and an active `hpoa` snapshot row exists.
- `ot_phenotype` is true only when the local bulk store has a readable `disease_phenotype` parquet table (check `_parquet_glob("disease_phenotype")`, not broad `is_available()`).

- [ ] **Step 1: Add HPOA-availability tests using temporary SQLite fixtures**

Add tests to `tests/test_symptom_harvester.py` that create a temp DB with the needed three tables and assert:

```python
assert availability["biomed_hpoa"] is True  # active_snapshots contains resource_name='hpoa'
assert availability["biomed_hpoa"] is False  # missing DB, missing tables, or no active HPOA snapshot
```

Use the `biomedical_db_path` argument to avoid changing global environment/config state.

- [ ] **Step 2: Run the availability tests and verify they fail because the helper is absent**

Run: `python -m pytest tests/test_symptom_harvester.py -k local_symptom_source_availability -q -n 0`
Expected: FAIL with import/attribute error for `local_symptom_source_availability`.

- [ ] **Step 3: Implement the local-only source probe**

Implement the declared helper in `symptom_harvester.py`:

```python
def local_symptom_source_availability(
    store: OpenTargetsBulkStore | None = None,
    biomedical_db_path: Path | None = None,
) -> dict[str, bool]:
    """Report whether each local phenotype source can be queried."""
```

Use `BIOMEDICAL_DB_PATH` only when `biomedical_db_path` is omitted. Open SQLite via `Path.as_uri() + "?mode=ro"`; verify required tables and an active `resource_name='hpoa'` row with a SELECT query. For Open Targets, use the passed store or instantiate `OpenTargetsBulkStore`; availability is the existence of `_parquet_glob("disease_phenotype")`. Catch only expected filesystem/SQLite/store errors, return false for the affected source, and never issue HTTP requests.

- [ ] **Step 4: Run all symptom-harvester tests**

Run: `python -m pytest tests/test_symptom_harvester.py -q -n 0`
Expected: all symptom-harvester tests pass.

## Task 2: Add Per-Disease and Aggregate Coverage States

**Files:**
- Modify: `src/med_research/diseases/corpus_status.py`
- Test: `tests/test_corpus_status.py`

**Interfaces:**
- Add constant `SYMPTOM_COVERAGE_STATES` with ordered values `("populated", "awaiting_curation", "no_source_annotations", "source_unavailable", "identifier_unresolved")`.
- Add helper `_symptom_coverage_state(symptoms: list[str], registry_entry: dict[str, Any] | None, source_availability: dict[str, bool], source_labels: dict[str, list[str]]) -> str`.
- Extend `build_corpus_status()` rows with `symptom_coverage` while preserving `symptom_count` and optional legacy `symptom_source` unchanged.
- Extend `aggregate` with `symptom_coverage`, mapping each state to a count initialized to zero.

- [ ] **Step 1: Add isolated classification tests for each state**

Add tests to `tests/test_corpus_status.py` for:

```python
assert _symptom_coverage_state(["fatigue"], None, {}, {}) == "populated"
assert _symptom_coverage_state([], {"mondo_id": "MONDO:1"}, {"biomed_hpoa": True}, {"biomed_hpoa": ["Fatigue"]}) == "awaiting_curation"
assert _symptom_coverage_state([], {"efo_id": "EFO_1"}, {"ot_phenotype": True}, {"ot_phenotype": []}) == "no_source_annotations"
assert _symptom_coverage_state([], {"efo_id": "EFO_1"}, {"ot_phenotype": False, "biomed_hpoa": False}, {}) == "source_unavailable"
assert _symptom_coverage_state([], {}, {"ot_phenotype": True}, {}) == "identifier_unresolved"
```

- [ ] **Step 2: Run the classification tests and verify they fail for the missing helper**

Run: `python -m pytest tests/test_corpus_status.py -k symptom_coverage -q -n 0`
Expected: FAIL because the new helper/state field is not implemented.

- [ ] **Step 3: Implement local registry/source inspection in corpus status**

Load `load_disease_registry()` once per `build_corpus_status()` call and make a slug-to-entry dictionary using `sanitize_id`. For each empty symptom list, use only `entry["mondo_id"]` and `entry["efo_id"]`; do not instantiate `DiseaseIdResolver`, which can fall back to its online resolver.

Call `local_symptom_source_availability()` once for the report (not once per disease). Query HPOA only when its source is available and a MONDO id exists, using the existing `_hpo_symptoms_from_biomed(mondo_id, limit=1)` local SQLite reader. Query Open Targets only when its source is available and an EFO id exists, using `store.get_phenotypes(efo_id, limit=1)`. Treat a source lookup exception as unusable for that row. If any usable source returns a label, classify `awaiting_curation`; if there are usable query paths but all return empty, classify `no_source_annotations`; if no supported source/query path remains usable, classify `source_unavailable`. If neither identifier is present, classify `identifier_unresolved` before querying.

Preserve blocked/error row semantics: rows where the module itself cannot be loaded remain blocked/error rows and do not increment symptom-state counts. Initialize aggregate counts for all five states before scanning.

- [ ] **Step 4: Test the report shape and compatibility**

Mock the disease list, registry, module disease object, source availability and label helpers. Assert:

```python
assert row["symptom_count"] == 0
assert row["symptom_source"] == "none"  # with include_symptom_source=True; legacy value unchanged
assert row["symptom_coverage"] == "awaiting_curation"
assert report["aggregate"]["symptom_coverage"]["awaiting_curation"] == 1
assert set(report["aggregate"]["symptom_coverage"]) == set(SYMPTOM_COVERAGE_STATES)
```

Also assert that `include_symptom_source=False` still omits the legacy field and that no file-write or HTTP helper is called.

- [ ] **Step 5: Run corpus-status tests**

Run: `python -m pytest tests/test_corpus_status.py -q -n 0`
Expected: all corpus-status tests pass.

## Task 3: Verify the Reporting Contract and Regression Surface

**Files:**
- Tests: `tests/test_corpus_status.py`, `tests/test_symptom_harvester.py`
- Check: the full project typecheck ratchet and offline test target.

- [ ] **Step 1: Run the focused reporting/source suites**

Run: `python -m pytest tests/test_corpus_status.py tests/test_symptom_harvester.py -q -n 0`
Expected: all tests pass.

- [ ] **Step 2: Run lint and formatting on changed Python files**

Run: `python -m ruff check src/med_research/diseases/corpus_status.py src/med_research/diseases/symptom_harvester.py tests/test_corpus_status.py tests/test_symptom_harvester.py`
Expected: `All checks passed!`.

Run: `python -m ruff format --check` with the same file list.
Expected: all files already formatted.

- [ ] **Step 3: Run typecheck and offline tests**

Run: `make typecheck`
Expected: `Success: no issues found in 173 source files`.

Run: `make test-offline`
Expected: complete offline tier passes, except any pre-existing environment/platform failures are reported with exact output.

## Spec Coverage Self-Review

- Per-disease states and five initialized aggregate counts: Task 2.
- Existing fields and tier behavior preserved: Task 2 compatibility test.
- Local-only availability and identifier handling; no live API use: Tasks 1 and 2.
- Source failure does not become “no annotations”: Task 2 source-path classification and test.
- No file mutation: explicit no-write test in Task 2.
- Focused/full verification: Task 3.

## Scope Boundaries

Do not implement the corpus backfill, symptom harvesting, status-file regeneration, dashboard display changes, or readiness-tier changes as part of this plan.
