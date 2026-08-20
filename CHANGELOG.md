# Changelog

## [Unreleased]

### Added

- **L3 expression consensus for seven Wave 3/4 indications** — disease-specific GEO consensus gene lists (no SLE signature reuse) for `nsclc`, `pancreatic_ductal_adenocarcinoma`, `glioblastoma`, `cystic_fibrosis`, `sickle_cell_anemia`, `heart_failure`, and `non_alcoholic_fatty_liver_disease`. Each list is restricted to symbols in that module's `genes.json`, with tissue-specific GEO search terms and filters (`lung`, `pancreas`, `tumor`, `airway`, `pbmc_blood`, `myocardium`, `liver`).
- **Screening/safety coverage for the same L3 slice** — `SCREENING_PROFILE.reference_drug_ids` now match each module's `drugs.json` catalog (CHEMBL IDs where the KG uses them), NAFLD gained pathway/mechanism keywords, and each module has a catalog-scoped `adverse_events.json` so screening and safety coverage report `ready/full`.

### Verification

- `pytest tests/test_gene_expression.py tests/test_tier_model.py tests/test_report_neutral_terminology.py -q`

---

## [2.1.0] — 2026-08-16

### Added

- **Platform-Wide Disease Catalog Promotion (Waves 3 & 4 — 45+ Tier-1 Curated Indications)**:
  - **Solid Tumors & Oncology**: `nsclc` (Non-Small Cell Lung Cancer), `colorectal_cancer`, `triple_neg_breast_cancer`, `pancreatic_ductal_adenocarcinoma`, `glioblastoma`, `acute_myeloid_leukemia`, `melanoma`, `breast_cancer`.
  - **Rare Genetic & Neuromuscular**: `cystic_fibrosis`, `sickle_cell_anemia`, `huntington_disease`, `spinal_muscular_atrophy`, `gaucher_disease`, `fabry_disease`, `phenylketonuria`, `wilson_disease`.
  - **Psychiatric & CNS (Wave 3)**: `major_depressive_disorder`, `schizophrenia`, `bipolar_disorder`, `epilepsy`.
  - **Metabolic & Hepatic (Wave 3)**: `non_alcoholic_fatty_liver_disease` (MASH/NASH), `obesity`, `t1d`, `hyperlipidemia`.
  - **Connective Tissue, Autoimmune & Dermatology (Wave 3)**: `scleroderma`, `systemic_scleroderma`, `alopecia_areata`, `vitiligo`, `celiac_disease`, `lupus_nephritis`, `sjogren_syndrome`.
  - **Cardiovascular & Respiratory**: `coronary_artery_disease`, `heart_failure`, `dilated_cardiomyopathy`, `essential_hypertension`, `coronary_atherosclerosis`, `atherosclerosis`, `copd`, `asthma`, `t2d`.
  - Every promoted module has 100% strict schema validation, complete clinical configs (`SYMPTOMS`, `PUBMED_QUERIES`, `TRIAL_QUERY`, `GWAS_SEARCH_TERMS`, `CAR_T_SCORES`, `DRUG_SAFETY_RISK`), and registered GTEx target tissues in `drug_repurposing/engine.py`.

- **Interactive 3D Molecular / AlphaFold Visualizer in Web Dashboard**:
  - Embedded `3Dmol.js` with AlphaFold PDB coordinate rendering directly inside the web UI.
  - Per-residue **pLDDT confidence spectrum** color ramps (Dark Blue >90, Cyan 70-90, Yellow 50-70, Orange <50).
  - AutoDock Vina 3D search box wireframes and interactive pocket residue inspection.

- **Interactive Cytoscape.js Multi-Disease Network Topology Explorer**:
  - Multi-disease merged subgraph construction in `pipeline/knowledge_graph/network_analytics.py`.
  - Dynamic force-directed (`cose`), concentric, hierarchical (`breadthfirst`), and circle layouts in the web UI.
  - Identification of multi-disease shared target hubs, drug repurposing bridges, and degree centrality node scaling.
  - Real-time `/api/kg/multi-network` endpoint and PNG export functionality.

- **Single-Cell RNA-seq (scRNA-seq) Cell-Type Deconvolution & Specificity Engine**:
  - Created `pipeline/gene_expression/single_cell.py` providing Yanai Tau ($\tau$) cell-type specificity index computation and marker deconvolution across immune, stromal, epithelial, and tumor microenvironment cell subsets.
  - Integrated single-cell specificity scoring into `pipeline/gene_expression/correlator.py` (Cell Type Specificity dimension) and `pipeline/biomarker_discovery/discover.py` (biomarker candidate specificity rankings).

- **In Silico Lead Optimization & Synergy Models**:
  - Quantitative Clark-Pickett BBB permeability, CYP450 5-isozyme metabolism/DDI liability, and hERG cardiotoxicity scoring in `pipeline/admet/engine.py`.
  - Quantitative Loewe Additivity Combination Index ($CI$) and Bliss Independence excess synergy ($\Delta \text{Bliss}$) in `pipeline/drug_synergy/engine.py`.

- **ClinicalTrials.gov API v2 Live Intelligence**:
  - Structured eligibility criteria parsing (inclusion/exclusion lists, age bounds, gender), Phase progression duration and PTRS forecasting, and sponsor portfolio analytics in `pipeline/clinical_trials/tracker.py`.

### Verification

- `pytest tests/test_disease_catalog_tier_promotion.py -v` — 90 passed (100% across all 45 promoted disease modules).
- `pytest tests/pipeline/test_single_cell_deconvolution.py -v` — 4 passed.
- `pytest tests/biomed/test_network_analytics.py -v` — 3 passed.
- `pytest tests/test_advanced_pipeline_enhancements.py -v` — 6 passed.
- `ruff check src tests` — All checks passed (0 errors).

---

## [Full HPO/HPOA import and registry tooling fixes] — 2026-08-13


### Added

- **Full MONDO/HPO/HPOA import into the biomed store** — `scripts/setup_biomed_imports.py --full` replaced the fixture-only ontology snapshots with real data: 57,000 entities (20,413 HP terms with labels) and 168,754 `HAS_PHENOTYPE` claims. This unblocks the Condition Explorer / comparison / graph-analytics features against real ontologies.
- **HPO-path symptom harvest** — `_hpo_symptoms_from_biomed` was rewritten against the real `claims` schema (it previously queried a non-existent `snapshot_id` column and silently returned nothing). Symptom labels now resolve through the cached HPO label map; the harvest filled **142 more scaffolded modules**, bringing populated `SYMPTOMS` configs to 3,824.

### Changed

- `disease list` no longer runs full config validation on all 10,405 modules by default — it lists ids in ~1.5s instead of ~98s. The old rich behavior (names, descriptions, gap report) is preserved behind `disease list --validate`.
- `pip-tools` bumped to `>=7.6.1`; both lock files regenerated with pip-compile 7.6.1 so `make lock` / `make lock-check` work again with pip 26 (7.6.0 crashed on the removed `pip._internal.utils.compat.stdlib_pkgs`).

### Fixed

- `test_restore_legacy_backup_reattaches_pathway_by_keyword` now scaffolds deterministically offline (monkeypatched `_collect_sources`), instead of depending on bulk data for `EFO_0001370` which is absent from the local OT subset. All 61 `test_disease_scaffold.py` tests pass.

### Verification

- `python -m pytest tests/test_disease_scaffold.py -q` — 61 passed
- `python -m pytest tests/test_bulk_store.py tests/test_symptom_harvester.py tests/test_disease_registry_validation.py -q` — 11 passed
- Registry scan: 3,824 populated `SYMPTOMS`, 0 corrupted blocks, 0 obsolete HPO terms.

---

## [Registry-wide symptom curation] — 2026-08-13

### Added

- **3,680 scaffolded disease modules now carry curated `SYMPTOMS`** — HPO-derived clinical phenotype labels harvested from the local Open Targets `disease_phenotype` bulk table and written into `config.py` (via `harvest_all_symptoms`). The 6,709 modules with no phenotype rows in the local subset remain empty and keep their curation TODO. Stale `# TODO: add the clinical symptoms ...` comments are removed once a module is populated.

