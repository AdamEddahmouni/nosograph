# med-research v2.0 — Comprehensive Technical Debt & Improvement Audit

> **Current-state note (2026-08-07):** This document preserves the 2026-07-25 audit for traceability, but several findings have since been resolved or mitigated. The supported runtime is the `src/med_research` package, the root `main.py` is a compatibility wrapper, all seven disease modules pass `python -m med_research.cli disease validate --all --strict`, and current usage is documented in `README.md`, `docs/evidence-workspace.md`, and `docs/api-reference.md`. Treat historical “Current state” sections below as dated audit observations, not the live API specification. The **Summary Matrix** at the bottom is likewise historical; prefer the resolved/mitigated list here and per-issue resolution notes.

**Resolved or mitigated findings:** legacy runtime entrypoints/static mounts, stale primary README guidance, incomplete seven-disease validation, unguarded `--reload` behavior, **#1 structured logging migration** (resolved 2026-08-07), **#2 KG JSON schema validation** (resolved 2026-08-07), **#3 legacy v1 directory cleanup** (archived and removed 2026-08-07), **#4 authentication** (mitigated 2026-08-07 — `AuthMiddleware` enforces `X-API-Key`; `API_KEY` is **required** when `DEBUG=false`, fail-fast in `web/main.py` lifespan), **#5 CORS wildcard default** (resolved 2026-08-07), **#6 Docker non-root user** (resolved 2026-08-07), **#7 Dockerfile SLE-only KG build** (resolved 2026-08-07), **#8 multi-disease KG validation in Docker build** (resolved 2026-08-07), **#9 expand_kg v1 paths** (resolved 2026-08-07), **#10 GWAS silent except blocks** (resolved 2026-08-07), **#11 ML predictor silent ImportError** (resolved 2026-08-07), **#12 disease config stubs** (mitigated 2026-08-07 — all seven diseases have curated CAR_T_SCORES and risk tiers), **#13 Base module interface** (resolved 2026-08-07 — 21 `BasePipelineModule` adapters + `registry.py`), **#14 dependency lock files** (resolved 2026-08-07 — `requirements.in`/`requirements-dev.in`, `make lock`/`lock-check`, CI lock-check step), **#15 error taxonomy** (substantially complete 2026-08-07 — `classify_api_error`, typed raises in API-heavy modules), **#16 `.env.example`** (resolved 2026-08-07), **#17 v1 static mounts** (resolved 2026-08-07), **#18 hardcoded web values** (mitigated 2026-08-07 — version from metadata, `tests_passing` removed), **#19 progress callbacks** (substantially complete 2026-08-07 — `_tick` helper + adapter tests), **#20 Caching strategy** (substantially complete 2026-08-07 — `CacheManager` migration), **#21 Separated compute/report** (substantially complete 2026-08-07 — adapters own `report()`), **#22 integration tests** (substantially complete 2026-08-07 — full-pipeline E2E for sle/ra/ibd, expanded integration, mocked evidence HTTP), **#25 B008 lint** (resolved 2026-08-07 — ruff B ruleset enabled), **#26 CLI subprocess smokes** (mitigated 2026-08-07 — `cli_helpers.py` pattern), **#29 IBD missing relationships** (resolved 2026-08-07), **#30 TypedDict pilot** (mitigated 2026-08-07 — `GeneDict`/`DrugDict` in `diseases/schemas.py`), **#31 Async/concurrent pipeline** (mitigated 2026-08-07 — `--parallel` run-all via `scheduler.py`), **#33 guarded `--reload`** (resolved 2026-08-07), **#34 rate limiting** (resolved 2026-08-08 — Redis-backed distributed sliding-window store with in-memory fallback; see `src/med_research/web/rate_limit.py`), **#35 Dockerfile hardcoded port** (resolved 2026-08-07), **#36 docker-compose volume paths** (resolved 2026-08-07), **#37 pyproject.toml package-data patterns** (resolved 2026-08-07), **#38 router file organization** (resolved 2026-08-07), **#39 index.html v1 branding** (resolved 2026-08-07), **Jinja2 report pilot** (mitigated 2026-08-07 — `render_report()` helper; drug_repurposing, bioinformatics, gene_expression on shared templates), **generic job API validation** (mitigated 2026-08-07 — `GenericModuleJobRequest` + 422 handlers), **unified dispatch** (resolved 2026-08-07 — `registry_service.run_module_job` → `execute_module()`), **mypy pilot** (mitigated 2026-08-07 — `[tool.mypy]`, `make typecheck`, core + adapter scope; adapter `opts` typing still open as of 2026-08-08). CLI `--export-html` provenance wiring (the remaining provenance gap vs engine `__main__` blocks) was resolved 2026-08-07 via `_provenance_for()` in `cli.py`. **2026-08-08:** slow-suite verification (WebSocket orphaned-job hang, trials `top_sponsors` contract, docking vs Meeko 0.7, `vina_setup --check` output), end-to-end dependency locking (CI installs the lock files and verifies the installed env against them; `make venv-sync`/`lock-verify`; `lock-check` also guards lock-to-lock consistency; dev lock compiled against the runtime lock), a new `network` marker for live-external-API tests, and fast docking prep unit tests moved into the PR test job. **#34 (Redis/distributed rate limiting) was resolved 2026-08-08 — `RedisRateLimitStore` (sorted-set + Lua sliding window, fail-open) with `InMemoryRateLimitStore` fallback, wired through `RateLimitMiddleware` via `asyncio.to_thread`, configured by `REDIS_RATE_LIMIT_URL`. The mypy adapter-`opts` gap remains open as of 2026-08-08.** Remaining open work should be re-verified against the current tree before implementation.

> **Audited:** 2026-07-25 | **Package:** `med-research` | **Version:** 2.0.0 (migration in progress)
> **Scope:** `src/med_research/` (114 Python files), `tests/` (25 files), root config, Docker, Makefile, `scripts/`, legacy v1 directories
> **Total findings:** 49 issues

---

## Critical

### 1. Logging — Zero Usage of `logging` Module

> **Resolved 2026-08-07.** All pipeline modules, the unified CLI, disease scaffold tooling, and web lifespan hooks now use structured logging via `logging_config.py`. CLI `--verbose`/`--quiet` adjust console level; FastAPI calls `setup_logging()` on startup (DEBUG when `DEBUG=true`, else INFO). Pipeline modules use `logging.getLogger(__name__)`; CLI and scaffold use `get_logger(__name__)`. Tests assert formatter output via `caplog` instead of `capsys`.

**Historical audit (2026-07-25):** Every pipeline module, every utility function, and the CLI used `print()` exclusively for all output. There were **zero imports** of `logging` or `logging.getLogger` anywhere in the `src/med_research/` tree.

**What this means:**
- No log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL). All output is at the same "always on" level.
- No ability to suppress verbose output in production or CI.
- No log file output, rotation, or structured logging (JSON).
- Emoji-prefixed print lines (`✅`, `❌`, `⚠️`, `🔄`, `💾`, `📦`, etc.) are used as DIY severity indicators.
- `sys.stdout.reconfigure(encoding="utf-8")` is called on Windows in nearly every module's `main()` function.

