# P1-0 Hosted CI Baseline Audit

**Date:** 2026-08-20  
**Workstream:** A (P1-0 Hosted CI Stabilization)  
**Repo HEAD at audit:** `717f52be79a5cebfb077fc4f8be704cbe94f7374` (master)  
**Public alpha tag:** `v2.2.0` @ `131b72eab6a3ca2826e2dd53829495cab22f67cd`  
**Reference failing run:** GitHub Actions `32428709854` (post–public-alpha merge)

## Executive summary

Hosted CI on `master` was **red** after the v2.2.0 public-alpha merge. Root causes were classified and fixed in-tree (uncommitted at audit time):

| Blocker | Classification | Fix |
|---------|----------------|-----|
| `integration-tests` Celery lifecycle (5 failures) | **REAL_DEFECT** | Set `task_store_eager_result=True` in integration `celery_eager` fixture |
| `test (3.12)` offline suite timeout (25 min) | **PERFORMANCE_TIMEOUT** | Raise step timeout to 45 min; run pytest with `-n 2` on Linux |
| `security` bandit scan | **VALID_SECURITY_DEFECT** + **FALSE_POSITIVE** | Fix MD5/SHA1 (`usedforsecurity=False`); refactor dynamic SQL helpers with documented `# nosec B608` |
| `lint` ruff (Platform Core additions) | **REAL_DEFECT** | Remove unused vars/imports; auto-format nosograph/sync modules |
| `lint` import audit (Open Targets sync test) | **STALE_CONFIGURATION** | Replace stale `tests.fixtures.opentargets` import with `runpy.run_path` |
| `typecheck` mypy (61 errors) | **INTENTIONAL_EXCEPTION** | Job remains informational (`continue-on-error: true`); ratchet baseline = 61 |
| `slow-tests` | **NETWORK_OPTIONAL** | Scheduled / manual only (unchanged) |
| Local `lock_verify` drift on Windows | **ENVIRONMENT_MISMATCH** | Expected (`uvloop`, `nvidia-nccl-cu12`, minor pin skew) |

## Repository state

| Field | Value |
|-------|-------|
| Branch | `master` |
| HEAD | `717f52be79a5cebfb077fc4f8be704cbe94f7374` |
| Workflows | `.github/workflows/test.yml`, `.github/workflows/source-sync-dry-run.yml` |
| Local gate | `make ci-local` (lint, format, locks, imports, serial offline tests) |

## CI workflow matrix

### Primary gate — `Tests` (`.github/workflows/test.yml`)

| Job | Purpose | Required for PR? | Gate type | Pre-fix state | Post-fix target |
|-----|---------|------------------|-----------|---------------|-----------------|
| `lint` | ruff, format, lock freshness, import audit | **Yes** | FAST_REQUIRED | PASS | PASS |
| `typecheck` | mypy on expanded scope (161 files) | No (informational) | NIGHTLY / advisory | FAIL (58 err) | FAIL (61 err, documented backlog) |
| `security` | pip-audit + bandit `-ll` | **Yes** | FAST_REQUIRED | FAIL | PASS |
| `test` (3.11, 3.12) | lock verify, docking, offline unit+coverage, CLI smokes | **Yes** | FAST_REQUIRED | FAIL (3.12 timeout) | PASS |
| `integration-tests` | Redis + offline integration marker | **Yes** | INTEGRATION_OPTIONAL* | FAIL (5) | PASS |
| `slow-tests` | L2 validate-batch (schedule), live APIs + Playwright | No | NETWORK_OPTIONAL | skipped on PR | weekly / dispatch |

\*Integration job is required on `main`/`master` pushes but uses fixture-backed tests only (no live network).

#### `test` job smoke steps (Platform Core / P1-B)

