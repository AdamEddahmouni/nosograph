# NosoGraph P1 Post-Alpha Report

Workstreams: **P1-0** (CI), **P1-A** (Validation), **P1-B** (Disease-General), **P1-C** (Naming), **P1-D** (Evidence UX), **P1-E** (Compare), **P1-F** (Curation), **P1-G** (Source Sync), **P1-H** (Demo analysis).

Generated: 2026-08-21

## Summary

Removed implicit `disease=sle` defaults from CLI entry points, Evidence Workspace requests, and web API query handling. Centralized disease identifier resolution (slug, alias, MONDO, EFO). Added batch strict validation with failure classification, formal curation tier definitions, enriched coverage reports, a `nosograph` CLI alias, and CI validation policy hooks.

## Files changed (P1 scope)

### New modules
| File | Purpose |
|------|---------|
| `src/med_research/diseases/identifiers.py` | `CI_VALIDATED_DISEASES`, `REFERENCE_DISEASES`, alias map, `resolve_disease_identifier()` |
| `src/med_research/diseases/curation_tiers.py` | Formal tier + failure-class definitions |
| `src/med_research/diseases/validation_batch.py` | `disease validate-batch` engine + JSON reports |
| `src/med_research/web/disease_params.py` | FastAPI dependencies (`?disease=` / `?disease_id=`) |
| `tests/test_disease_identifiers.py` | Identifier resolution tests |
| `tests/test_validation_batch.py` | Batch validation tests |
| `data/reports/validation_*.json` | Machine-readable validation outputs |

### Modified (platform defaults removed or generalized)
| File | Change |
|------|--------|
| `src/med_research/cli.py` | Required `--disease` on pipeline commands; `validate-batch`; `_trial_query` no longer falls back to lupus |
| `pyproject.toml` | `nosograph` console script alias → same `main()` |
| `src/med_research/pipeline/evidence_workspace/schemas.py` | `ResearchRequest.disease_id` required |
| `src/med_research/diseases/coverage_report.py` | Curation tier, strict_pass, phenotype/mechanism/treatment flags |
| `src/med_research/diseases/base.py` | Invalidate identifier cache on scaffold |
| `src/med_research/web/routers/*.py` | Generic disease selection via `resolve_optional_query_disease` |
| `src/med_research/web/static/js/dashboard.js` | No SLE hardcode; `pickDefaultDiseaseId()` from API list |
| `.github/workflows/test.yml` | PR: CI-validated + reference batch; weekly: full L2 batch |
| `tests/test_evidence_workspace_schemas.py`, `tests/test_web_api.py` | Updated for required/generic disease behavior |

## Assumptions removed (DEFAULT_BEHAVIOR / ARCHITECTURAL_ASSUMPTION)

| Location | Before | After | Class |
|----------|--------|-------|-------|
| CLI pipeline commands (~25) | `--disease` default `sle` | `--disease` **required** | DEFAULT_BEHAVIOR |
| `ResearchRequest` schema | `disease_id="sle"` | required field | DEFAULT_BEHAVIOR |
| Web API routers | `Query("sle")` | generic CI-validated default or 422 on unknown | ARCHITECTURAL_ASSUMPTION |
| `dashboard.js` `getActiveDisease()` | fallback `'sle'` | empty → first curated from API | DEFAULT_BEHAVIOR |
| `dashboard.js` error fallback | hardcoded SLE object | empty list | DEFAULT_BEHAVIOR |
| `_trial_query()` CLI helper | `"lupus OR SLE"` | disease-scoped query string | LEGACY_NAME |
| `system.py` `core_diseases` inline set | duplicated 8 IDs | `CI_VALIDATED_DISEASES` constant | ARCHITECTURAL_ASSUMPTION |

### Preserved (intentionally not changed)