### Fixed

- `OpenTargetsBulkStore.get_phenotypes()` now returns **human-readable HPO labels** for the real OT parquet schema (`disease`/`phenotype`/`evidence`) instead of raw HP ids (`HP_0003829` → "Neoplasm of the lung"). Labels come from the local HPO artifact (`data/biomed/artifacts/hp.json`), with obsolete terms filtered out and the raw id retained as a fallback.
- `duckdb` (a declared core dependency in `pyproject.toml`) was missing from `requirements.in` and both lock files, silently breaking every OT bulk-store query ("No module named 'duckdb'"). Added `duckdb` and `orjson` to `requirements.in` and regenerated `requirements-lock.txt` / `requirements-dev-lock.txt`.
- Per-call `DESCRIBE` and parquet-glob scans in `OpenTargetsBulkStore` are now cached per table, cutting the symptom harvest from ~0.45s to ~0.15s per disease.

### Verification

- `python -m pytest tests/test_bulk_store.py tests/test_symptom_harvester.py tests/test_disease_registry_validation.py tests/test_adverse_events.py -q` — passed
- `python -m med_research.cli disease validate 12q14_microdeletion_syndrome` — KG files pass
- Registry scan: 3,682 configs with non-empty `SYMPTOMS`, 0 corrupted `SYMPTOMS` blocks, 0 obsolete HPO terms.

---

## [Platform expansion: 10k scaffolds, new modules, streaming, graph analytics] — 2026-08-13

### Added

- **Disease registry expansion to 10,405 modules** — 10,387 auto-generated OpenTargets knowledge-graph scaffolds (genes/drugs/pathways/relationships + generated configs) on top of 18 hand-curated modules. Bulk harvest tooling: `scripts/setup_opentargets_bulk.py`, `scripts/disease_batch_pipeline.py`, `scripts/expand_all_diseases.py`, `scripts/batch_refresh_diseases.py`, and the `disease bulk-harvest` / `disease batch-add` CLI commands.
- **New pipeline modules** — `admet` (ADMET radar safety & toxicity), `crispr`, `multi_omics`, and `structure_3d`, registered in the module registry with typed result contracts, generic CLI commands, web job endpoints, and report templates.
- **Live external connectors** — Open Targets, GTEx, ChEMBL, UniProt, and bioRxiv clients under `pipeline/external/`, exposed through the `live` CLI command and additional Evidence Workspace sources (`opentargets`, `gtex`, `biorxiv`, `chembl`).
- **Graph Analytics and Target Vulnerability UI tab** — claim-path explorer and target-prioritization ranking via `/api/v1/biomed/pathways` and `/api/v1/biomed/target-prioritization/{disease_curie}`, backed by `biomed/graph_analytics.py`.
- **ClinVar and openFDA live API adapters** for `BiomedicalRepository` (`biomed/imports/clinvar_adapter.py`, `openfda_adapter.py`), alongside existing MONDO/HPO/HPOA import adapters.
- **SSE job streaming** — `GET /api/stream/jobs/{job_id}` server-sent events as an alternative to the job WebSocket.
- **Registry-wide schema and relationship consistency validation tests** (`tests/test_disease_registry_validation.py`).
- `GET /api/ready` readiness endpoint and `GET /api/system/modules` pipeline-catalog endpoint.

### Changed

- `disease validate --all --strict` now walks the full 10,405-module registry and reports config gaps (e.g. empty `SYMPTOMS`) on scaffolded modules, exiting non-zero in strict mode. Gate individual curated modules with `disease validate <id> --strict`.
- Web dashboard gained the Biomedical Import Status panel and 10k-module-aware platform stats.

### Verification

- `python -m pytest --collect-only -q` — 22,897 tests collected
- `python -m med_research.cli disease validate sle --strict` — passed
- `python -m med_research.cli modules` — registered module catalog includes admet, crispr, multi_omics, structure_3d

---

## [Universal Biomedical Schema v1] — 2026-08-12

### Added

- `med_research.biomed` canonical SQLite store with versioned entities, claims, evidence, resource snapshots, and research runs.
- Ontology import adapters for MONDO, HPO, and HPOA with idempotent, checksum-verified imports and legacy disease migration for all seven core modules.
- Versioned `/api/v1` condition search, detail, hierarchy, claims, snapshot, and comparison endpoints with research-only disclaimers.
- Dashboard Condition Explorer, Condition Comparison (searchable CURIE pickers), and Biomedical Import Status operator panel.
- Pinned fixture manifest (`data/biomed/pinned-artifacts.json`), `scripts/verify_biomed_imports.py`, and `make biomed-verify`.

### Changed

- `BIOMEDICAL_DB_PATH` now resolves to the repository `data/biomedical.sqlite3` instead of `src/data/`.
- Import bundles skip duplicate snapshot writes when the same resource version and checksum are re-imported.

### Verification

- `python -m pytest tests/biomed tests/web/test_universal_models.py tests/web/test_universal_service.py tests/web/test_universal_api.py tests/web/test_universal_dashboard.py tests/web/test_universal_language.py tests/web/test_universal_comparison_api.py tests/web/test_universal_comparison_dashboard.py -q`
- `python scripts/verify_biomed_imports.py --from-fixtures --check-store`
- `python -m med_research.cli biomed init && python scripts/setup_biomed_imports.py --from-fixtures && python -m med_research.cli biomed migrate legacy`

---

## [Per-disease expression consensus curation] — 2026-08-11

### Added

- Per-disease curated consensus gene lists in `geo.py` for sle, ra, ibd, ms, ss, ssc, and t1d (`CURATED_CONSENSUS_DISEASES`).
- `fetch_expression_data()` explicit `not_implemented` contract — live GEO matrix download is not supported; only cached matrices are used.
- `CONTRIBUTING.md` — contributor guide covering validate/coverage workflow and local development.
- `docs/disease-curation.md` — disease curation playbook for expression consensus and coverage expectations.

### Changed

- Correlator and signature modules load per-disease signatures; uncurated diseases no longer silently inherit SLE consensus genes.
- Report templates and bioinformatics provenance use disease-neutral terminology and coverage wording.
- CLI typing cleanup (`PipelineRunResult`, typed `_dispatch`, safer `_default_pubmed_query`); web lifespan return type.

### Verification

- `python -m pytest tests/test_report_neutral_terminology.py tests/test_gene_expression.py -q`
- `python -m pytest tests/ -m "not slow and not integration" -q`
- `python -m med_research.cli disease validate --all --strict`

---

## [Typed result contracts and pipeline gateway] — 2026-08-10

### Added

- `src/med_research/pipeline/results.py` — TypedDict result contracts for every engine seam, with `validate_result_contract()` (Pydantic `TypeAdapter`) enforced at the dispatch boundary and `result_contract_name()`/`result_contract_schema()` feeding catalog metadata.
- `src/med_research/pipeline/gateway.py` — `PipelineGateway` facade (`execute`, `coverage`, `provenance`, `report`) as the single typed entry point shared by the CLI, web services, and Celery.
- The registry now owns module aliases, request-option schemas, and Celery task routes, so the catalog drives the generic CLI and web job APIs from one source of truth.
- `tests/test_pipeline_contracts.py` — registry-wide contract tests: typed dispatch, adapter call discipline, catalog metadata, Workspace request-schema alignment, and per-route response-model coverage.
- `tests/test_cli_progress.py` — every engine `main()` must thread the shared `cli_progress` callback.

### Changed

- `PipelineRunResult` and `BasePipelineModule` are now generic over result types; all adapters declare `BasePipelineModule[ResultT]` with typed `run()`/`report()` signatures.
- `execute_module()` validates raw results against the module contract before CLI, web, Celery, or report consumers see them; contract violations surface as typed failures instead of silent drift.
- CLI and web services dispatch through `pipeline_gateway`; generic CLI commands generate argument converters from catalog request schemas.
- mypy typecheck scope expanded to 57 files; newly surfaced errors fixed (RDKit compiled-module attributes, `chromadb` fallback assignment).
- Integration HTTP fixtures aligned to real engine output shapes (`gwas_results`/crossref as dicts).