| Step | Command | Purpose |
|------|---------|---------|
| Unified CLI | `med_research.cli --help`, `nosograph --help` | Entry-point alias parity |
| Curated eight | `disease validate {sle…ad} --strict` | Original curated corpus |
| Reference tier | `disease validate-batch --tier reference --strict` | Reference corpus slice |
| Corpus readiness | `test_registry_quality`, `test_tier_model`, `test_corpus_status`, `test_disease_identifiers`, `test_validation_batch`, … | Unit coverage for new modules |
| KG / repurpose | `kg --disease sle --export`, `repurpose --disease sle --top 5` | Pipeline smoke |

#### Trigger layering

| Tier | When | Jobs |
|------|------|------|
| PR / push fast gate | `push`/`pull_request` to `main`/`master` | `lint`, `security`, `test`, `integration-tests` |
| Advisory | same runs | `typecheck` (non-blocking) |
| Nightly / manual | `schedule` Mon 03:00 UTC, `workflow_dispatch` | `slow-tests` |

### Manual only — `Source sync dry-run` (`.github/workflows/source-sync-dry-run.yml`)

| Job | Trigger | Purpose | Required for PR? |
|-----|---------|---------|------------------|
| `opentargets-dry-run` | `workflow_dispatch` only | Build OT fixtures, `biomed sync open_targets --dry-run` | No |

**Note:** Uses older action pins (`checkout@v4`, `setup-python@v5`) and `pip install -e ".[dev]"` instead of lock files. Not on the PR merge path; track separately for action-pin alignment.

## Local verification (Windows dev, `.venv\Scripts\python`)

| Check | Command | Result | Classification |
|-------|---------|--------|----------------|
| ruff lint | `python -m ruff check src tests` | **PASS** | — |
| ruff format | `python -m ruff format --check src tests` | **PASS** | — |
| import audit | `python scripts/check_imports.py` | **PASS** (after opentargets fix) | — |
| lock verify | `python scripts/lock_verify.py` | FAIL (2 missing, 2 skew) | **ENVIRONMENT_MISMATCH** |
| bandit (CI scope) | `bandit -c .bandit -r src/med_research -ll -x tests,src/med_research/diseases,src/med_research/pipeline/dossier` | **PASS** | — |
| mypy (full scope) | `python -m mypy` (161 files from `Makefile`) | FAIL (61 errors / 46 files) | **INTENTIONAL_EXCEPTION** |
| Platform Core unit tests | `pytest tests/test_disease_identifiers.py tests/test_validation_batch.py tests/biomed/sync/test_opentargets_sync.py tests/biomed/nosograph_compare/test_engine.py -n 0` | **PASS** (16 tests) | — |
| Celery lifecycle | `pytest tests/integration/test_celery_lifecycle.py -n 0` | **SKIP** (no local Redis) | **INTEGRATION_OPTIONAL** locally |
| validate-batch smoke | `disease validate-batch --tier reference --strict` | **PASS** | — |
| nosograph alias | `nosograph --help` | **PASS** | — |
| Full offline suite | `make ci-local` / `pytest -m "unit and not network" -n 0` | Not run to completion (15–20 min serial) | prior runs PASS |

### Platform variance (Linux CI vs Windows dev)

| Package / behavior | Linux CI | Windows dev | Classification |
|--------------------|----------|-------------|----------------|
| `uvloop` | installed via lock | not available (no Windows wheel) | **ENVIRONMENT_MISMATCH** |
| `nvidia-nccl-cu12` | installed (torch CUDA dep) | not installed | **ENVIRONMENT_MISMATCH** |
| `biopython` / `fastapi` pins | exact lock match | minor skew (1.87 vs 1.88, 0.140 vs 0.141) | **ENVIRONMENT_MISMATCH** |
| pytest parallelism | CI `test` job uses `-n 2` | `make ci-local` uses `-n 0` (serial) | intentional local gate |
| Redis integration | `integration-tests` service container | absent unless started manually | **INTEGRATION_OPTIONAL** locally |
| `make` | available on `ubuntu-latest` | not on default Windows PATH | use `.venv\Scripts\python` equivalents |

**Contributor guidance:** On Windows, run `make venv-sync && make lock-verify` inside WSL or accept the two expected missing CUDA/uvloop pins. Do not “fix” the lock file for Windows-only gaps.