| Location | Rationale | Class |
|----------|-----------|-------|
| `Disease("sle")` in docstrings/examples | DOCUMENTATION_EXAMPLE | |
| SLE-specific adverse-event legacy fallback in `base.py` | LEGITIMATE_DISEASE_DATA for curated SLE module | |
| `CURATED_CONSENSUS_DISEASES` in geo.py | LEGITIMATE_DISEASE_DATA (expression corpus) | |
| Pipeline internal `def foo(disease_id="sle")` when only called with explicit args | deferred; callers now pass explicit disease | TEST_FIXTURE / internal |
| Celery task signatures with `disease_id="sle"` | tasks always invoked with explicit disease from API jobs | |

## Curation tier definitions

| Tier | Meaning |
|------|---------|
| **scaffold** | Auto-generated from public KBs; KG skeleton present, config incomplete |
| **L0** | No usable KG data |
| **L1** | Partial KG and/or config gaps; strict validation fails |
| **L2** | Strict validation pass — pipeline-ready (~88 in cached 500-disease scan) |
| **L3** | Research-ready (expression consensus or deep curation) |
| **ci_validated** | Subset of L2/L3: eight core modules in every PR CI gate |
| **blocked** | Non-disease slug or load failure |

Formal definitions: `src/med_research/diseases/curation_tiers.py`

## Reference diseases (diverse corpus slice)

Used for tests, `validate-batch --tier reference`, and documentation:

| ID | Category |
|----|----------|
| `sle` | Autoimmune |
| `cystic_fibrosis` | Mendelian |
| `tuberculosis` | Infectious |
| `melanoma` | Neoplastic |
| `als` | Neurodegenerative |
| `t2d` | Metabolic |

## CI-validated modules (8)

`sle`, `ra`, `ms`, `ss`, `ssc`, `t1d`, `ibd`, `ad` — unchanged merge gate; now sourced from `CI_VALIDATED_DISEASES`.

## Validation stats

Reports under `data/reports/`:

| Batch | Total | Pass | Fail | Pass rate | Failure classes |
|-------|-------|------|------|-----------|-----------------|
| `ci_validated` | 8 | 8 | 0 | 100% | — |
| `reference` | 6 | 6 | 0 | 100% | — |
| `L2` (sample n=50) | 50 | 50 | 0 | 100% | — |

Corpus tier counts (cached `disease_batch_status.json`, n=500 scan): L3=2, L2=88, L1=410, L0=0.

Failure taxonomy implemented: `SCHEMA`, `PROVENANCE`, `IDENTIFIER`, `MAPPING`, `MISSING_REQUIRED_DATA`, `LEGACY_FORMAT`, `DANGLING_REFERENCE`, `VALIDATOR_BUG`, `SOURCE_VARIANCE`.

## CI validation policy

| Trigger | Policy |
|---------|--------|
| **PR / push** | Strict validate 8 CI modules + `validate-batch --tier reference --strict` |
| **main** | Same as PR (full L2 batch deferred to weekly until corpus status report is refreshed on main) |
| **Weekly schedule** | `validate-batch --tier L2 --strict` + scaffold sample (200 modules) |

Commands:

```bash
med-research disease validate sle --strict          # single module
med-research disease validate-batch --tier L2 --strict --output data/reports/validation_l2_full.json
med-research disease corpus-status --output data/reports/disease_batch_status.json
med-research disease coverage sle --json /tmp/cov.json
```

## P1-C: med-research → nosograph naming

- **Shipped:** `nosograph` console entry point in `pyproject.toml` invoking the same `med_research.cli:main` implementation.
- **Compatibility:** `med-research` unchanged; both commands share one codebase.
- **Future:** Package rename to `nosograph` on PyPI is a separate release decision; alias satisfies low-risk migration path.

## Tests run

```
pytest tests/test_disease_identifiers.py tests/test_validation_batch.py \
       tests/test_evidence_workspace_schemas.py tests/test_tier_model.py \
       tests/test_corpus_status.py tests/test_web_api.py::TestKGGraphDiseaseAware -n 0
```

Result: **51 passed** (36 unit + 15 API/identifier batch).

## P1-0 Hosted CI (Workstream A)

See [`docs/audits/p1-ci-baseline.md`](p1-ci-baseline.md) for the full audit.

