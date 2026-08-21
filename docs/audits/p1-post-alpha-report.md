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
| `L2` (full corpus, recomputed 2026-08-21) | 88 | 88 | 0 | 100% | — |

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
| `biomed sync` CLI | `biomed sync open_targets --dry-run` (also `med-research` / `nosograph`) |
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

---

## P1 Integrated Closeout (2026-08-21)

### Integration gate

| Item | Value |
|------|-------|
| Starting master HEAD | `adbacff54` (PR #17 merge) |
| PR #18 merge SHA | `a398ee359` |
| Final master HEAD | `a398ee359` |
| PR #18 hosted run (green) | [32461598725](https://github.com/AdamEddahmouni/nosograph/actions/runs/32461598725) |
| Post-merge master run | [32463088564](https://github.com/AdamEddahmouni/nosograph/actions/runs/32463088564) |

Closeout commits on PR #18 branch (after initial `2aef74fc5`):

- `5d946d564` — align workspace/CLI tests with required `disease_id`
- `f61759ba0` — wire `biomed sync` CLI + ruff format
- `29c040deb` — workspace OpenAPI / job body `ResearchRequest` alignment
- `433376f32` — integration-tests job timeout 30 min

### Hosted CI (master run 32463088564)

| Check | Result |
|-------|--------|
| lint | PASS |
| security | PASS |
| test (3.12) | PASS |
| integration-tests | PASS |
| test (3.11) | PASS |
| typecheck | FAIL (informational; 61 errors, ceiling 61) |
| slow-tests | SKIPPED (schedule/dispatch only) |

### L2 strict validation (recomputed on master)

```bash
python -m med_research.cli disease validate-batch --tier L2 --strict \
  --output data/reports/validation_l2_full.json
```

| Metric | Value |
|--------|-------|
| L2 total | 88 |
| Passed | 88 |
| Failed | 0 |
| Pass rate | 100% |
| Runtime | ~15 s (local Windows) |
| Report | `data/reports/validation_l2_full.json` |

### Source sync

| Item | Status |
|------|--------|
| Lifecycle stages | `discover_version` → `fetch` → `verify` → `store_raw` → `normalize` → `validate` → `diff` → `publish` → `update_provenance` |
| CLI | `python -m med_research.cli biomed sync open_targets --dry-run` |
| Local dry-run | PASS (all stages recorded; publish skipped) |
| Hosted workflow | `Source sync dry-run` — [run 32504822631](https://github.com/AdamEddahmouni/nosograph/actions/runs/32504822631) PASS (2026-08-21) |
| Hosted stages | discover_version ✓, fetch skipped (dry-run), verify ✓, store_raw ✓, normalize ✓, validate ✓, diff ✓, publish skipped, update_provenance ✓ |
| Unit tests | `tests/biomed/sync/test_opentargets_sync.py` — 3/3 offline |

### Evidence golden trace (fixture-backed)

```
MONDO:0007915 (systemic lupus erythematosus)
  → GET /api/v1/conditions/MONDO:0007915/claims
  → claim_id from seeded legacy/HPOA bundle
  → GET /api/v1/claims/{claim_id}/evidence
  → GET /api/v1/claims/{claim_id}/provenance (stages: source_snapshot, normalized_record, graph_claim)
  → original source: HPOA / legacy migration snapshot
```

Verified by `tests/web/test_claim_provenance_api.py` (3/3).

### Compare acceptance

- Engine + API + tests: **COMPLETE**
- Dashboard UI (`renderNosoGraphCompareResult`, `POST /api/v1/nosograph/compare`): **PARTIAL** (API-backed panel; not a standalone product UX)
- Dimensions: phenotype, gene, mechanism, treatment, evidence_coverage
- Missingness: `NOT_RECORDED` ≠ `KNOWN_ABSENT`; also `UNKNOWN`, `NOT_APPLICABLE`

### P1 track matrix (final)

| Track | Result | Evidence |
|-------|--------|----------|
| P1-0 | COMPLETE | PR #17 + branch protection |
| P1-A | COMPLETE | validate-batch + CI reference gate + weekly L2 wiring |
| P1-B | COMPLETE | `identifiers.py`, required `--disease`, resolver tests |
| P1-C | COMPLETE | `nosograph` + `med-research` same `main()` |
| P1-D | PARTIAL | API golden trace; shallow user-facing provenance UX |
| P1-E | PARTIAL | Engine + API + dashboard slice; no full Compare product |
| P1-F | COMPLETE | curation tiers + coverage semantics |
| P1-G | COMPLETE | sync framework + OT slice + CLI + offline tests; hosted dry-run [32504822631](https://github.com/AdamEddahmouni/nosograph/actions/runs/32504822631) PASS |
| P1-H | DESIGNED | assessment in this document |

### Overall P1 status

**COMPLETE_WITH_DEFERRED_WORK** — foundational contracts integrated, required CI green on master, P1-G hosted source-sync dry-run proof complete; deferred: package rename, full Compare UX, public deployment, slow-test weekly run.

### v2.3.0 readiness

**READY_FOR_V2.3.0_RELEASE_PREP** — post-P1 master baseline established at `a398ee359`; proceed with bounded release-preparation wave (not tagging in this pass).