## Failure classification (hosted run 32428709854 + P1-0 follow-up)

### REAL_DEFECT

**Celery integration lifecycle** (`tests/integration/test_celery_lifecycle.py`, 5 tests)

- Symptom: tasks logged `succeeded` but HTTP/WebSocket status stayed `PENDING` or returned 500.
- Cause: `task_always_eager=True` without `task_store_eager_result=True` — eager runs do not write to the Redis result backend.
- Fix: `tests/integration/conftest.py` — set `celery_app.conf.task_store_eager_result = True` in `celery_eager` fixture.

**Ruff lint regressions** (Platform Core modules)

- Unused variables in `opentargets_adapter.py` (`snapshot_id_source`, `payload`).
- Unused import `time` in `biomed/sync/lifecycle.py`.
- Import sort / format drift across nosograph_compare, CLI, routers.

**Bandit B608 in `biomed/repository.py`**

- Class-level `# bandit: disable=B608` is ineffective in bandit 1.9.x for multiline f-string SQL.
- Fix: module-level SQL helper functions with `# nosec B608` on single-line returns; callers use helpers instead of inline f-strings.

### STALE_CONFIGURATION

**Import audit — Open Targets sync test**

- `tests/biomed/sync/test_opentargets_sync.py` imported `tests.fixtures.opentargets` (no package `__init__.py`).
- Fix: `runpy.run_path(.../build_fixtures.py)` in autouse fixture.

**Bandit disease-tree exclusion**

- CI excludes `src/med_research/diseases` to avoid scanning ~10k scaffolded per-disease modules (1.5M+ LOC) and false-positive DuckDB SQL in `bulk_store.py`.
- `bulk_store.py` now uses `_duckdb_parquet_sql()` helper with documented `# nosec B608` (store-local globs, bound params).
- Top-level package modules (`identifiers.py`, `validation_batch.py`, `curation_tiers.py`) remain excluded in CI for scan-time reasons; acceptable **ACCEPTED_RISK** until exclusion narrows to `diseases/*/data` only.

### PERFORMANCE_TIMEOUT

**`test (3.12)` — "Run deterministic offline tests"**

- Symptom: step cancelled at 25 minutes.
- Fix: timeout 25 → 45 minutes; pytest `-n 0` → `-n 2` on `ubuntu-latest`.

### VALID_SECURITY_DEFECT (fixed)

| Rule | Location | Fix |
|------|----------|-----|
| B324 MD5 | `biomed/imports/clinvar_adapter.py`, `openfda_adapter.py` | `hashlib.md5(..., usedforsecurity=False)` |
| B324 SHA1 | `pipeline/evidence_workspace/sources.py` | `sha1(..., usedforsecurity=False)` |

### FALSE_POSITIVE / ACCEPTED_RISK (documented suppressions)

| Rule | Locations | Rationale | Suppression |
|------|-----------|-----------|-------------|
| B608 SQL | `biomed/repository.py` helpers | Column lists from typed dataclass keys; values bound | `# nosec B608` on helper returns |
| B608 SQL | `diseases/bulk_store.py` | DuckDB `read_parquet('{glob}')`; globs from store layout | `_duckdb_parquet_sql()` helper |
| B608 SQL | `biomed/graph_analytics.py`, `cli.py`, `workspace_store.py` | `IN (...)` uses `?` placeholders | `# nosec B608` per query |
| B104 bind all | `web/config.py`, `cli.py serve`, `lead_opt/app.py` | Env-overridable defaults; dev-only entry | `# nosec B104` / `# nosec` |
| B201 Flask debug | `lead_opt/app.py` | `__main__` dev helper only | `# nosec` |
| B310 urlopen | evidence/external/docking modules | Curated HTTPS endpoints | `# nosec B310` |
| B314 XML | `matching_engine/clinical_trials_parser.py` | Offline CT.gov XML fixtures | `# nosec B314` |