### Verification

- `python -m pytest tests/test_pipeline_contracts.py tests/test_cli_progress.py -q` — 73 passed
- `python -m pytest tests/ -m "not slow and not integration"` — 1803 passed, 1 skipped
- `python -m pytest tests/ -m "integration and not slow"` — 59 passed, 24 skipped
- `make typecheck` — no issues in 57 source files

---

## [Locked dependency environment and docking verification] — 2026-08-08

### Added

- `scripts/lock_verify.py` — pin-by-pin check of the installed environment against `requirements-lock.txt`, plus `--compare-locks` to fail when the runtime and dev lock files disagree on any shared package.
- `make venv-sync` (syncs `.venv` to the lock files via uv) and `make lock-verify`; `make lock-check` now also fails on lock-to-lock divergence.
- CI installs `requirements-lock.txt` / `requirements-dev-lock.txt` instead of the loose `requirements.in` ranges and verifies installed packages match the lock on every push. Test matrix narrowed to Python 3.11–3.12 (the locked numpy requires 3.11+).
- Fast synthetic docking tests for the Meeko 0.7 receptor (`Polymer`) and ligand (`MoleculePreparation`/`PDBQTWriterLegacy`) preparation paths, run in the PR test job; the real-PDB receptor test is marked `network` and stays in the scheduled slow job.

### Changed

- `requirements-dev-lock.txt` is compiled against the runtime lock (`-c requirements-lock.txt`) so the two files cannot silently diverge (fixes the fastapi/starlette version mismatch between them).
- Fixed docking against Meeko 0.7: receptor prep uses the `Polymer` workflow (`write_pdbqt_file` was removed) and `_CleanSelect` now subclasses BioPython's `Select`; ligand prep handles `write_string`'s 3-tuple return.
- Job WebSocket handler closes connections after terminal messages and runs Celery reads off the event loop (orphaned-job hang); trials `top_sponsors` now matches the API's list-of-dicts contract.
- Untracked regenerated module outputs and legacy flat-file caches; docking artifacts (`*_clean.pdb`, `*.pdbqt`) are gitignored.

### Verification

- `python scripts/lock_verify.py` — all 65 locked packages match
- `make lock-check` — runtime/dev dry-runs fresh; locks agree on all shared packages
- `python -m pytest tests/ -m "not slow and not integration"` — 1626 passed
- Slow suite (ML, WebSocket, trials, docking, live APIs) — 64/64 pass on the locked environment

---

## [Provenance, API hardening, disease-neutral polish] — 2026-08-07

### Added

- Provenance footers for cross-disease, drug synergy, network pharmacology, gene expression, ML predictor, and semantic search reports.
- `tests/integration/` with CLI subprocess smoke tests and auto-marked integration suite.
- `tests/test_report_neutral_terminology.py` — RA/IBD reports must not leak unrelated lupus/SLE copy.
- API hardening: request body size limit middleware, UUID `job_id` validation, fail-fast `API_KEY` requirement when `DEBUG=false`.
- Disease-neutral `get_disease_gene_list()` as the primary bioinformatics helper (`get_lupus_gene_list` deprecated).

### Changed

- CLI semantic/evidence/extractor default queries derive from `--disease` via curated PubMed queries.
- Drug synergy and repurposing report templates use disease-neutral wording.
- Optional-dependency tests (RDKit, Meeko, ChromaDB) skip cleanly when packages are absent.

### Verification

- `python -m pytest tests/test_provenance.py tests/test_report_provenance.py tests/test_evidence_workspace_report.py -q`
- `python -m pytest tests/ -m "not slow" -q`
- `make test-unit` / `make test-integration`

---

## [Pipeline report provenance footers] — 2026-08-07

### Added

- Shared `provenance_footer_html()` in `pipeline/reporting.py` for standardized reproducibility footers.
- `tests/test_report_provenance.py` — integration tests for all eight priority pipeline HTML report generators.
- Provenance footer and cross-run fingerprint stability tests in `tests/test_provenance.py`.
- Evidence Workspace report provenance block test in `tests/test_evidence_workspace_report.py`.

### Changed

- Priority pipeline report generators accept optional `provenance` and inject a footer before `</body>`.
- CLI `--export-html` paths build provenance metadata via `build_provenance()` for adverse events, bioinformatics, biomarker discovery, CAR-T, clinical trials, drug repurposing, literature mining, and virtual screening.
- Evidence Workspace report refactored to use the shared footer helper.
- Removed generated artifact `adverse_events/report.html`.

### Verification

- `python -m pytest tests/test_provenance.py tests/test_report_provenance.py tests/test_evidence_workspace_report.py -q`
- `python -m pytest tests/ -m "not slow" -q`

---

## [Tech debt quick wins batch] — 2026-08-07

### Added

- `tests/test_package_data.py` — verifies disease JSON, web static assets, and pipeline data ship via setuptools package-data.
- `tests/test_cli.py` — asserts `--reload` is disabled unless `DEBUG=true`.

### Changed

- `docker-compose.yml` — removed stale named volumes; mount `./data:/app/data`; configurable `PORT` mapping.
- Multi-disease branding in root `index.html`, `web/config.py` API tags, and knowledge-graph explorer page.
- Consolidated `jobs_router` into `routers/__init__.py` with domain-grouping comments.
- `make serve` no longer passes `--reload` by default.
- Marked Technical Debt **#33**, **#35**, **#36**, **#37**, **#38**, and **#39** resolved in `TECHNICAL_DEBT_ISSUES.md`.

### Verification

- `python -m pytest tests/test_package_data.py tests/test_cli.py -q`
- `python -m pytest tests/ -m "not slow" -q`
- `python -m ruff check src/ tests/`
- `docker compose config`

---

## [Quick wins and provenance hardening] — 2026-08-07

### Added

- Shared provenance contract tests in `tests/test_provenance.py` with run ID, retrieval timestamps, and stable fingerprints.
- Parametrized test ensuring all seven diseases ship curated `CAR_T_SCORES` and disease-risk configs.

### Changed

- ML predictor logs missing optional dependencies and raises `ConfigurationError` via `require_ml_dependencies()`.
- `HealthResponse` reads package version from metadata; removed stale `tests_passing` from `PlatformStats`.
- Evidence Workspace dossiers embed `run_id` and per-source retrieval times in provenance metadata.
- FastAPI lifespan warns when `DEBUG=false` and `API_KEY` is unset; `.env.example` documents production auth and `ENTREZ_EMAIL`.
- Playwright browser tests marked `slow` for offline CI; vina setup CLI tests target the v2 module path.

### Verification

- `python -m pytest tests/ -m "not slow" -q` (1037 passed)
- `python -m ruff check src/ tests/`

---

## [Multi-disease coverage completion] — 2026-08-07

### Changed

- Unified `DEFAULT_MODULE_INPUTS` as the single module registry for CLI, `GET /api/system/diseases`, and coverage reports (19 modules including semantic, evidence, and KG).
- Wired `module_coverage` boundaries in semantic search, evidence gatherer/extractor/monitor, knowledge graph builder wrapper, and cross-disease success path.
- Propagated `coverage` + `status` through repurposing, synergy, biomarker, expression, clinical trials, ML predictor, cross-disease, semantic, evidence, and KG web services.
- Extended Pydantic response models with optional `coverage` and `status` fields for all affected analysis endpoints.

### Verification

- `python -m pytest tests/test_multidisease_coverage.py tests/test_web_api.py -q`
- `python -m pytest tests/ -m "not slow" -q`
- `python -m med_research.cli disease coverage ra`
- `python -m med_research.cli disease coverage ibd`

---

## [Structured logging phase 3] — 2026-08-07

### Changed