| Fix | Status |
|-----|--------|
| Celery `task_store_eager_result=True` in integration fixture | Applied |
| Test job timeout 45 min + pytest `-n 2` | Applied |
| Bandit `.bandit` config + hash/`nosec` suppressions | Applied |
| `typecheck` remains informational (61 mypy errors) | Unchanged |

Recommended required checks: `lint`, `security`, `test (3.12)`, `integration-tests`.

## P1-G Source Synchronization

Framework: `src/med_research/biomed/sync/` — nine-stage lifecycle (DISCOVER_VERSION → … → UPDATE PROVENANCE).

| Artifact | Purpose |
|----------|---------|
| `sync/models.py`, `contracts.py`, `lifecycle.py`, `registry.py` | Sync contract + orchestrator + 13-source matrix |
| `sync/sources/opentargets.py` | Vertical slice (checksums, diff, provenance) |
| `biomed sync` CLI | `list`, `open_targets --dry-run`, publish path |
| `data/sources/source-matrix.md` | Connector inventory |
| `docs/architecture/source-sync-lifecycle.md` | Architecture |
| `.github/workflows/source-sync-dry-run.yml` | Manual dry-run (no secrets) |

Tests: `tests/biomed/sync/test_opentargets_sync.py` — **3/3 passed**.

## P1-D Evidence & Provenance UX

End-to-end trace (SLE phenotype claim):

```
HPOA → HpoAnnotationAdapter → Claim (MONDO:0007915 HAS_PHENOTYPE HP:…)
  → ClaimEvidence → SQLite → API → Condition Explorer panel
```

New routes under `/api/v1/`:

- `GET /claims/{claim_id}`
- `GET /claims/{claim_id}/evidence` (confidence explainability)
- `GET /claims/{claim_id}/provenance` (ingestion → graph steps)

Tests: `tests/web/test_claim_provenance_api.py` — **3/3 passed**.

## P1-E NosoGraph Compare

Module: `src/med_research/biomed/nosograph_compare/`

| Dimension | Predicate |
|-----------|-----------|
| phenotype | `HAS_PHENOTYPE` |
| gene | `ASSOCIATED_WITH_GENE` |
| mechanism | `INVOLVES_PATHWAY` |
| treatment | `TREATED_BY` |
| evidence_coverage | claim-id overlap |

- **API:** `POST /api/v1/nosograph/compare` — per-dimension shared/unique/missing_data; no universal score
- **Missing-data:** `KNOWN_ABSENT`, `NOT_RECORDED`, `UNKNOWN`, `NOT_APPLICABLE`
- **UI:** Compare section in dashboard (dimension checkboxes + overlap summary)

Tests: `tests/biomed/nosograph_compare/test_engine.py` — **3/3 passed** (fixture via `tests/biomed/nosograph_compare/conftest.py`).

## P1-H Demo Readiness (analysis only — not deployed)

| Blocker | Severity |
|---------|----------|
| No public deployment configured | P1 |
| `API_KEY` required when `DEBUG=false` | P0 for public |
| 10k scaffold vs ~45 L2 curated messaging gap | P1 |
| Live API rate limits | P2 |
| Celery/Redis for async jobs | P2 |

Safe demo scope: eight CI-validated diseases + Mondo/HPO/HPOA fixtures; avoid full scaffold registry.

## Features verification (combined)

```
pytest tests/biomed/sync/test_opentargets_sync.py \
       tests/biomed/nosograph_compare/test_engine.py \
       tests/web/test_claim_provenance_api.py -n 0
```

Result: **9 passed**.

## Follow-ups (out of scope for this pass)

1. Refresh full-corpus `disease_batch_status.json` on main (10k modules) for accurate L2/L3 counts.
2. Remove remaining internal `disease_id="sle"` defaults in Celery tasks / web service layer signatures.
3. Expand L2 strict validation to full corpus once status report covers all modules.
4. Wire `readiness_tier=ci_validated` into `/api/system/diseases` JSON for dashboard tier-aware picker.