Bandit config: `.bandit` (exclude dirs + pointer to this audit).

#### Bandit exclusion dirs (still justified)

| Excluded path | Reason | Re-review trigger |
|---------------|--------|-------------------|
| `tests/` | Test code not deployed | never |
| `src/med_research/diseases/` | 10k+ scaffold modules + parquet bulk layer; scan time / noise | When scaffold moves out-of-tree or exclusion narrows to data-only |
| `src/med_research/pipeline/dossier/` | Generated markdown/PDF artifacts | never |

## Typecheck ratchet

| Metric | Value |
|--------|-------|
| Scope | 161 files (`make typecheck`) |
| Baseline (2026-08-20) | **61 errors in 46 files** |
| Prior audit estimate | 58 errors (pre–Platform Core expansion) |
| CI policy | `continue-on-error: true` — **not a merge blocker** |
| Dominant themes | Router `-> dict[str, Any]` vs Pydantic responses; `ProvenanceMetadata` vs `dict` in report helpers; adapter `report()` overrides |
| Ratchet rule | Do not increase error count on required jobs; reduce incrementally per `TECHNICAL_DEBT_ISSUES.md` |

## Slow test taxonomy

| Marker / suite | Tier | CI placement |
|----------------|------|--------------|
| `unit and not network` | FAST_REQUIRED | `test` job |
| `integration and not slow` | INTEGRATION_OPTIONAL | `integration-tests` job (Redis service) |
| `slow` | NETWORK_OPTIONAL | `slow-tests` (nightly) |
| `test_evidence_workspace_browser.py` | SLOW_REQUIRED (Playwright) | excluded from PR gate; nightly |
| Docking (`test_docking.py -m "not network"`) | FAST_REQUIRED | dedicated step before main suite |
| L2 validate-batch | NETWORK_OPTIONAL | `slow-tests` schedule step only |

### `slow-tests` job verification (static)

| Step | Condition | Expected behavior |
|------|-----------|-------------------|
| Job `if:` | `schedule` or `workflow_dispatch` | Skipped on PR/push |
| L2 validate-batch | `if: schedule` | Full L2 corpus strict validation |
| Scaffold sample | `validate-batch --tier all --limit 200 \|\| true` | Non-blocking sample on schedule |
| Slow pytest | `-m slow` | Live API tests |
| Playwright artifacts | `actions/upload-artifact@v7` | Browser diagnostics on failure |

### `integration-tests` job verification (static)

| Setting | Value |
|---------|-------|
| Redis service | `redis:7` on `:6379` with health check |
| Marker | `integration and not slow` |
| Timeout | 15 minutes |
| Celery fix dependency | `task_store_eager_result=True` in `tests/integration/conftest.py` |

## Recommended branch protection (coordinator)

**Required status checks on `master`:**

1. `lint`
2. `security`
3. `test (3.12)` — primary Python pin
4. `integration-tests`

**Advisory (report only, do not block merge):**

- `typecheck`
- `test (3.11)` — matrix compatibility signal

**Not on PR path:**

- `slow-tests` (weekly / manual)
- `Source sync dry-run` (manual)

## Files changed in P1-0 fix pass