- Completed migration of all remaining `print()` calls to structured `logging` across pipeline modules, CLI, and disease scaffold tooling.
- FastAPI lifespan now calls `setup_logging()` (DEBUG when `DEBUG=true`, else INFO).
- Tests updated from `capsys` to `caplog` in literature mining, knowledge graph, disease scaffold, and evidence workspace CLI tests.
- Marked Technical Debt **#1** resolved in `TECHNICAL_DEBT_ISSUES.md`.

### Verification

- `rg "print\\(" src/med_research --glob "*.py"` (no user-output prints remaining)
- `python -m pytest tests/ -m "not slow" -q`
- `python -m med_research.cli disease validate --all --strict`

---

## [Coverage, logging, and deployment hygiene] — 2026-08-07

### Added

- `module_coverage` wiring for repurposing, synergy, biomarkers, expression, network pharmacology, ML predictor, clinical trials, cross-disease, and PPI modules.
- `.env.example` documenting web API, Celery, CORS, rate-limit, and workspace environment variables.
- Extended `DEFAULT_MODULE_INPUTS` in `diseases/coverage_report.py` for all wired modules.

### Changed

- Migrated seven pipeline modules from `print()` to structured `logging` (drug repurposing, synergy, biomarkers, expression, network pharmacology, cross-disease, CAR-T).
- `web/main.py` lifespan hooks now use the logging module.
- Removed local `_archive_v1/` legacy directory copy from the working tree.
- Tests updated to assert CLI formatter output via `caplog` instead of `capsys`.

### Verification

- `python -m pytest tests/ -m "not slow" -q` (excluding Playwright browser tests)
- `python -m med_research.cli disease validate --all --strict`

---

## [KG schema validation] — 2026-08-07

### Added

- Pydantic validation for all five KG entity files at the two central load boundaries (`config.load_disease_json`, `Disease.load_json`).
- `AdverseEventsFile` schema for disease-local `adverse_events.json` loaded via `validate_and_load`.
- `disease validate` now checks KG file schema (per-file `ok` / `missing` / `invalid` status); `--strict` fails on any non-`ok` KG file.
- Relationship node-integrity test parametrized across all seven diseases; curated gene entries added for relationship endpoints that referenced assay targets not previously in entity catalogs.
- API test ensuring `GET /api/system/diseases` survives a disease with invalid KG data without crashing.

### Changed

- `DataValidationError` handling in `web/routers/system.py` disease registry build (degrades to empty counts / blocked coverage instead of 500).
- Marked Technical Debt **#2** resolved in `TECHNICAL_DEBT_ISSUES.md`.

### Verification

- `python -m pytest tests/test_kg_schema_validation.py -q`
- `python -m pytest tests/ -m "not slow" -q` (excluding Playwright browser tests when Chromium is not installed)
- `python -m med_research.cli disease validate --all --strict`

---

## [Current capabilities] — last verified 2026-08-13

This section is the maintained snapshot of the live repository. Historical phase entries below are preserved for project history and describe the codebase at the time of each change; their test counts, paths, and implementation wording are not the current runtime specification.

### Platform status

- **Package:** `med-research` 2.0.0, Python 3.11–3.12 support, unified `med-research` / `python -m med_research.cli` entry points.
- **Disease modules:** 10,405 discovered modules — 18 hand-curated (`sle`, `ra`, `ms`, `ss`, `ssc`, `t1d`, `ibd`, `ad`, `als`, `as`, `asthma`, `atopic_dermatitis`, `copd`, `gout`, `pd`, `psa`, `pso`, `t2d`) plus 10,387 auto-generated OpenTargets knowledge-graph scaffolds. `disease validate --all` walks the full registry and reports config gaps on scaffolded modules (e.g. empty `SYMPTOMS`); `disease validate <id> --strict` passes for the curated set.
- **Universal Biomedical Schema v1:** canonical `med_research.biomed` SQLite store with versioned MONDO/HPO/HPOA snapshots, entities, claims, evidence, research runs, legacy-disease migration, HPO-aware condition comparison, graph analytics, and read-only `/api/v1` endpoints with research-only disclaimers.
- **Analysis capabilities:** disease-specific knowledge graphs, repurposing, bioinformatics, literature mining, virtual screening/docking, trials, ML prediction, synergy, safety, ADMET, CRISPR, multi-omics, structure 3D, network pharmacology, expression, CAR-T, biomarkers, semantic search, evidence gathering/extraction, monitoring, cross-disease analysis, and live external connectors (Open Targets, GTEx, ChEMBL, UniProt, bioRxiv).
- **Web application:** FastAPI API and vanilla JavaScript dashboard, with Celery/Redis-backed asynchronous jobs, WebSocket **and SSE** progress, HTTP polling fallback, saved Workspace history, comparison, trends, alerts, weekly digests, JSON/HTML exports, API-key middleware, distributed rate limiting, researcher sessions (local + trusted proxy), and the Condition Explorer / Condition Comparison / Biomedical Import Status / Graph Analytics & Target Vulnerability tabs.
- **Evidence Workspace:** PubMed and ClinicalTrials.gov are the dashboard defaults; GWAS, FDA-label, Open Targets, GTEx, bioRxiv, and ChEMBL adapters are also available. Dossiers include source-level status, native citations, supporting/contradictory claims, explainable drug/target rankings, graph path/no-path explanations, warnings, limitations, and reproducibility fingerprints.
- **Research-safety posture:** Workspace rankings are computational prioritization heuristics only. Outputs require source review and experimental/clinical validation and are not medical advice.

### Maintained documentation

- `README.md` — installation, CLI, disease validation, dashboard, Docker, and testing quick start.
- `docs/evidence-workspace.md` — Workspace tutorial and dossier/API behavior.
- `docs/api-reference.md` — live server routes, job lifecycle, environment variables, exports, universal `/api/v1` endpoints, and deployment caveats.
- `docs/disease-curation.md` — validate/coverage/refresh curation playbook and scaffold workflow.
- `docs/deployment.md` — self-hosted Docker Compose setup and production env guidance.
- `docs/licensing.md` — MIT license and third-party data attribution.
- `TECHNICAL_DEBT_ISSUES.md` — historical audit with current-state qualification.

### Verification snapshot

The following checks were run in the current checkout:

| Check | Result |
|---|---|
| `python -m pytest --collect-only -q` | **22,897 tests collected** |
| `python -m pytest tests/test_evidence_workspace*.py -q --tb=short` | **86 collected** |
| `python -m med_research.cli disease validate sle --strict` | **Passed** |
| `python -m med_research.cli disease validate --all --strict` | Reports scaffold config gaps (expected; exit 1) |
| `python -m med_research.cli --help` | **Passed** |
| Documentation link/content checks and `git diff --check` | **Passed** |

Test counts are a verification snapshot, not a permanent contract. Re-run the commands above after changes and update this section's date/results when the maintained capability status changes.

---

## Historical release notes

## [Evidence Workspace and documentation alignment] — 2026-08-06

### Added

- Evidence-to-Hypothesis Workspace documentation in `docs/evidence-workspace.md`, covering the live CLI request contract, dashboard lifecycle, dossier fields, saved-run history, comparison/trends, exports, failure semantics, and deterministic browser tests.
- API and operations reference in `docs/api-reference.md`, generated from the current FastAPI route surface, CLI server settings, Docker Compose profiles, Celery lifecycle, environment variables, and export endpoints.

### Changed

- Replaced the stale v1-oriented README with current `med-research` 2.0 installation, CLI, seven-disease validation, dashboard, Workspace, testing, and Docker instructions.
- Marked the original Workspace design records as implemented historical documents and aligned their scope with the disease-aware source adapters, provenance fingerprints, browser tests, terminal failure recovery, and exports now in the codebase.
- Clarified the technical-debt audit's historical status so resolved migration, disease-validation, static-mount, and guarded-reload findings are not mistaken for open defects.

### Verification

- `python -m med_research.cli disease validate --all --strict` passed for all seven discovered disease modules.
- The checkout collected 969 tests; the test command exit status remains authoritative over this snapshot.

---