**Affected files (every module):**
| File | Print statements |
|---|---|
| `src/med_research/cli.py` | ~25 |
| `src/med_research/pipeline/knowledge_graph/builder.py` | ~15 |
| `src/med_research/pipeline/drug_repurposing/engine.py` | ~12 |
| `src/med_research/pipeline/bioinformatics/gwas.py` | ~20 |
| `src/med_research/pipeline/bioinformatics/enrichment.py` | ~15 |
| `src/med_research/pipeline/bioinformatics/ppi.py` | ~15 |
| `src/med_research/pipeline/literature_mining/miner.py` | ~10 |
| `src/med_research/pipeline/virtual_screening/screening.py` | ~15 |
| `src/med_research/pipeline/virtual_screening/docking.py` | ~20 |
| `src/med_research/pipeline/clinical_trials/tracker.py` | ~12 |
| `src/med_research/pipeline/ml_predictor/predictor.py` | ~10 |
| `src/med_research/pipeline/drug_synergy/engine.py` | ~10 |
| `src/med_research/pipeline/adverse_events/profiler.py` | ~10 |
| `src/med_research/pipeline/network_pharmacology/analyzer.py` | ~10 |
| `src/med_research/pipeline/gene_expression/correlator.py` | ~12 |
| `src/med_research/pipeline/car_t_predictor/predictor.py` | ~8 |
| `src/med_research/pipeline/biomarker_discovery/discover.py` | ~10 |
| `src/med_research/pipeline/semantic_search/engine.py` | ~8 |
| `src/med_research/pipeline/evidence/gatherer.py` | ~12 |
| `src/med_research/pipeline/evidence/extractor.py` | ~10 |
| `src/med_research/pipeline/cross_disease/analyzer.py` | ~10 |
| `src/med_research/web/routers/*.py` | ~5 (FastAPI uses its own logger) |

**Recommended approach:**
1. Create `src/med_research/logging_config.py` with `setup_logging(level=INFO)` that configures both console (colored) and file handlers.
2. Replace all `print()` calls with `logger = logging.getLogger(__name__)` in each module.
3. Map emoji prefixes to log levels: `✅` → INFO, `❌` → ERROR, `⚠️` → WARNING, `🔄` → INFO, `💾`/`📦` → DEBUG.
4. Add `--verbose`/`--quiet` CLI flags that adjust console handler level.

**Estimated effort:** Medium (touches every module file, but pattern is mechanical)

---

### 2. Data Validation — KG JSON Files Loaded Without Schema Validation

> **Resolved 2026-08-07.** KG entity files (`genes.json`, `drugs.json`, `pathways.json`, `relationships.json`, `profile.json`) are validated at load time via Pydantic models in `src/med_research/diseases/schemas.py`, routed through `load_validated_json()` in `pipeline/knowledge_graph/config.py` and `Disease.load_json()`. Typed errors (`MissingDataError`, `SchemaValidationError`) live in `src/med_research/exceptions.py`. `disease validate --all --strict` exercises all five KG files. `adverse_events.json` uses `AdverseEventsFile` via `validate_and_load`. Coverage: `tests/test_kg_schema_validation.py` (parametrized happy-path, error contract, validate integration, relationship integrity).

**Historical audit (2026-07-25):** Knowledge graph JSON files were loaded via raw `json.load()` / `json.loads()` with **no schema, no type checking, no required-field validation.**

**Loading points:**
- `src/med_research/diseases/base.py:73,91` — `json.load(f)` for profile and data files
- `src/med_research/pipeline/knowledge_graph/config.py:56` — `json.loads(path.read_text())`
- Each pipeline module has its own `load_json()` helper: `drug_repurposing/engine.py:42`, `drug_synergy/engine.py:91`, `car_t_predictor/predictor.py:36`, `biomarker_discovery/discover.py:36`, `gene_expression/correlator.py:76`, `evidence/gatherer.py:47`, `evidence/extractor.py:87`, `evidence/monitor.py:84`

**What this means:**
- A missing `targets` or `pathways` key in `genes.json` causes a cryptic `KeyError` deep inside `biomarker_discovery/discover.py` or `ml_predictor/predictor.py`.
- A malformed JSON file (extra comma, wrong type) causes `JSONDecodeError` at load time, but the error message tells you nothing about *which* gene/drug entry is corrupt.
- No guarantee that `drugs.json` entries have `name`, `mechanism`, or `targets` fields — these are assumed by 8+ pipeline modules.
- `ibd/data/relationships.json` is **missing entirely** — `Disease("ibd").load_relationships()` raises `FileNotFoundError`.

**Pydantic already installed** (`pydantic>=2.5.0` in requirements.txt) but used **only** in `src/med_research/web/models/` for FastAPI request/response validation. Pipeline code uses bare `dict`.

**Recommended approach:**
1. Define Pydantic `BaseModel` classes for each KG entity type:
   ```python
   class KGNode(BaseModel):
       id: str
       type: Literal["gene", "drug", "pathway", "symptom"]
       name: str
       targets: list[str] = Field(default_factory=list)
       pathways: list[str] = Field(default_factory=list)
       ...
   ```
2. Replace all `load_json()` helpers with a single `load_validated[T](path, model)` that loads + validates.
3. Add `model_validate_json()` at every JSON load point.
4. Generate `ibd/data/relationships.json` or handle missing files gracefully.

**Estimated effort:** Medium-High (designing models for 5 entity types, touching ~20 load sites)

---

### 3. Pre-Reorganization Cleanup — 19 Legacy v1 Directories Duplicate v2 Package

> **Resolved 2026-08-07.** Legacy v1 directories were archived under `_archive_v1/` and removed from the working tree. Root `main.py` delegates to `med_research.cli`, and `web/main.py` mounts only v2 pipeline static paths.

**Historical audit (2026-07-25):**

**Legacy directories at root:**
| Root Directory | Duplicated in | Issue |
|---|---|---|
| `knowledge_graph/` | `src/med_research/pipeline/knowledge_graph/` | Identical files, different import paths |
| `web_api/` | `src/med_research/web/` | Full FastAPI app, models, services, config duplicated (54 Python files) |
| `adverse_events/` | `src/med_research/pipeline/adverse_events/` | Duplicate |
| `bioinformatics/` | `src/med_research/pipeline/bioinformatics/` | Duplicate |
| `biomarker_discovery/` | `src/med_research/pipeline/biomarker_discovery/` | Duplicate |
| `car_t_predictor/` | `src/med_research/pipeline/car_t_predictor/` | Duplicate |
| `clinical_trials/` | `src/med_research/pipeline/clinical_trials/` | Duplicate |
| `cross_disease/` | `src/med_research/pipeline/cross_disease/` | Duplicate |
| `drug_repurposing/` | `src/med_research/pipeline/drug_repurposing/` | Duplicate |
| `drug_synergy/` | `src/med_research/pipeline/drug_synergy/` | Duplicate |
| `evidence_gatherer/` | `src/med_research/pipeline/evidence/` | Duplicate (merged gatherer+monitor) |
| `evidence_monitor/` | `src/med_research/pipeline/evidence/` | Duplicate |
| `gene_expression/` | `src/med_research/pipeline/gene_expression/` | Duplicate |
| `literature_mining/` | `src/med_research/pipeline/literature_mining/` | Duplicate |
| `llm_extractor/` | `src/med_research/pipeline/evidence/` | Duplicate (extractor.py) |
| `ml_predictor/` | `src/med_research/pipeline/ml_predictor/` | Duplicate |
| `network_pharmacology/` | `src/med_research/pipeline/network_pharmacology/` | Duplicate |
| `semantic_search/` | `src/med_research/pipeline/semantic_search/` | Duplicate |
| `virtual_screening/` | `src/med_research/pipeline/virtual_screening/` | Duplicate |

**Additional hazards:**
- Legacy modules use **27 `sys.path.insert(0, ...)` hacks** for importing, while v2 uses `from med_research.pipeline...`. If someone runs a legacy script by accident, it may import from the wrong location.
- `web_api/config.py` is a near-identical duplicate of `src/med_research/web/config.py` — different API titles/versions (v1: "Lupus Research Platform API" / "1.0.0", v2: "Medical Research Platform API" / "2.0.0"), same defaults for HOST, PORT, CORS, Celery.
- `v2 web/main.py:120` has `uvicorn.run("web_api.main:app")` referencing the v1 directory — hard crash if v1 is deleted.
- Root `main.py:30-51` (967 lines) maps `SCRIPTS` to v1 paths like `"knowledge_graph/build_graph.py"` and imports `from bioinformatics.report import ...` from v1. Fully broken in v2.
- **6 corrupted directory names** exist as literal entries (missing backslashes from path concatenation):
  - `C:Usersadamedesktopmedicaladverse_eventsdata/`
  - `C:Usersadamedesktopmedicalbiomarker_discoverydata/`
  - `C:Usersadamedesktopmedicalcar_t_predictordata/`
  - `C:Usersadamedesktopmedicaldrug_synergydata/`
  - `C:Usersadamedesktopmedicalgene_expressiondata/`
  - `C:Usersadamedesktopmedicalnetwork_pharmacologydata/`