| File | Change |
|------|--------|
| `tests/integration/conftest.py` | Celery eager result storage |
| `.github/workflows/test.yml` | Bandit config, timeout, pytest `-n 2`, validate-batch + nosograph CI steps |
| `.bandit` | Bandit exclude dirs + audit pointer |
| `src/med_research/biomed/imports/clinvar_adapter.py` | MD5 `usedforsecurity=False` |
| `src/med_research/biomed/imports/openfda_adapter.py` | MD5 `usedforsecurity=False` |
| `src/med_research/biomed/imports/opentargets_adapter.py` | Remove unused vars; format |
| `src/med_research/pipeline/evidence_workspace/sources.py` | SHA1 `usedforsecurity=False` |
| `src/med_research/biomed/repository.py` | SQL helper functions + `# nosec B608` |
| `src/med_research/diseases/bulk_store.py` | `_duckdb_parquet_sql()` helper + `# nosec B608` |
| `src/med_research/biomed/graph_analytics.py` | nosec B608 on IN-clause queries |
| `src/med_research/cli.py` | nosec B104/B608; import format |
| `src/med_research/pipeline/lead_opt/app.py` | nosec B104/B201 |
| `src/med_research/pipeline/evidence/extractor.py` | nosec B310 |
| `src/med_research/pipeline/evidence/gatherer.py` | nosec B310 |
| `src/med_research/pipeline/external/client.py` | nosec B310 |
| `src/med_research/pipeline/virtual_screening/docking.py` | nosec B310 |
| `src/med_research/pipeline/matching_engine/clinical_trials_parser.py` | nosec B314 |
| `src/med_research/web/services/workspace_store.py` | nosec B608 |
| `src/med_research/biomed/sync/lifecycle.py` | Remove unused `time` import |
| `tests/biomed/sync/test_opentargets_sync.py` | Fix stale fixture import (`runpy.run_path`) |
| nosograph_compare / router / service modules | ruff format + import order |

## Remaining work (not P1-0 blockers)

1. **Mypy backlog** — ratchet at 61 errors; fix `ProvenanceMetadata` typing and router return annotations.
2. **Windows venv sync** — `make venv-sync && make lock-verify` for contributors on Windows (or use WSL).
3. **Bandit exclusion narrowing** — move scaffold tree out of `src/` or exclude `diseases/*/data` only so package modules are scanned in CI.
4. **Optional:** split CLI smoke steps into a parallel job to shorten critical path.
5. **Optional:** add `bandit` to `requirements-dev.in` for local parity with CI security job.
6. **Optional:** align `source-sync-dry-run.yml` action pins and lock-file install with `test.yml`.

## Verification checklist (post-merge)

- [x] Push branch and confirm `lint`, `security`, `test (3.12)`, `integration-tests` green — PR [#16](https://github.com/AdamEddahmouni/nosograph/pull/16), run [32441092381](https://github.com/AdamEddahmouni/nosograph/actions/runs/32441092381)
- [x] Confirm `typecheck` still informational (58 errors on Linux; ≤61 ratchet)
- [ ] Dispatch `slow-tests` manually once to validate Playwright + live API tier
- [ ] Dispatch `Source sync dry-run` once after Open Targets sync lands
- [ ] Enable branch protection required status checks (ruleset currently PR-only; no required checks configured)

## P1-0 closeout (2026-08-21)

**Status:** `COMPLETE`

| Field | Value |
|-------|-------|
| Merge commit | `174a52533f64e1604bf478c13d945586284ec396` |
| Authoritative CI run | [32441092381](https://github.com/AdamEddahmouni/nosograph/actions/runs/32441092381) |
| Hosted fixes after first push | Celery env-at-import (`CELERY_TASK_*`), integration `-n 0`, literature cache stub |

### Hosted verification (run 32441092381)

| Job | Result | Runtime |
|-----|--------|---------|
| `lint` | PASS | 4m11s |
| `security` | PASS | 2m13s |
| `test (3.12)` | PASS | 12m49s |
| `test (3.11)` | PASS | 14m1s |
| `integration-tests` | PASS | 14m32s |
| `typecheck` | FAIL (informational) | 4m26s — 58 errors |
| `slow-tests` | skipped (PR) | — |

### Fixes required after push (hosted-only)

1. **REAL_DEFECT** — Literature adapter contract test hit live PubMed without cache on fresh Linux checkout (`ENTREZ_EMAIL`); fixed with monkeypatched cache fixture.
2. **REAL_DEFECT** — Integration Celery lifecycle: `task_store_eager_result` must be set at Celery app import via `CELERY_TASK_*` env; `task_eager_propagates=false` so FAILURE jobs are pollable.
3. **STALE_CONFIGURATION** — Integration job needed `-n 0` to avoid xdist/Redis collisions despite serial `-n 0` being intended for Celery tests.