## [Phase 23] Real Molecular Docking — 2026-07-25

### Sprint Goal
Complete the molecular docking pipeline with AutoDock Vina integration, making real binding energy calculations available alongside property-based virtual screening. Harden the existing docking infrastructure and add comprehensive tests.

---

### Added

#### Vina Binary Download Helper (`virtual_screening/vina_setup.py`)
- Cross-platform Vina binary downloader (Win/Mac/Linux)
- `--auto` flag for non-interactive installation
- `--check` flag for installation status
- `--force` flag for re-download
- Downloads from official GitHub releases (v1.2.5)

#### Docking Pipeline Dependencies
- **Meeko** installed (`meeko>=0.5.0` in requirements.txt) — PDBQT molecule preparation
- **gemmi** added to requirements (`gemmi>=0.7.0`) — Meeko dependency
- All 3 dependencies now available: RDKit, Meeko, BioPython
- Vina binary is platform-specific — use `vina_setup.py` or manual install

#### SMILES Coverage
- All 15 dockable small-molecule drugs now have SMILES strings
- Biologics (belimumab, rituximab, etc.) correctly excluded from docking (MW > 5000)
- Full SMILES-to-3D-to-PDBQT ligand pipeline operational

#### Docking Infrastructure (existing, hardened)
- **`docking.py`** (902 lines): receptor prep (RCSB PDB fetch + BioPython cleanup + Meeko PDBQT), ligand prep (SMILES → RDKit 3D → Meeko PDBQT), parallel Vina execution via ProcessPoolExecutor, score normalization (Vina ΔG → 0-10)
- **`targets_config.json`** (290 lines): 10 validated PDB targets with grid boxes, 3 validation targets (JAK1, BTK, TYK2), 12 excluded targets with biological rationale
- **Bug fix**: `_find_vina_binary()` now returns `None` (not `False`) when not found, fixing `get_vina_status_text()` output

#### Tests
- **38 tests** in `tests/test_docking.py`:
  - 3 dependency detection tests
  - 7 score normalization tests (strong/moderate/weak/edge cases)
  - 1 Vina binary detection test
  - 10 DockingEngine config/target tests (10 validated targets, AlphaFold exclusions, field validation)
  - 5 real binding score computation tests (biologic skip, error handling, valid results)
  - 3 Vina setup tool tests (check, system detection)
  - 3 public API function tests
  - 3 target config validation tests (PDB IDs, grid sizes, grid centers)
  - 3 slow tests (receptor prep, CLI help/check)

### Changed

- `.gitignore`: Added `virtual_screening/bin/`, `targets/receptors/`, `targets/ligands/`, `targets/docking_output/`
- `requirements.txt`: Added `gemmi>=0.7.0`

### Docking Status
- **RDKit**: available
- **Meeko**: available (v0.7.1)
- **BioPython**: available
- **AutoDock Vina**: requires manual install or `python virtual_screening/vina_setup.py --auto`
- **docking_possible**: True (when Vina binary is installed)

**Total test count: 363 (35 docking + 328 existing).**

---

## [Phase 22] Cross-Disease Drug Repurposing Analyzer — 2026-07-25

### Sprint Goal
Load all 7 autoimmune disease knowledge graphs and compute cross-disease shared biology, disease similarity, multi-disease drug scoring, and cross-disease repurposing recommendations.

---

### Added

#### Cross-Disease Module (`cross_disease/`)
- **`analyzer.py`** — Core analysis engine:
  - Loads all 7 disease KGs (SLE, RA, MS, SS, SSc, T1D, IBD) via `knowledge_graph.config`
  - Computes shared genes (PTPN22 in 6 diseases, TYK2 in 4, etc.) with per-disease details
  - Computes shared drugs (rituximab in 5 diseases, prednisone in 4, etc.)
  - Computes shared pathways across diseases via Jaccard similarity
  - Disease similarity matrix: pairwise Jaccard similarity on genes (40%), drugs (35%), pathways (25%)
  - 5-dimensional multi-disease drug scoring (97 drugs across all 7 diseases):
    - Disease Coverage (30%), Target Centrality (25%), Pathway Breadth (20%), Mechanistic Transferability (15%), Novelty (10%)
  - Cross-disease repurposing: finds drugs from one disease's KG that target genes in another disease's KG
  - 4-tier classification: Tier 1 (≥7.5) to Tier 4 (<4.5)
- **`report.py`** — Standalone HTML report with:
  - Disease profile overview cards for all 7 diseases with gene/drug/pathway counts
  - Disease similarity matrix (21 pairwise comparisons)
  - Interactive Chart.js radar chart (top 5 multi-disease drugs across 5 dimensions)
  - Ranked multi-disease drug candidates table
  - Shared genes/drugs/pathways tables
  - Cross-disease repurposing opportunity table
  - Methodology section with all scoring weights

#### CLI & Dashboard
- CLI: `python main.py cross-disease --top 20 --export-html`
- Subcommand `cross-disease` already integrated into `main.py`
- Output saved to `cross_disease/data/cross_disease_analysis.json`

#### Tests
- **31 tests** in `tests/test_cross_disease.py`:
  - 3 data loading tests (7 diseases, correct keys, SLE gene count)
  - 7 normalization/Jaccard unit tests
  - 9 shared gene/drug/pathway unit tests
  - 3 disease similarity tests (matrix size=21 pairs, SLE↔RA highest)
  - 3 multi-disease drug scoring tests (97 drugs, sorted, tiering)
  - 3 CLI print function tests (analyze, top drugs, repurposing)
  - 3 slow tests (HTML report, CLI help, CLI run)

### Technical Improvements

- Fixed PPI recursion bug in `bioinformatics/ppi.py` where `load_genes()` called itself instead of the KG config loader

### Results

- **26 shared genes** across 2+ diseases (PTPN22 in 6, TYK2/HLA-DRB1 in 4)
- **24 shared drugs** across 2+ diseases (rituximab in 5, prednisone/mycophenolate in 4)
- **5 shared pathways** (IL-6/JAK-STAT, T cell costim, complement, NF-κB, Type I IFN)
- **SLE ↔ RA** is the most similar disease pair (0.2013 Jaccard)
- **97 multi-disease drugs scored**, top candidate: Rituximab (5.68/10, 5 diseases)
- **3-dimensional similarity scoring**: gene (40%), drug (35%), pathway (25%)

**All 31 cross-disease tests pass. Platform now spans 22 phases. Total test count: 328.**

---

## [Phase 21] Cross-Disease Expansion — 2026-07-25

### Sprint Goal
Curate knowledge graph data for all 5 remaining autoimmune diseases to complete Phase 21 and enable cross-disease analysis across 7 diseases.

---

### Added

#### Multiple Sclerosis (MS) — `knowledge_graph/data/ms/`
- **22 curated risk genes**: HLA-DRB1 (OR 3.1), IL7R, IL2RA, CD40, CD58, TNFRSF1A, IRF8, CYP27B1, STAT3, TYK2, CLEC16A, EVI5, CD6, CD86, CBLB, RGS1, CXCR5, TNFSF14, CD226, MAPK1, TNFRSF13B, IL22RA2
- **20 approved/investigational drugs**: ocrelizumab, ofatumumab, ublituximab, rituximab, natalizumab, fingolimod, siponimod, ozanimod, ponesimod, dimethyl fumarate, diroximel fumarate, teriflunomide, cladribine, alemtuzumab, glatiramer acetate, interferon beta, evobrutinib, tolebrutinib, mitoxantrone, methylprednisolone
- **7 pathways**: B Cell Depletion, S1P Modulation, Integrin/Adhesion Blockade, Th17/IL-17 Axis, NF-κB/NRF2, Type I IFN/JAK-STAT, BTK Signaling
- **Graph**: 50 nodes, 61 edges across 4 edge types