- `index.html` at root is branded "Lupus Research Platform" (v1), but v2 is multi-disease.
- Root `lupus_research.md` and `exa_ai_research.md` are outdated v1 docs.
- Legacy `requirements.txt` files exist in `knowledge_graph/`, `clinical_trials/`, `virtual_screening/`, `drug_repurposing/`, `bioinformatics/`, `literature_mining/`, and `ml_predictor/` — potentially stale.
- `.gitignore` is missing entries for `adverse_events/data/`, `car_t_predictor/data/`, `biomarker_discovery/data/`, `network_pharmacology/data/`, `semantic_search/data/`.

**Recommended approach:**
1. Confirm CI workflows or Dockerfile don't reference legacy paths.
2. Move all 19 legacy dirs to `_archive_v1/` or delete them.
3. Delete the 6 corrupted path-named directories.
4. Fix `src/med_research/web/main.py:120` to reference `"med_research.web.main:app"`.
5. Rewrite or delete root `main.py` (replace with `med_research.cli.main()` wrapper or delete).
6. Add missing data directories to `.gitignore`.

**Estimated effort:** Low (mostly `git mv`, verification)

---

### 4. Security — No Authentication on Any API Endpoint

> **Mitigated 2026-08-07.** `AuthMiddleware` in `src/med_research/web/middleware.py` enforces `X-API-Key` when `API_KEY` is set. The FastAPI lifespan in `src/med_research/web/main.py` now **requires** `API_KEY` when `DEBUG=false` (fail-fast `RuntimeError` on startup); `DEBUG=true` allows local development without a key. Document `API_KEY` in deployment runbooks.

**Historical audit (2026-07-25):** All 17+ FastAPI router modules in `src/med_research/web/routers/` had **zero authentication or authorization middleware.** Every endpoint — job submission, WebSocket streaming, evidence extraction, KG queries — was publicly accessible with no API key or user auth.

**What this means:**
- Anyone who can reach the web server can submit Celery jobs, stream WebSocket results, and extract evidence via LLM (potentially burning API quota).
- No user identity is tracked — job IDs are accepted without ownership validation (`jobs.py:116-117`).
- Rate limiting is absent — no protection against abuse of computational resources.