#### Sjögren's Syndrome (SS) — `knowledge_graph/data/ss/`
- **16 curated risk genes**: HLA-DRB1 (OR 2.5), STAT4, IRF5, TNFAIP3, BLK, BANK1, TNIP1, IL12A, BAFF, PTPN22, FCGR2A, ETS1, IKZF1, CXCR5, TNFSF4, CHRM3
- **12 approved/investigational drugs**: hydroxychloroquine, rituximab, belimumab, ianalumab, iscalimab, abatacept, leflunomide, mycophenolate, prednisone, pilocarpine, cevimeline, cyclosporine ophthalmic
- **5 pathways**: Type I IFN Signature, B Cell Hyperactivity/BAFF, Tfh-Germinal Center Axis, TLR7/9 Innate Sensing, JAK-STAT Signaling

#### Systemic Sclerosis (SSc) — `knowledge_graph/data/ssc/`
- **18 curated risk genes**: HLA-DPB1, STAT4, IRF5, TNFAIP3, BANK1, BLK, CD247, TNIP1, DNASE1L3, PTPN22, IRF8, IL12A, TLR2, TNFSF4, IL21, PPARG, FCGR2B, TGFB1
- **18 approved/investigational drugs**: nintedanib, tocilizumab, mycophenolate, cyclophosphamide, rituximab, bosentan, ambrisentan, macitentan, sildenafil, tadalafil, treprostinil, selexipag, prednisone, methotrexate, lenabasum, fresolimumab, riociguat, belimumab
- **6 pathways**: TGF-β/Fibrosis, Endothelin/Vasculopathy, IL-6/JAK-STAT, B Cell Dysregulation, Innate Immune/TLR4

#### Type 1 Diabetes (T1D) — `knowledge_graph/data/t1d/`
- **18 curated risk genes**: HLA-DQA1, HLA-DQB1, PTPN22, INS, CTLA4, IL2RA, IFIH1, PTPN2, CTSH, CLEC16A, IL10, GLIS3, SH2B3, ERBB3, C1QTNF6, UBASH3A, BACH2
- **15 approved/investigational drugs**: insulin (glargine/lispro/aspart/degludec), teplizumab, otelixizumab, golimumab, abatacept, rituximab, alefacept, anti-thymocyte globulin (ATG), low-dose IL-2, verapamil, GAD-alum, ustekinumab
- **6 pathways**: T Cell Autoimmunity/Insulitis, β Cell ER Stress/Apoptosis, IL-2/Treg Dysfunction, Type I Interferon, Costimulation/Immune Checkpoint, Antigen Presentation (HLA Class II)

#### Inflammatory Bowel Disease (IBD) — `knowledge_graph/data/ibd/`
- **22 curated risk genes**: NOD2, ATG16L1, IL23R, IRGM, LRRK2, TNFSF15, IL10, IL10RA, PTPN22, STAT3, JAK2, IL12B, CARD9, NKX2-3, MST1, FUT2, HNF4A, CCR6, SMAD3, SLC22A5, TYK2, ICOSLG
- **24 approved drugs**: infliximab, adalimumab, certolizumab pegol, golimumab, vedolizumab, ustekinumab, risankizumab, mirikizumab, tofacitinib, upadacitinib, ozanimod, etrasimod, natalizumab, azathioprine, 6-mercaptopurine, methotrexate, mesalamine, budesonide, prednisone, cyclosporine, tacrolimus
- **7 pathways**: IL-23/Th17 Axis, JAK-STAT, Leukocyte Trafficking/Integrins, TNF-alpha, Epithelial Barrier/Autophagy, IL-10 Anti-inflammatory, S1P Modulation

#### Documentation
- README: Phase 21 marked ✅ Complete, cross-disease section lists all 7 diseases
- Stats table updated with cross-disease support count
- All 7 diseases auto-discovered by `build_graph.py --list-diseases`

**All 5 disease datasets build successfully as knowledge graphs. Platform now spans 7 autoimmune diseases across 21 phases.**

---

## [Phase 5] Integration & Polish — 2026-07-19

### Sprint Goal
Transform 4 standalone research modules into a **unified, reproducible, well-tested platform** with a single entry point, containerization, and complete documentation.

---

### Added

#### Unified CLI (`main.py`)
- Single entry point orchestrating all 4 modules via `argparse` subcommands
- **`run-all`** — Full pipeline: Knowledge Graph → Drug Repurposing → Bioinformatics → Literature Mining
- **`kg`** — Build & export the knowledge graph with optional analysis
- **`repurpose`** — Score drug repurposing candidates with configurable top-N
- **`bioinformatics`** — Run GWAS, enrichment, and PPI individually or combined
- **`literature`** — Mine PubMed with configurable article count and per-drug targeted queries
- **`test`** — Run the full test suite (quiet mode available)
- Consolidated bioinformatics report: `run-all --export-html` loads all three JSON result sets and generates one combined `bioinformatics_report.html`
- Cross-platform subprocess execution via `sys.executable`
- Graceful error handling with non-zero exit codes for CI integration

#### Root Dependency Files
- **`requirements.txt`** — Merged from 4 module-specific files: `networkx`, `matplotlib`, `gseapy`, `requests`, `biopython`
- **`requirements-dev.txt`** — Dev tooling: `pytest`, `pytest-cov`, `ruff`
- **`ruff.toml`** — Linter config: Python 3.10+, line-length 100, pyflakes + bugbear + simplify rules

#### Dockerization
- **`Dockerfile`** — Multi-stage build (`python:3.11-slim`), pre-builds knowledge graph at image build time, exposes port 8080, `main.py` as entrypoint
- **`docker-compose.yml`** — Two services: `pipeline` (CLI with writable output volumes) and `kg-web` (serves interactive graph on `:8080`)
- **`.dockerignore`** — Excludes `__pycache__`, venv, IDE files, databases

#### Unified Dashboard (`index.html`)
- Dark-themed root dashboard matching all existing report styles
- Hero section with animated gradient, subtitle, and tech badges
- 6 stat cards: 50 KG nodes, 22 genes, 39 candidates, 4 modules, ~150 articles, 137 tests
- 4 completed module cards with colored borders, icons, descriptions, tags, and dual-action buttons (View Report / View Data)
- 3 planned module cards (dimmed) for Virtual Screening, ML Predictor, Clinical Trial Tracker
- Quick Start section with `pip` + `main.py` and Docker commands
- Footer with links to all 4 reports

#### Literature Mining Tests (`tests/test_literature_mining.py`)
- **59 new tests** across all 4 literature_mining sub-modules
- **ner.py** (17 tests): regex gene/drug/disease extraction, deduplication, known-entity filtering, merge logic, install hints
- **crossref.py** (16 tests): synonym generation, entity matching, relevance scoring, cross-referencing integration
- **miner.py** (12 tests): candidate query generation, mocked PubMed search, error handling, print summary
- **report.py** (14 tests): HTML escape, report generation with mocked file I/O, novel entity sections
- Global spaCy mocking via autouse fixture; BioPython per-test mocking with monkeypatch

---

### Changed

#### README.md
- Roadmap updated: Phases 1–4 marked ✅ Complete, Phase 5 marked 🟡 In Progress
- Architecture tree showing all 4 modules, test files, and CI
- Usage commands for every module with correct flags
- Quick Start section with full pipeline walkthrough
- Stats table (50 nodes, 39 candidates, 196 tests)
- Installation instructions updated to use root `requirements.txt`
- Docker usage section added
- Contributing section with areas needing help

#### CI Workflow (`.github/workflows/test.yml`)
- Now installs from root `requirements.txt` + `requirements-dev.txt`
- Adds `python main.py --help` verification step
- Tests all 6 modules automatically (already ran `pytest tests/`)

---

### Summary

| Metric | Before | After |
|--------|--------|-------|
| Entry points | 6 separate scripts | 1 unified CLI + 6 separate scripts |
| `requirements.txt` files | 4 (per module) | 1 root + 1 dev |
| Tests | 137 | 196 (+59 literature mining) |
| Docker support | None | Dockerfile + compose |
| Dashboard | Per-module only | Root `index.html` hub |
| README accuracy | Phases 2-4 marked "Planned" | All phases accurate |
| CI coverage | KG + drug repurposing | All 6 modules |

**All 196 tests pass. No breaking changes to any module API.**

## [Phase 9] Drug Combination Synergy — 2026-07-24

### Sprint Goal
Add a new module that predicts synergistic drug pairs from the 26-drug knowledge graph library using a 5-dimensional weighted scoring model.

---

### Added

#### Drug Synergy Module (`drug_synergy/`)
- **`engine.py`** — Core synergy scoring engine with 5 weighted dimensions:
  - Target Complementarity (30%) — how different are the two drugs' molecular targets?
  - Pathway Diversity (25%) — how diverse are the biological pathways affected?
  - Mechanism Orthogonality (20%) — how independent are the mechanisms of action?
  - Safety Non-overlap (15%) — non-overlapping toxicity profiles
  - Combined Evidence (10%) — existing clinical evidence for the combination
- Scores all 325 unique drug pairs from the 26-drug library
- Ranked output with 4-tier priority classification
- **`report.py`** — Standalone HTML report with highlights grid, ranked table, and methodology

#### Web API Integration
- **`GET /api/synergy/pairs`** — Returns ranked synergistic drug pairs with score breakdowns
- **`POST /api/jobs/synergy`** — Celery async job with WebSocket progress streaming
- Pydantic models in `web_api/models/synergy.py`
- Service layer in `web_api/services/synergy_service.py`
- Dedicated router in `web_api/routers/synergy.py`
- "Synergy" OpenAPI tag in config

#### Dashboard & CLI
- Synergy module card in the web dashboard with live execution
- CLI subcommand: `python main.py synergy --top 20 --export-html`
- Integration into `run-all` pipeline (now 8 steps)
- WebSocket job streaming and HTTP polling fallback support

#### Tests
- **23 tests** in `tests/test_drug_synergy.py`:
  - 13 unit tests covering all 5 scoring dimensions
  - 7 integration tests for batch scoring and full pipeline
  - 2 CLI integration tests
  - Marked with `@pytest.mark.slow` for integration tests

### Upcoming Features (Documented)
- Adverse Event Profiling (FAERS/SIDER integration)
- Network Pharmacology Hub (centrality, community detection)
- Gene Expression Correlation (GEO datasets, Connectivity Map)
- Interactive Radar Charts (Chart.js score visualizations)

**All 23 synergy tests pass alongside the existing 297.**

---

## [Phase 10] Adverse Event Profiling — 2026-07-25

### Sprint Goal
Add lupus-specific adverse event safety profiling across all 26 KG drugs and integrate as a new scoring dimension in the drug repurposing engine.

---

### Added

#### Adverse Events Module (`adverse_events/`)
- **`profiler.py`** — Core profiling engine with curated FDA-label safety data for all 26 drugs
- 4-dimensional weighted scoring:
  - Lupus Symptom Overlap (35%) — do AEs mimic lupus symptoms?
  - Severity Burden (30%) — how severe are common AEs?
  - Chronic Use Safety (25%) — is the drug safe long-term?
  - Drug-Induced Lupus Risk (10%) — risk of triggering DIL
- Black box warning tracking and monitoring requirements
- **`report.py`** — HTML report with safety rankings, highlights, and per-drug profiles

#### Drug Repurposing Engine Update
- Replaced `safety_score` (10%) with `adverse_event_score` (20%)
- Updated weights: Target 20%, Pathway 15%, Mechanistic 20%, Clinical 15%, AE 20%, Novelty 10%
- Drug name matching against KG drug IDs for reliable profile lookup
- Graceful fallback to legacy `safety_score` for non-KG repurposing candidates
- Updated report display for adverse event scores

#### Web API Integration
- **`GET /api/safety/profiles`** — All 26 drug safety profiles with summary stats
- **`GET /api/safety/profiles?drug_id=X`** — Single drug detailed safety profile
- **`POST /api/jobs/safety`** — Celery async job with progress streaming
- Pydantic models in `web_api/models/adverse_events.py`
- Service layer in `web_api/services/adverse_events_service.py`
- "Safety" OpenAPI tag in config

#### Dashboard & CLI
- Safety Profiling module card in the web dashboard (Phase 10)
- CLI: `python main.py safety --drug belimumab --export-html`
- WebSocket streaming support for async profiling

#### Tests
- **26 tests** in `tests/test_adverse_events.py`:
  - 17 unit tests covering all scoring dimensions
  - 9 integration tests (marked `@pytest.mark.slow`)

**All 26 adverse event tests pass. All existing engine tests pass with updated weights.**

---

## [Phase 11] Network Pharmacology Hub — 2026-07-25

### Sprint Goal
Deep network analysis on the full 72-node/115-edge lupus knowledge graph with centrality metrics, community detection, and bridge node identification.

---

### Added

#### Network Pharmacology Module (`network_pharmacology/`)
- **`analyzer.py`** — Comprehensive network analysis engine:
  - **Centrality**: degree, betweenness, eigenvector, closeness, PageRank for all 72 nodes
  - **Community Detection**: Louvain algorithm (with greedy modularity fallback), 9 communities found (modularity 0.524)
  - **Bridge Nodes**: Top 20 nodes by betweenness centrality connecting communities
  - **Graph Metrics**: density (0.045), diameter, avg shortest path, clustering coefficient, assortativity
  - Graceful eigenvector centrality fallback on disconnected graphs (uses largest component)
  - Results saved to `network_analysis.json` for API consumption
- **`report.py`** — HTML report with metrics cards, centrality rankings, community breakdown, and methodology

#### Web API Integration
- **`GET /api/kg/centrality?metric=betweenness&top_n=20`** — Per-node centrality scores
- **`GET /api/kg/communities`** — Community detection results with node membership
- Service functions in `web_api/services/kg_service.py`: `run_centrality_analysis()`, `run_community_detection()`
- Pydantic models in `web_api/models/kg.py`: `CentralityResponse`, `CommunityDetectionResponse`

#### Dashboard & CLI
- Network Pharmacology module card in the web dashboard (Phase 11)
- CLI: `python main.py network --centrality`, `--communities`, `--export-html`

#### Tests
- **16 tests** in `tests/test_network_pharmacology.py`:
  - 11 unit tests: graph metrics, centrality, bridge nodes, communities
  - 5 integration tests (marked `@pytest.mark.slow`)

**All 16 network pharmacology tests pass. 72 nodes, 115 edges, 9 communities, modularity 0.524.**

---

## [Phase 12] Gene Expression Correlation — 2026-07-25

### Sprint Goal
Connectivity Map-inspired module that correlates drug mechanisms against curated SLE gene expression signatures to score each drug's potential to reverse disease-associated transcriptomic dysregulation.

---

### Added

#### Gene Expression Module (`gene_expression/`)
- **`correlator.py`** — Core correlation engine with curated SLE signatures:
  - **SLE Upregulated Genes** (38 genes with fold-changes): IFN signature, cytokines, B/T cell markers
  - **SLE Downregulated Genes** (26 genes with fold-changes): complement, Treg, DNase, clearance
  - **Drug Target Gene Mapping**: 26 drugs → therapeutic target genes
  - **Pathway-Level Reversal**: 11 drugs with known pathway-level expression effects
  - **Cell Type Relevance**: 11 SLE-relevant immune cell types with disease relevance scores
- 5-dimensional weighted scoring:
  - Signature Reversal (35%) — counteracts up/down-regulated disease genes?
  - Target-Disease Overlap (25%) — drug targets in dysregulated lupus pathways?
  - Cell Type Specificity (20%) — active in B cells, pDCs, Tfh?
  - Expression Evidence (15%) — well-studied in SLE transcriptomics?
  - Directionality (5%) — drug's effect directionally correct?
- **`report.py`** — HTML report with highlights grid, ranked table, and methodology

#### Web API Integration
- **`GET /api/expression/correlate?top_n=10`** — Ranked drug expression correlation scores
- Pydantic models in `web_api/models/expression.py`
- Service layer in `web_api/services/expression_service.py`
- Dedicated router in `web_api/routers/expression.py`
- "Expression" OpenAPI tag in config