**Recommended approach:**
1. Add at minimum an API key check or basic auth middleware for admin endpoints (job submission, evidence extraction).
2. Validate job ID format (UUID) and track submitted job IDs per session/token.
3. Add `slowapi` or Redis-based rate limiter middleware.
4. Document authentication requirements in a `.env.example` file (see Issue #16).

**Estimated effort:** Medium (adding middleware, key management)

---

### 5. Security — CORS Defaults to Wildcard (`*`)

> **Resolved 2026-08-07.** `CORS_ORIGINS` in `src/med_research/web/config.py` now defaults to `http://localhost:3000`. Production deployments should set `CORS_ORIGINS` explicitly via environment variable (documented in `.env.example`).

**Historical audit (2026-07-25):** `src/med_research/web/config.py:114` defaulted `CORS_ORIGINS` to `"*"` with `allow_credentials=True` and `allow_methods=["*"]`.

```python
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
```

**What this means:**
- Any website on the internet can make credentialed requests to the API.
- Combined with no authentication (Issue #4), this is a full-open gateway.

**Recommended approach:**
- Default to `"http://localhost:3000"` in development.
- Require explicit configuration in production. The `.env.example` (Issue #16) should document this.

**Estimated effort:** Low (one line change + env doc)

---

### 6. Docker Container Runs as Root

> **Resolved 2026-08-07.** `Dockerfile` creates `appuser`, chowns `/app`, and sets `USER appuser` before `ENTRYPOINT`.

**Historical audit (2026-07-25):** `Dockerfile` had no `USER` directive. The container ran as root.

**What this means:**
- Container escape vulnerabilities become remote code execution as root on the host.
- Best practice violation. All modern Docker security scanners flag this.

**Recommended approach:**
Add before `ENTRYPOINT`:
```dockerfile
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser
```

Also switch to `EXPOSE 8000` instead of hardcoded `"--port" "8000"` in ENTRYPOINT.

**Estimated effort:** Low (3 lines in Dockerfile)

---

### 7. Dockerfile Hardcodes SLE Knowledge Graph Build

> **Resolved 2026-08-07.** The SLE-only KG build step was removed. The Docker image now runs `python -m med_research.cli disease validate --all --strict` at build time to verify all seven disease modules.

**Historical audit (2026-07-25):** `Dockerfile:25` ran `python -m med_research.cli kg --disease sle --export`. Only the SLE knowledge graph was pre-built into the Docker image. All 6 other diseases were absent.

**What this means:**
- Running the pipeline for RA, MS, IBD, SS, SSc, or T1D inside Docker requires building the KG from scratch at runtime (slow).
- The `docker-compose.yml` volume mounts assume the KG is already built.

**Recommended approach:**
Either build all 7 disease KGs at image build time, or remove this line and build at runtime on first request.

**Estimated effort:** Low (loop over diseases or remove the line)

---

### 8. Dockerfile Installs Package Twice

> **Resolved 2026-08-07.** The duplicate `pip install -e ".[all]"` in the runtime stage was removed; only the `deps` stage installs the package.

**Historical audit (2026-07-25):** `Dockerfile:16` and `Dockerfile:22` both ran `pip install -e ".[all]"` in `deps` and `runtime` stages.

**What this means:**
- Wasted build time (second install does nothing useful since `COPY . .` doesn't change the installed editable package).
- The second install at L22 suggests confusion about what editable installs do.

**Recommended approach:**
Remove line 22. The editable install from the `deps` stage is inherited via `COPY --from=deps`.

**Estimated effort:** Low (delete one line)

---

### 9. `scripts/expand_kg.py` Writes to v1 Legacy Data Paths

> **Resolved 2026-08-07.** `scripts/expand_kg.py` now writes to `src/med_research/diseases/{disease_id}/data/` aligned with the v2 package layout.

**Historical audit (2026-07-25):** `scripts/expand_kg.py:9` resolved to root `knowledge_graph/data/` — the **v1 legacy** directory, NOT v2 `src/med_research/diseases/{id}/data/`.

**What this means:**
- Any KG expansion for RA, IBD, SS, T1D, MS, SSc writes new data to the v1 directory that the v2 pipeline won't read.
- Running `expand_kg.py` silently populates the wrong location.

**Recommended approach:**
Rewrite to use `src/med_research/diseases/{id}/data/` paths aligned with the v2 package structure.

**Estimated effort:** Low (path update in one file)

---

### 10. Silent Exception Swallowing in GWAS — `except: pass`

> **Resolved 2026-08-07.** GWAS API error paths in `gwas.py` now log HTTP 404s, connection/timeouts, and unexpected errors via `logger.info`/`logger.warning` instead of silent `pass`.

**Historical audit (2026-07-25):** `src/med_research/pipeline/bioinformatics/gwas.py:125-133` had **four consecutive empty except blocks**:
```python
try:
    # fetch variant data
except Exception:
    pass
```

**What this means:**
- HTTP 404s, 5xx errors, connection timeouts, DNS failures, and JSON parse errors are **all silently swallowed** with zero logging.
- The function returns an empty list as if no data exists.
- The user sees "GWAS complete" with no results and no indication anything went wrong.

**Recommended approach:**
Log each error type distinctly. Only suppress 404s (expected). Reraise or return empty list for transient errors after retry. At minimum, log the error.

**Estimated effort:** Low (add logging in 4 except blocks)

---

### 11. Silent `ImportError: pass` in ML Predictor

> **Resolved 2026-08-07.** Optional imports set `NP_AVAILABLE`, `SKLEARN_AVAILABLE`, `XGB_AVAILABLE`, and `SHAP_AVAILABLE` flags with `logger.warning` on failure. `require_ml_dependencies()` raises `ConfigurationError` before training when core ML packages are missing.

**Historical audit (2026-07-25):** `src/med_research/pipeline/ml_predictor/predictor.py:48-67` had **three consecutive `except ImportError: pass` blocks** that silently disabled sklearn, XGBoost, and SHAP.

**What this means:**
- User runs ML pipeline, everything "completes", but the model was never actually trained because imports silently failed.
- `train_and_predict()` at L197 fails with `ImportError` — but far too late to understand what went wrong.

**Recommended approach:**
Set flags at import time and log warnings when optional dependencies are missing. Raise `ConfigurationError` early.

**Estimated effort:** Low (3 changed except blocks)

---

## High

### 12. Disease Configs Are Stubs — Only SLE Has Real Data

**Current state:** Of 7 diseases under `src/med_research/diseases/`, only SLE has complete configuration. The other 6 diseases have near-empty configs.

**Comparison:**
| Disease | `CAR_T_SCORES` | `DRUG_INDUCED_LUPUS_RISK` | Symptoms | PubMed Queries |
|---|---|---|---|---|
| `sle` | 5 scored tables (~45 genes each, 1–10 scale) | 3 tiers populated (24 drugs) | 51 items | 5 queries |
| `ra` | `{}` (empty) | 3 empty tiers | 24 items | 5 queries |
| `ibd` | `{}` (empty) | 3 empty tiers | 25 items | 4 queries |
| `ms` | `{}` (empty) | 3 empty tiers | 23 items | 5 queries |
| `ss` | `{}` (empty) | 3 empty tiers | 21 items | 3 queries |
| `ssc` | `{}` (empty) | 3 empty tiers | 25 items | 4 queries |
| `t1d` | `{}` (empty) | 3 empty tiers | 19 items | 4 queries |

**Impact:**
- `car_t_predictor/predictor.py` reads `CAR_T_SCORES` from the disease config at `src/med_research/pipeline/car_t_predictor/predictor.py:140` (`score_gene()`). With an empty dict, **all genes get a score of 0 for every CAR-T category**, making the entire CAR-T predictor output meaningless for non-SLE diseases.
- `adverse_events/profiler.py` calls `get_drug_induced_lupus_risk()` from `diseases/base.py:142`. With empty lists, **all drugs are classified as zero risk**, making the safety assessment a no-op.
- GWAS, enrichment, PPI modules hardcode lupus-specific terms (e.g., `gwas.py` searches "lupus OR SLE" by default; `enrichment.py` has `get_lupus_gene_list()`; `literature_mining/miner.py:50-59` hardcodes lupus PubMed queries in `DEFAULT_QUERIES`).

**The CLI supports `--disease ra` but produces garbage for anything other than SLE.** `"sle"` is hardcoded as the default in 24+ locations across CLI, base class, and pipeline modules.

**Recommended approach:**
1. Populate `CAR_T_SCORES` for all 6 remaining diseases with disease-appropriate scoring tables.
2. Rename `DRUG_INDUCED_LUPUS_RISK` to a disease-agnostic name (e.g., `DRUG_SAFETY_RISK`) or guard it as SLE-only.
3. Add a validation check at pipeline startup that warns/errors if a disease has empty critical configs.
4. Audit bioinformatics and literature modules for SLE-specific hardcoded values — make disease_id-driven.
5. Make `--disease` a required argument in CLI, not defaulting to "sle".

**Estimated effort:** High (requires domain expertise to populate scoring tables, 6 diseases x 5+ tables each)

---

### 13. Base Module / Plugin Interface — Every Module Has a Different API

> **Resolved 2026-08-07.** All 20 pipeline modules now implement `BasePipelineModule` via per-module adapters in `src/med_research/pipeline/*/adapter.py`. `registry.py` provides `get_module()`, `list_modules()`, and CLI/web dispatch through a uniform `run()` / `report()` contract. `python -m med_research.cli modules --json` lists all registered modules.

**Historical audit (2026-07-25):** There was **no common interface** across the 19 pipeline modules. Each had a unique API surface.

**API diversity:**
| Module | Init/Entry | Main Method | Signature |
|---|---|---|---|
| `knowledge_graph.builder` | `build_graph(disease_id)` | — | `-> nx.MultiDiGraph` |
| `drug_repurposing.engine` | `DrugRepurposingEngine(disease_id)` | `.run()` | `-> None` (stores in `self.results`) |
| `bioinformatics.gwas` | `run_gwas_analysis(use_cache, max_studies)` | — | `-> None` (prints to stdout) |
| `bioinformatics.enrichment` | `run_enrichment_analysis(use_cache)` | — | `-> None` |
| `bioinformatics.ppi` | `run_ppi_analysis(use_cache, confidence)` | — | `-> None` |
| `literature_mining.miner` | `LiteratureMiner()` | `.search(max_articles, ...)` | `-> list` |
| `virtual_screening.screening` | `screen_compounds(target_genes, ...)` | — | `-> dict` |
| `clinical_trials.tracker` | `track_trials(query, max_results, ...)` | — | `-> dict` |
| `ml_predictor.predictor` | `train_and_predict(G, top_n)` | — | `-> dict` |
| `drug_synergy.engine` | `compute_synergy(progress_callback)` | — | `-> list` |
| `adverse_events.profiler` | `score_all_drugs(progress_callback)` | — | `-> list` |
| `network_pharmacology.analyzer` | `compute_all_metrics(progress_callback)` | — | `-> dict` |
| `gene_expression.correlator` | `compute_all_correlations(progress_callback, ...)` | — | `-> list` |
| `car_t_predictor.predictor` | `compute_all_scores(progress_callback)` | — | `-> list` |
| `biomarker_discovery.discover` | `compute_biomarker_matrix(progress_callback)` | — | `-> list` |
| `semantic_search.engine` | `SemanticSearchEngine(model_name)` | `.search(query, top_k)` | `-> list` |
| `evidence.gatherer` | `gather_evidence(query, sources, ...)` | — | `-> dict` |
| `evidence.extractor` | `extract_all(query, sources, ...)` | — | `-> dict` |
| `cross_disease.analyzer` | `compute_cross_disease_analysis(progress_callback)` | — | `-> dict` |

**Inconsistencies:**
- Some return results, others store in `self.results`, others only print.
- 3 are classes (`DrugRepurposingEngine`, `LiteratureMiner`, `SemanticSearchEngine`), 16 are bare functions.
- Some accept `disease_id`, others don't (e.g., `run_gwas_analysis()` is hardcoded to SLE).
- Progress callbacks are inconsistently supported (~6 modules accept `progress_callback`).
- The CLI (`cli.py:500-512`) has a hardcoded `PIPELINE_STEPS` registry — every new module requires a CLI code change.

**Recommended approach:**
1. Create `src/med_research/pipeline/base.py`:
   ```python
   from abc import ABC, abstractmethod
   from dataclasses import dataclass

   @dataclass
   class PipelineResult:
       success: bool
       data: dict[str, Any]
       errors: list[str]

   class BasePipelineModule(ABC):
       def __init__(self, disease_id: str, progress_callback=None):
           self.disease_id = disease_id
           self.progress_callback = progress_callback

       @abstractmethod
       def run(self) -> PipelineResult: ...

       @property
       @abstractmethod
       def name(self) -> str: ...
   ```
2. Make every module class inherit from `BasePipelineModule`.
3. Update the CLI to auto-discover modules via `__subclasses__()` or a registry.
4. Standardize output: every `run()` returns `PipelineResult`.

**Estimated effort:** High (refactoring 19 modules to a common contract, updating all callsites)

---

### 14. Dependency Lock File — Builds Are Non-Reproducible

**Current state:** No lock file of any kind exists. Neither `poetry.lock` nor `requirements.lock`.

**What exists:**
- `requirements.txt`: Unpinned floor versions (e.g., `networkx>=3.2`).
- `requirements-dev.txt`: Same pattern (`pytest>=7.0`, `ruff>=0.1.0`).
- `pyproject.toml`: Floor version dependency groups (`ml`, `cheminformatics`, `nlp`, `semantic`, `dev`, `all`).
- **No pip freeze output committed.**
- 7 per-module legacy `requirements.txt` files (`knowledge_graph/`, `clinical_trials/`, `virtual_screening/`, `drug_repurposing/`, `bioinformatics/`, `literature_mining/`, `ml_predictor/`) list potentially different/stale versions and risk accidental use.

**Impact:**
- Two developers running `pip install -r requirements.txt` a month apart get different dependency trees.
- CI builds are non-reproducible — a transitive dependency update can break the build.
- Dockerfile installs from un-pinned `requirements.txt`.

**Recommended approach:**
1. Adopt `pip-tools`: create `requirements.in`, generate pinned `requirements.txt` via `pip-compile`.
2. Or adopt Poetry/PDM for dependency management + lock file (cleaner long-term, already uses `pyproject.toml`).
3. Delete all legacy per-module `requirements.txt` files.
4. Pin `requirements-dev.txt` similarly.

**Estimated effort:** Low (mechanical pinning)

---

### 15. Proper Error Types — 39 Bare `except Exception` + Zero Custom Exceptions

**Current state:** **39 occurrences** of `except Exception` / `except Exception as e` with **zero custom exception classes defined.**

**Breakdown by file:**
| File | Count | Pattern |
|---|---|---|
| `virtual_screening/docking.py` | 6 | Subprocess/Docker errors for Vina |
| `bioinformatics/gwas.py` | 4 | API HTTP errors, JSON parse errors |
| `gene_expression/geo.py` | 4 | GEO API errors, parse errors |
| `gene_expression/correlator.py` | 3 | File I/O, parse errors |
| `ml_predictor/predictor.py` | 3 | ML training errors |
| `semantic_search/engine.py` | 3 | ChromaDB index errors |
| `bioinformatics/ppi.py` | 3 | STRING API + cache errors |
| `bioinformatics/enrichment.py` | 2 | Enrichr API errors |
| `literature_mining/ner.py` | 2 | spaCy model errors |
| `literature_mining/miner.py` | 1 | PubMed API errors |
| `virtual_screening/screening.py` | 2 | RDKit + API errors |
| `clinical_trials/tracker.py` | 1 | ClinicalTrials.gov API errors |
| `bioinformatics/report.py` | 1 | SVG generation errors |
| `network_pharmacology/analyzer.py` | 1 | Community detection errors |
| `gene_expression/signature.py` | 1 | Signature parsing errors |
| `web/routers/jobs.py` | 1 | Celery job errors |
| `cli.py` | 1 | Pipeline orchestrator catch-all |

**Problematic patterns:**
1. **18 silent `except Exception:`** (no `as e`) — completely swallowing errors.
2. **Indistinguishable error types:** Network timeout, JSON parse error, file-not-found, algorithmic bug — all fall into the same block.
3. **No retry logic** on transient network errors in any API-calling module.
4. `web/routers/jobs.py:176-185` uses `with suppress(Exception)` which catches `KeyboardInterrupt` and `SystemExit`, preventing clean shutdown.
5. `ml_predictor/predictor.py:179-185` returns `{}` on ANY exception including memory errors and networkx bugs.

**Recommended approach:**
1. Create `src/med_research/exceptions.py`:
   ```python
   class MedResearchError(Exception): ...
   class DataValidationError(MedResearchError): ...
   class ExternalAPIError(MedResearchError): ...
   class APITimeoutError(ExternalAPIError): ...
   class APIQuotaError(ExternalAPIError): ...
   class APIParseError(ExternalAPIError): ...
   class CacheCorruptionError(MedResearchError): ...
   class ConfigurationError(MedResearchError): ...
   ```
2. Replace bare `except Exception` with specific catches:
   - API calls → catch `urllib.error.URLError` → raise `APITimeoutError`; catch `json.JSONDecodeError` → raise `APIParseError`.
   - Cache loads → catch `json.JSONDecodeError`, `FileNotFoundError` → raise `CacheCorruptionError`.
   - Config loads → catch `KeyError`, `TypeError` → raise `ConfigurationError`.
3. Add retry with exponential backoff + jitter in `api_get()` (`evidence/gatherer.py:150`).
4. The CLI orchestrator (`cli.py:502-506`) can then distinguish retriable vs. fatal errors.

**Estimated effort:** Medium (creating exception hierarchy, touching ~39 catch sites)

---

### 16. Configuration Management — No `.env.example`, Scattered Config

**Current state:** Environment variables used across the codebase are undocumented. There is no `.env.example` file.

**Undocumented environment variables:**
`HOST`, `PORT`, `DEBUG`, `CORS_ORIGINS`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `USE_CACHE`, `OPENAI_API_KEY`, `OPENAI_API_BASE`, `LLM_EXTRACTOR_MODEL`, `ENTREZ_EMAIL`

**Other configuration issues:**
- `.env` is **not listed** in `.gitignore` — accidental commit could leak API keys.
- `OPENAI_API_KEY` defaults to `""` (`evidence/extractor.py:52`) — empty string, not `None`. Calls OpenAI API with no auth, cryptic failure.
- `--model` CLI flag (`cli.py:132`) defaults to `""` but help text implies "gpt-4o-mini". The handler at L448 does `model=args.model or None` which falls through to a different default.
- `pyproject.toml` uses `{name = "Medical Research Platform"}` (L13) — not a person/org name.
- `pyproject.toml:63-68` package-data patterns are relative to `src/med_research/` but the actual file structure may not match `"diseases/*/data/*.json"`.
- Inconsistent config loading: some use `importlib.util.spec_from_file_location`, others use `json.load()`, others `os.environ.get()`.
- `ruff.toml:18` suppresses `B008` (function calls in arg defaults) project-wide, masking risky mutable-default patterns.

**Recommended approach:**
1. Create `.env.example` listing all variables with descriptions and defaults.
2. Add `.env` and `.env.*` to `.gitignore`.
3. Change `OPENAI_API_KEY` default to `None` and validate at init time.
4. Fix `--model` CLI default to `"gpt-4o-mini"` explicitly.
5. Unify config loading on Pydantic Settings or a single loader module.
6. Enable `B008` in ruff and fix cases with `None` sentinels.

**Estimated effort:** Low (mostly documentation + a few one-line fixes)

---

### 17. Web API v2 Mounts v1 Legacy Static Directories

> **Resolved 2026-08-07.** Resolved with Issue #3 cleanup. `web/main.py` mounts only v2 pipeline static paths; legacy v1 directories were removed from the working tree.

**Historical audit (2026-07-25):** `src/med_research/web/main.py:83-101` mounted 16 `StaticFiles` directories from the project root's legacy v1 directories:
```python
app.mount("/static/adverse_events", StaticFiles(directory=str(REPO_ROOT / "adverse_events")))
app.mount("/static/biomarker_discovery", StaticFiles(directory=str(REPO_ROOT / "biomarker_discovery")))
# ... 14 more legacy paths
```

**What this means:**
- 16 root-level v1 directories (containing code, data, and HTML reports) are exposed as static files.
- If someone puts a malicious HTML file in any of those directories, it becomes served.
- `.gitignore` **does not cover** `adverse_events/data/`, `car_t_predictor/data/`, `biomarker_discovery/data/`, `network_pharmacology/data/`, `semantic_search/data/` — generated output could be accidentally committed.

**Recommended approach:**
Serve only v2 output from `src/med_research/pipeline/*/data/` directories. Remove all v1 static mounts.

**Estimated effort:** Low (update static mount paths)

---

### 18. Hardcoded Values in Web API

**Current state:**
- `src/med_research/web/routers/system.py:24` returns version `"1.0.0"` but the project is v2.0.0 per `pyproject.toml:7`.
- `src/med_research/web/routers/system.py:45` returns `"tests_passing": 297` — a magic number that will go stale with every test change.
- `src/med_research/pipeline/literature_mining/miner.py:46` hardcodes `DEFAULT_EMAIL = "lupus-research@example.com"` — violates NCBI Entrez guidelines requiring a real contact email for rate-limit identification.
- `src/med_research/web/config.py:10` / `docker-compose.yml:48` / `Dockerfile:29` all hardcode port 8000 — changing requires 3 edits.

**Recommended approach:**
1. Read version from `importlib.metadata.version("med-research")`.
2. Remove `tests_passing` entirely or derive from CI output.
3. Load `ENTREZ_EMAIL` from environment variable.
4. Use env var for PORT everywhere.

**Estimated effort:** Low (4 targeted fixes)

---

## Medium

### 19. Progress Reporting — Long-Running Steps Give No Feedback

**Current state:** Most pipeline steps are I/O-bound (API calls to GWAS Catalog, STRING, Enrichr, PubMed, ClinicalTrials.gov, GEO, FDA) and can take minutes with **zero incremental feedback.**

**7 modules already support `progress_callback`:** `drug_synergy`, `adverse_events`, `network_pharmacology`, `gene_expression`, `car_t_predictor`, `biomarker_discovery`, `cross_disease`.

**11 modules without any progress feedback:** `knowledge_graph`, `drug_repurposing`, `bioinformatics/gwas`, `bioinformatics/enrichment`, `bioinformatics/ppi`, `literature_mining`, `virtual_screening`, `clinical_trials`, `ml_predictor`, `semantic_search`, `evidence/gatherer`.

**Recommended approach:**
1. Standardize `progress_callback(step: str, current: int, total: int)` across all modules.
2. Add `tqdm` integration in CLI: auto-wrap when `progress_callback is None`.
3. Have callback emit WebSocket messages in the web API.

**Estimated effort:** Medium (touches 19 modules, additive pattern)

---

### 20. Caching Strategy — Inconsistent, No TTL, No Central Manager

> **Substantially complete 2026-08-07.** `CacheManager` in `src/med_research/cache.py` centralizes namespaced get/set with TTL, `--clear-cache` / `--cache-ttl` CLI flags, and legacy JSON migration helpers (`load_legacy_json`, `cache_get`/`cache_set`). GWAS, enrichment, PPI, literature mining, evidence gatherer/extractor, and gene expression modules migrated. Remaining gap: some modules still write legacy flat files alongside the central store. **2026-08-08:** the legacy base cache files (gwas/enrichment/extraction/pubmed/ct/geo) were verified as read-only migration inputs (current code writes via `CacheManager` and per-disease `{stem}_{disease}.json` files); the regenerated per-disease outputs, module result files, and legacy caches were untracked and gitignored so runs no longer dirty `git status`.

**Historical audit (2026-07-25):** 8+ modules implemented caching independently with different patterns — no TTL, no centralized invalidation, no statistics.

| Module | Cache File(s) | Cache Key | Invalidation |
|---|---|---|---|
| `bioinformatics/gwas.py` | `gwas_cache.json` | Single file | None |
| `bioinformatics/ppi.py` | `ppi_cache.json` | Sorted symbol list + confidence | Confidence check |
| `bioinformatics/enrichment.py` | `enrichment_cache.json` | Single file | None |
| `clinical_trials/tracker.py` | `ct_cache.json` | Single file | None |
| `literature_mining/miner.py` | `pubmed_cache.json` | Single file | None |
| `evidence/gatherer.py` | `evidence_cache.json` | `query\|\|\|source\|\|\|max_results` | None |
| `evidence/extractor.py` | `extraction_cache.json` | `article_id + model` | None |
| `gene_expression/geo.py` | `geo_cache/` directory | Named per search | None |

**Inconsistencies:**
- No unified cache directory — files scattered across module dirs.
- No TTL/expiration — cache lives forever.
- `--no-cache` handled per-module. No `--clear-cache` global flag.
- `USE_CACHE` env var in web config not respected by pipeline modules.

**Recommended approach:**
1. Create `src/med_research/cache.py` with `CacheManager(cache_dir, ttl_hours=24)`.
2. All modules call `cache.get(namespace, cache_key)` / `cache.set(...)`.
3. Add `--cache-ttl` and `--clear-cache` CLI flags.
4. Auto-invalidate entries older than TTL.

**Estimated effort:** Medium (refactoring ~8 cache implementations, new CacheManager class)

---

### 21. Separated Compute/Report — Interleaved Concerns

> **Substantially complete 2026-08-07.** Adapters own `report()` as a separate step from `run()`; CLI and web services call report generation at the dispatch layer rather than inside engine `analyze()` methods. Legacy engines may still inline HTML generation when invoked directly via `__main__`.

**Historical audit (2026-07-25):** 7 modules called `generate_html_report()` inline inside their `analyze()` method.

**Affected modules:** `drug_repurposing`, `drug_synergy`, `adverse_events`, `biomarker_discovery`, `car_t_predictor`, `cross_disease`, `network_pharmacology`

**What this means:**
- Can't get results without generating HTML (side effect).
- Can't generate PDF/CSV/JSON reports without refactoring.
- Report generation untestable independently.

**Recommended approach:**
1. `run()` returns `PipelineResult` (data only).
2. `generate_html_report(results)` becomes a pure function in `report.py`.
3. Call report generation from CLI/web service layer, not inside the engine.

**Estimated effort:** Medium (refactoring 7 modules, clean separation)

---

### 22. Integration Tests — Zero Organized Integration Tests

> **Substantially complete 2026-08-07.** `tests/integration/` holds CLI subprocess smokes (`test_cli_smoke.py`), pipeline E2E smoke (`test_pipeline_e2e.py`), and auto-marked `integration` tests via `conftest.py`. Evidence gatherer tests use `responses`-based HTTP mocks (`tests/evidence_http_fixtures.py`). `make test-integration` / `make test-offline` targets run suites independently. Remaining gaps: `unit` marker still auto-applied rather than explicit on most tests; full KG→all-modules→report E2E not yet automated. **2026-08-08:** added a `network` marker (registered in `pyproject.toml`) for tests that require live external APIs; the RCSB-downloading docking receptor-prep test is tagged `network` and excluded from the PR docking gate, which runs the fast synthetic prep tests on every push. The `unit`-explicit and E2E gaps remain open.

**Historical audit (2026-07-25):** ~718 total tests. ~628 pure unit tests. ~90 tests with integration-like behavior but **not marked, not separated, not independently runnable.**

**Problems:**
- `unit` marker defined in `pytest.ini` but **never applied** to any test.
- `slow` marker used on ~70 tests but doesn't distinguish unit/integration.
- No `integration` marker, no `tests/integration/` directory, no `make test-integration` target.
- `test_evidence_gatherer.py` (15 tests) makes **real external API calls** — fails offline, consumes API quotas.
- 14 tests across 10 files use `subprocess.run(["med-research", ...])` — can't track code coverage.
- No end-to-end pipeline test (KG → repurposing → bioinformatics → ML → report).

**Recommended approach:**
1. Create `tests/integration/` directory with `integration` marker.
2. Apply `unit` marker to all existing unit tests.
3. Add `make test-unit` and `make test-integration` targets.
4. Write 3-5 smoke tests running full pipeline with mock data.
5. Replace real API calls with `responses` library or VCR cassettes.
6. Replace subprocess CLI tests with direct imports.
7. Add `pytest-xdist` for parallel test execution (`-n auto`).

**Estimated effort:** Medium (reorganizing ~90 tests, writing 3-5 new pipeline smoke tests)

---

### 23. `time.sleep()` Rate Limiting Without Jitter

**Current state:** 14 `time.sleep()` calls across the codebase use fixed intervals:
- `cli.py:507` — 0.3s between pipeline steps
- `gwas.py:97,135,195,295,550` — GWAS API rate limiting
- `tracker.py:129` — ClinicalTrials.gov rate limiting
- `geo.py:139,204` — GEO API rate limiting
- `miner.py:131,231,258` — PubMed rate limiting
- `monitor.py:451` — Evidence monitor polling
- `bioinformatics_service.py:50` — Web service polling

**What this means:**
- Fixed intervals cause thundering herd problems if multiple processes run.
- No adaptation to API response headers (e.g., `Retry-After`, `X-RateLimit-Reset`).
- Competitive API clients with jitter get priority over fixed-interval clients.

**Recommended approach:**
Replace with exponential backoff + jitter, respecting `Retry-After` headers where available.

**Estimated effort:** Low (add backoff utility, update ~14 call sites)

---

### 24. Missing Input Validation in Web API

**Current state:**
- Query parameters lack length/pattern validation: `src/med_research/web/routers/kg.py:42` accepts `q: str` with no `min_length` or `max_length`.
- No request body size limits configured — arbitrary payloads accepted.
- WebSocket job IDs not validated as UUIDs (`jobs.py:116-117`) — any string accepted.

**Recommended approach:**
1. Add `min_length=1`, `max_length=500` to search queries.
2. Add `Request` body size middleware (e.g., 10 MB limit).
3. Validate job_id as UUID format.

**Estimated effort:** Low (adding validation decorators/parameters)

---

### 25. `ruff.toml` B008 Suppressed Project-Wide

**Current state:** `ruff.toml:18` ignores `B008` (do not perform function calls in argument defaults). This masks risky patterns like mutable default arguments.

**Recommended approach:**
Enable B008. Fix specific cases with `None` sentinels and factory patterns.

**Estimated effort:** Low (enable rule, fix ~5 cases)

---

### 26. Subprocess Tests Don't Provide Coverage

**Current state:** 14 tests across 10 files call `subprocess.run(["med-research", ...])` to exercise CLI. Coverage tools can't track code executed in subprocesses.

**Recommended approach:**
Replace with direct `import` calls and `monkeypatch` for CLI entry points.

**Estimated effort:** Low (refactoring 14 test invocations)

---

### 27. Stale Documentation Files

**Current state:**
- Root `main.py` (967 lines) has docstring referencing "Lupus Research Platform" and old usage patterns that no longer work.
- Root `index.html` branded "Lupus Research Platform" but v2 is multi-disease.
- `lupus_research.md`, `exa_ai_research.md` are v1 docs at root.

**Recommended approach:**
- Replace `main.py` with a one-line wrapper calling `med_research.cli.main()` or delete.
- Rebrand `index.html` to "Medical Research Platform."
- Archive or delete v1 markdown docs.

**Estimated effort:** Low (file updates/deletions)

---

### 28. WebSocket Error Handler Swallows All Exceptions

**Current state:** `src/med_research/web/routers/jobs.py:176-185`:
```python
with suppress(Exception):  # catches ALL including KeyboardInterrupt
    ...
```

**What this means:**
`Ctrl+C` (KeyboardInterrupt) and `SystemExit` are silently suppressed, preventing clean shutdown.

**Recommended approach:**
Catch specific expected exceptions, not `Exception`. Let `KeyboardInterrupt` and `SystemExit` propagate.

**Estimated effort:** Low (one block change)

---

### 29. `ibd/data/relationships.json` Missing

> **Resolved 2026-08-07.** `ibd/data/relationships.json` is present and validated; `disease validate --all --strict` passes for all seven diseases.

**Historical audit (2026-07-25):** `src/med_research/diseases/ibd/data/` contained `drugs.json`, `genes.json`, `pathways.json`, `profile.json` but **no `relationships.json`**. All other 6 diseases had this file.

**Impact:** `Disease("ibd").load_relationships()` raises `FileNotFoundError`. Graph cannot be built for IBD.

**Recommended approach:**
Generate `ibd/data/relationships.json` or handle missing relationships gracefully (empty graph with warning).

**Estimated effort:** Low (generate missing file or add fallback)

---

## Low

### 30. Type Hints — Bare `-> dict` Everywhere

**Current state:** Type hints present but shallow.

**Patterns observed:**
- **100+ functions** return `-> dict` instead of `-> dict[str, Any]`, `-> dict[str, list[dict]]`, etc.
- Parameter annotations inconsistent — some functions fully annotated, others (older code) have none.
- No `TypedDict` or `Protocol` usage despite well-known data shapes.
- No generics — `-> list` instead of `-> list[dict]` or `-> list[RepurposingCandidate]`.
- `from __future__ import annotations` used in only 2 files (`cli.py`, `diseases/base.py`).

```python
# Current                              # Should be
def load_json(path: Path) -> dict:     def load_json(path: Path) -> dict[str, Any]:
def load_kg_genes() -> dict:           def load_kg_genes() -> dict[str, GeneDict]:
```

**Recommended approach:**
1. Define `TypedDict` classes: `GeneDict`, `DrugDict`, `PathwayDict`, `CandidateDict`, `TrialDict`.
2. Add full annotations to all public functions.
3. Enable `mypy` or `pyright` in CI.

**Estimated effort:** Medium-High (touches ~200 function signatures across 19 modules)

---

### 31. Async/Concurrent Pipeline — Sequential I/O-Bound Steps

> **Mitigated 2026-08-07.** `scheduler.py` derives topological levels from adapter `depends_on` metadata and `run-all --parallel` executes independent levels via `ThreadPoolExecutor`. Sequential mode remains the default. Remaining gap: no async I/O within individual modules; parallelism is module-level only.

**Historical audit (2026-07-25):** CLI pipeline (`cli.py:500-507`) ran all steps sequentially in a `for` loop.

**I/O-bound steps that could run in parallel (no data dependencies):**
Literature mining, GWAS, enrichment, PPI, clinical trials, evidence gathering, gene expression, virtual screening — all read from the KG (built first) and have no interdependencies.

**Recommended approach:**
1. Define DAG of pipeline dependencies.
2. Use `concurrent.futures.ThreadPoolExecutor` or `asyncio.gather()` for parallel execution.
3. Add `--parallel` / `--sequential` CLI flag.

**Estimated effort:** Medium (async wrappers, DAG scheduling, thread safety for shared KG reads)

---

### 32. Template-Based Reports — HTML Built with F-strings

**Current state:** 16 HTML reports generated via Python string concatenation/f-strings with inline CSS.

**Problems:**
- Zero template reuse — every report copy-pastes CSS, header/footer.
- XSS risk — `escape_html()` used inconsistently.
- Hard to test individual rendering components.
- Changing style requires editing 16 Python files.

**Recommended approach:**
1. Add `jinja2` to dependencies.
2. Create `src/med_research/templates/` with `base.html`, partials, and per-report templates.
3. `report.py` functions become `render_report(results, template_name) -> str`.
4. Jinja2 auto-escapes HTML by default, eliminating XSS risk.

**Estimated effort:** Medium-Low (creating ~9 templates, refactoring 16 report functions)

---

### 33. Hardcoded Debug Mode via CLI Flag

> **Resolved 2026-08-07.** `cmd_serve` honors `--reload` only when `DEBUG=true`; otherwise it logs a warning and starts without reload. `tests/test_cli.py` mocks `uvicorn.run` to assert the guard, and `make serve` no longer passes `--reload` by default.

**Historical audit (2026-07-25):** `src/med_research/cli.py:163` — `--reload` flag on `serve` command enables uvicorn reload, which can leak stack traces and source in production.

**Recommended approach:**
Restrict `--reload` to only when `DEBUG=true` or remove entirely from production path.

**Estimated effort:** Low (guard clause)

---

### 34. No Rate Limiting on Web API

> **Resolved 2026-08-08.** `RateLimitMiddleware` now delegates to a `RateLimitStore` (`src/med_research/web/rate_limit.py`): `RedisRateLimitStore` provides distributed sliding-window limiting via a Redis sorted set + atomic Lua script (shared across app instances, keyed by client IP, fails open on Redis errors), with `InMemoryRateLimitStore` as the per-process fallback when Redis is unreachable (`create_rate_limit_store` probes with a 1s-timeout ping). Store checks run off the event loop (`asyncio.to_thread`) so a slow Redis call cannot stall the server. Configured via `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW` / `REDIS_RATE_LIMIT_URL` (defaults to the Celery broker URL). Originally mitigated 2026-08-07 with the in-memory-only `RateLimitMiddleware`; the distributed backend was the remaining #34 follow-up and is now implemented.

**Historical audit (2026-07-25):** `src/med_research/web/main.py:52` had no rate limiting middleware. All endpoints accepted unlimited requests.

**Recommended approach:**
Add `slowapi` or custom Redis-based rate limiter.

**Estimated effort:** Low (adding middleware, 1 dependency)

---

### 35. Dockerfile `ENTRYPOINT` Uses Hardcoded Ports

> **Resolved 2026-08-07.** `Dockerfile` uses `EXPOSE 8000` and `CMD ["serve", "--host", "0.0.0.0"]` without a hardcoded `--port`; `docker-compose.yml` passes `PORT` via environment and `${PORT:-8000}` port mapping.

**Historical audit (2026-07-25):** `Dockerfile:29` — `"--port", "8000"` hardcoded. Changing port required Dockerfile edit.

**Recommended approach:**
Use `EXPOSE 8000` and let `--port` default from env var.

**Estimated effort:** Low (one line change)

---

### 36. docker-compose Volume Paths Reference Non-Existent Structure

> **Resolved 2026-08-07.** Removed `disease-data` and `pipeline-data` named volumes. `web`, `worker`, and `pipeline` services now mount `./data:/app/data` for runtime persistence.

**Historical audit (2026-07-25):** `docker-compose.yml:38-39,57-58,68-69` mapped volumes like `/app/src/med_research/diseases` and `/app/src/med_research/pipeline` but these paths didn't match the container layout cleanly.

**Recommended approach:**
Map only `./src:/app/src:ro` or `./data:/app/data`.

**Estimated effort:** Low (volume path cleanup)

---

### 37. pyproject.toml Package-Data Patterns May Not Match

> **Resolved 2026-08-07.** `tests/test_package_data.py` verifies disease JSON, web static assets, and pipeline data files via `importlib.metadata.files("med-research")` (with an editable-install fallback via `importlib.resources`).

**Historical audit (2026-07-25):** `pyproject.toml:63-68` package-data patterns were relative to `src/med_research/` and had not been verified against a built wheel.

**Recommended approach:**
Test with `python -m build --wheel` and verify package contents. Remove or fix patterns.

**Estimated effort:** Low (build verification)

---

### 38. Web API Router File Organization

> **Resolved 2026-08-07.** `jobs_router` consolidated into `src/med_research/web/routers/__init__.py` with domain-grouping comments; `main.py` includes routers from the single registry only.

**Historical audit (2026-07-25):** `src/med_research/web/routers/` had 17+ router files with no consistent domain grouping, and `jobs_router` was included separately in `main.py`.

**Recommended approach:**
Group routers by domain (kg, analysis, evidence, system) with consistent naming.

**Estimated effort:** Low (reorganization)

---

### 39. `index.html` Branded as v1

> **Resolved 2026-08-07.** Root `index.html`, API OpenAPI tag descriptions in `web/config.py`, and the knowledge-graph explorer page use multi-disease / disease-agnostic branding.

**Historical audit (2026-07-25):** Root `index.html` referenced "Lupus Research Platform" with SLE-specific branding. v2 is multi-disease.

**Recommended approach:**
Rebrand to "Medical Research Platform" or generate dynamically per disease.

**Estimated effort:** Low (HTML updates)

---

---

## Positive Findings (No Action Needed)

The following patterns were verified and found to be safe:

- **Zero `assert` statements in non-test code** — no production assertions.
- **Zero `os.system()`, `subprocess(shell=True)`, `eval()`, or `exec()` calls** in `src/med_research/` — no command injection vectors.
- **Zero hardcoded API keys or passwords** (email is fake, API keys loaded from env).
- **Zero `except: pass` without `Exception` qualification** (all pass blocks explicitly catch Exception/ImportError, no bare `except:`).
- Zero circular imports detected.
- No mutable default arguments found in function signatures (B008 rule would catch these).
- No commented-out code blocks of significant size.
- No duplicate function definitions.
- Pydantic v2 used correctly for web API request/response validation.
- `pyproject.toml` properly configured for package discovery, CLI entry points, and optional dependency groups.
- Tests use `conftest.py` with session-scoped fixtures for shared data (efficient).
- No secrets tracked in git history (verified `.gitignore` coverage of data files).

---

## Summary Matrix

> **Historical (2026-07-25 audit).** Severity/effort ratings below predate the 2026-08-07 resolutions. See the header resolved/mitigated list and per-issue resolution notes for current status.

| # | Issue | Severity | Effort | Dependencies |
|---|---|---|---|---|
| 1 | Logging (print everywhere) | Critical | Medium | None |
| 2 | Data validation (no schema) | Critical | Medium-High | Pydantic installed |
| 3 | Pre-reorg cleanup (19 legacy dirs) | Critical | Low | None |
| 4 | No auth on API endpoints | Critical | Medium | None |
| 5 | CORS defaults to `*` | Critical | Low | None |
| 6 | Docker runs as root | Critical | Low | None |
| 7 | Dockerfile hardcodes SLE KG | Critical | Low | None |
| 8 | Dockerfile installs package twice | Critical | Low | None |
| 9 | expand_kg.py writes to v1 paths | Critical | Low | None |
| 10 | Silent pass in GWAS except blocks | Critical | Low | None |
| 11 | Silent ImportError in ML predictor | Critical | Low | None |
| 12 | Disease config stubs (6 diseases) | High | High | Domain expertise |
| 13 | Base module interface | High | High | #15 (error types) |
| 14 | Dependency lock file | High | Low | None |
| 15 | Proper error types (39 sites) | High | Medium | None |
| 16 | No .env.example, scattered config | High | Low | None |
| 17 | Web API mounts v1 static dirs | High | Low | #3 (cleanup) |
| 18 | Hardcoded values (version, email, port) | High | Low | None |
| 19 | Progress reporting | Medium | Medium | #13 (common interface) |
| 20 | Caching strategy | Medium | Medium | None |
| 21 | Separated compute/report | Medium | Medium | #13, #32 |
| 22 | Integration tests | Medium | Medium | #13 |
| 23 | time.sleep() without jitter | Medium | Low | #15 (error types) |
| 24 | Missing input validation in API | Medium | Low | None |
| 25 | ruff B008 disabled project-wide | Medium | Low | None |
| 26 | Subprocess tests no coverage | Medium | Low | None |
| 27 | Stale documentation files | Medium | Low | None |
| 28 | WebSocket swallows KeyboardInterrupt | Medium | Low | #15 (error types) |
| 29 | ibd missing relationships.json | Medium | Low | #2 (validation) |
| 30 | Type hints (bare -> dict) | Low | Medium-High | None |
| 31 | Async/concurrent pipeline | Low | Medium | #13, #15 |
| 32 | Template-based reports | Low | Medium-Low | #21 |
| 33 | --reload flag exposes debug | Low | Low | None |
| 34 | No rate limiting on API | Low | Low | None |
| 35 | Dockerfile hardcoded port | Low | Low | None |
| 36 | docker-compose volume paths | Low | Low | None |
| 37 | pyproject.toml package-data patterns | Low | Low | None |
| 38 | Router file organization | Low | Low | None |
| 39 | index.html v1 branding | Low | Low | None |

### Recommended Execution Order

**Phase 1 — Quick Wins (Low effort, high impact):**
3 → 5 → 6 → 8 → 9 → 10 → 11 → 14 → 16 → 18 → 29

**Phase 2 — Foundation (Medium effort, blocks later work):**
1 → 15 → 7 → 17 → 4 → 20 → 24 → 23 → 25 → 28

**Phase 3 — Architecture (High effort, transformative):**
2 → 13 → 21 → 32 → 19 → 30 → 22 → 26

**Phase 4 — Enhancement:**
31 → 33 → 34 → 35 → 36 → 37 → 38 → 39 → 12 → 27