#### Dashboard & CLI
- Gene Expression module card in the web dashboard (Phase 12)
- CLI: `python main.py expression --top 15 --export-html`
- Direct API mode (no Celery job) for fast synchronous results

#### Tests
- **17 tests** in `tests/test_gene_expression.py`:
  - 4 data integrity tests (SLE signatures, target mappings, cell types)
  - 7 unit tests covering all 5 scoring dimensions
  - 3 integration tests for full analysis and JSON persistence
  - 3 slow tests (report generation, API service, CLI help)

**Top result: Anifrolumab (9.16) — strongest IFN signature reversal. Litifilimab (8.81), Baricitinib (7.90).**

---

## [Phase 13] Interactive Radar Charts — 2026-07-25

### Sprint Goal
Add interactive Chart.js radar (spider) charts to the three core scoring reports for visual score dimension comparison.

---

### Added

#### Drug Repurposing Report (`drug_repurposing/report.py`)
- Radar chart of top 5 candidates across 6 dimensions (Target Similarity, Pathway Proximity, Mechanistic Rationale, Clinical Evidence, Adverse Event Profile, Novelty)
- Chart.js v4.4.7 CDN integration
- Dark-themed chart styling matching platform design
- Novelty score scaled 0-5 to 0-10 for visual consistency

#### Virtual Screening Report (`virtual_screening/report.py`)
- **Overall radar chart**: Top 5 hits across 5 dimensions (Binding, Drug-Like, Target, Similarity, Novelty)
- **Per-target radar charts**: Individual radar charts for each screened gene target
- JSON data generated via `json.dumps()` for proper escaping

#### Drug Synergy Report (`drug_synergy/report.py`)
- Radar chart of top 5 synergistic pairs across 5 dimensions (Target Complementarity, Pathway Diversity, Mechanism Orthogonality, Safety Non-overlap, Combined Evidence)
- Pair names truncated for legend readability

**All 3 reports regenerated with interactive charts. No external dependencies beyond Chart.js CDN.**

---

## [Phase 14] CAR-T Response Predictor — 2026-07-25

### Sprint Goal
Gene-level CD19 CAR-T cell therapy suitability scoring across all 35 lupus-associated genes, identifying which pathways are most B-cell-dependent and likely to respond to CAR-T immune reset.

---

### Added

#### CAR-T Predictor Module (`car_t_predictor/`)
- **`predictor.py`** — Core scoring engine with curated gene-level profiling:
  - B Cell Dependency (35%) — centrality to B cell biology (CD20, BLK, BTK, BANK1, PRDM1)
  - Autoantibody Association (25%) — link to pathogenic anti-dsDNA/ANA
  - Plasma Cell Relevance (20%) — critical for long-lived plasma cell survival
  - CD19 Targeting (15%) — direct impact of CD19 CAR-T on pathway
  - Clinical Evidence (5%) — published CAR-T/deep B cell depletion data
- **`report.py`** — HTML report with radar chart, highlights grid, ranked table, methodology
- Curated scoring dictionaries for all 35 genes with biological rationale

#### Results
- **Top Gene**: PRDM1 (BLIMP-1) — **9.28/10** — plasma cell master transcription factor
- **#2**: BAFF/TNFSF13B — **9.07/10** — B cell survival factor (belimumab target)
- **Bottom**: C4A — **1.65/10** — complement deficiency, not B-cell-driven
- 3 Tier 1 genes (≥8.0), 6 Tier 2 (7.0-8.0), 7 Tier 3 (5.0-7.0)

#### Web API Integration
- **`GET /api/cart/suitability?top_n=10`** — Ranked gene-level CAR-T suitability scores
- "CAR-T" OpenAPI tag in config

#### Dashboard & CLI
- CAR-T Predictor card in the web dashboard (Phase 14)
- CLI: `python main.py cart --top 15 --export-html`

#### Tests
- **11 non-slow + 3 slow tests** in `tests/test_car_t_predictor.py`

**All CAR-T predictor tests pass. Platform now spans 14 phases.**

---

## [Phase 15] Biomarker Discovery — 2026-07-25

### Sprint Goal
Cross-module integration engine that correlates gene expression signatures with predicted treatment responses across all 5 scoring platforms to identify the most predictive biomarkers for lupus therapy selection.

---

### Added

#### Biomarker Discovery Module (`biomarker_discovery/`)
- **`discover.py`** — Cross-module integration engine:
  - Loads results from all 5 scoring platforms (Gene Expression, CAR-T, Drug Repurposing, Safety, Synergy)
  - Maps each of 35 lupus genes to scores from all available modules
  - 5-dimensional weighted scoring:
    - Cross-Module Consistency (30%) — consistent signal across platforms?
    - Expression Predictiveness (25%) — does expression predict drug response?
    - CAR-T Alignment (20%) — B cell dependency for immune reset?
    - Druggability (15%) — existing or repurposable drugs targeting this gene?
    - Biomarker Novelty (10%) — how novel is this biomarker?
  - Results saved to `biomarker_matrix.json` for API consumption
- **`report.py`** — HTML report with radar chart, highlights grid, ranked table, methodology

#### Results
- **Top Gene**: BTK — **8.29/10** — strongest cross-module signal
- **#2**: BLK — **8.24/10** — consistent across expression + CAR-T + repurposing
- **Bottom**: C4A — **3.13/10** — complement deficiency, weak cross-module signal
- 35 genes scored across 5 platforms

#### Web API Integration
- **`GET /api/biomarker/discover?top_n=10`** — Ranked biomarker discovery results
- "Biomarker" OpenAPI tag in config

#### Dashboard & CLI
- Biomarker Discovery card in the web dashboard (Phase 15)
- CLI: `python main.py biomarker --top 15 --export-html`

#### Tests
- **7 non-slow + 3 slow tests** in `tests/test_biomarker_discovery.py`

**All biomarker discovery tests pass. Platform now spans 15 phases.**

---

## [Phase 16] Semantic Literature Search — 2026-07-25

### Sprint Goal
Add embedding-based semantic search over cached PubMed abstracts using sentence-transformers + ChromaDB, enabling "find papers by meaning, not keywords" — inspired by Exa AI's neural search approach.

---

### Added

#### Semantic Search Module (`semantic_search/`)
- **`engine.py`** — Core search engine:
  - `SemanticSearchEngine` class wrapping sentence-transformers + ChromaDB
  - `index_articles()` — embeds and indexes cached PubMed abstracts into vector DB
  - `search()` — cosine similarity search returning ranked results with 0-10 scores
  - Graceful fallback if dependencies (chromadb, sentence-transformers) are missing
  - Module-level memoization for the gene-drug target map
- **`report.py`** — HTML report with search query display, stats grid, results table, methodology

#### Demo Results
- **106 PubMed articles indexed** into ChromaDB vector store
- Query "B cell depletion therapy lupus" correctly ranks B-cell depletion papers first:
  - #1: "Opportunities and limitations of B cell depletion approaches in SLE" (5.5)
  - #2: "B-cell depletion with obinutuzumab for lupus nephritis" (4.5)
  - #3: "B-cell depletion in autoimmune diseases" (4.2)

#### Web API Integration
- **`GET /api/semantic/search?q=...&top_k=20`** — Natural language semantic search
- "Semantic Search" OpenAPI tag in config

#### Dashboard & CLI
- Semantic Search module card in the web dashboard (Phase 16)
- CLI: `python main.py semantic --index --query "B cell depletion lupus" --top 10 --export-html`

#### Tests
- **6 non-slow + 4 slow tests** in `tests/test_semantic_search.py`
  - Dependency checks, engine initialization, article loading, indexing + search, report, API, CLI

**All 6 non-slow tests pass. Platform now spans 16 phases.**

---

## Remaining ideas (not scheduled)

- Real GEO expression matrix download and ingestion (beyond curated signatures)
- Deeper AutoDock Vina integration for virtual screening beyond property-based heuristics
