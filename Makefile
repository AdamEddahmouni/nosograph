.PHONY: help test test-quiet test-fast test-offline test-unit test-integration test-integration-all test-slow test-cov lint lint-fix check-imports typecheck lock lock-check lock-verify venv-sync run-all kg repurpose bio literature docker-build docker-up docker-test clean install biomed-init biomed-verify

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Setup ─────────────────────────────────────────────────────────────────

install:  ## Install the package in development mode
	pip install -e ".[all]"

# ── Testing ──────────────────────────────────────────────────────────────

test:  ## Run all tests (verbose)
	python -m pytest tests/ -v --tb=short

test-quiet:  ## Run all tests (quiet)
	python -m pytest tests/ -q --tb=line

test-fast:  ## Run fast unit tests without slow or integration markers
	python -m pytest tests/ -m "not slow and not integration" -q --tb=line

test-offline:  ## Run the complete offline suite; live API tests are marked slow
	python -m pytest tests/ -m "unit and not network" -q --tb=short

test-slow:  ## Run live API/integration tests marked slow
	python -m pytest tests/ -m slow -v --tb=short

test-unit:  ## Run unit tests only (fast, offline)
	python -m pytest tests/ -m "unit" -q --tb=line

test-integration:  ## Run offline integration tests (fixture-backed, no live APIs)
	python -m pytest tests/ -m "integration and not slow" -q --tb=short

test-integration-all:  ## Run integration and slow tests (may hit external APIs)
	python -m pytest tests/ -m "integration or slow" -v --tb=short

test-cov:  ## Run tests with coverage
	python -m pytest tests/ --cov=src/med_research --cov-report=term-missing

# ── Linting ──────────────────────────────────────────────────────────────

lint:  ## Run ruff linter
	python -m ruff check src tests

lint-fix:  ## Auto-fix ruff lint issues
	python -m ruff check src tests --fix

check-imports:  ## Audit for stale/dead internal med_research imports
	python scripts/check_imports.py

typecheck:  ## Run mypy on the expanded type-check scope
	python -m mypy \
	src/med_research/pipeline/dispatch.py \
	src/med_research/pipeline/gateway.py \
	src/med_research/pipeline/provenance.py \
	src/med_research/pipeline/progress.py \
	src/med_research/pipeline/registry.py \
	src/med_research/pipeline/base.py \
	src/med_research/pipeline/scheduler.py \
	src/med_research/pipeline/results.py \
	src/med_research/pipeline/adapter_options.py \
	src/med_research/exceptions.py \
	src/med_research/pipeline_errors.py \
	src/med_research/cache.py \
	src/med_research/rate_limiter.py \
	src/med_research/diseases/base.py \
	src/med_research/diseases/coverage.py \
	src/med_research/diseases/schemas.py \
	src/med_research/pipeline/adverse_events/adapter.py \
	src/med_research/pipeline/adverse_events/profiler.py \
	src/med_research/pipeline/bioinformatics/adapter.py \
	src/med_research/pipeline/bioinformatics/enrichment.py \
	src/med_research/pipeline/bioinformatics/gwas.py \
	src/med_research/pipeline/bioinformatics/ppi.py \
	src/med_research/pipeline/biomarker_discovery/adapter.py \
	src/med_research/pipeline/biomarker_discovery/discover.py \
	src/med_research/pipeline/car_t_predictor/adapter.py \
	src/med_research/pipeline/car_t_predictor/predictor.py \
	src/med_research/pipeline/clinical_trials/adapter.py \
	src/med_research/pipeline/clinical_trials/tracker.py \
	src/med_research/pipeline/cross_disease/adapter.py \
	src/med_research/pipeline/drug_repurposing/adapter.py \
	src/med_research/pipeline/drug_repurposing/engine.py \
	src/med_research/pipeline/drug_synergy/adapter.py \
	src/med_research/pipeline/drug_synergy/engine.py \
	src/med_research/pipeline/evidence/adapter.py \
	src/med_research/pipeline/evidence/extractor.py \
	src/med_research/pipeline/evidence/gatherer.py \
	src/med_research/pipeline/evidence_workspace/adapter.py \
	src/med_research/pipeline/evidence_workspace/extraction.py \
	src/med_research/pipeline/evidence_workspace/graph.py \
	src/med_research/pipeline/evidence_workspace/ranking.py \
	src/med_research/pipeline/evidence_workspace/report.py \
	src/med_research/pipeline/evidence_workspace/schemas.py \
	src/med_research/pipeline/evidence_workspace/sources.py \
	src/med_research/pipeline/evidence_workspace/workspace.py \
	src/med_research/pipeline/gene_expression/adapter.py \
	src/med_research/pipeline/gene_expression/correlator.py \
	src/med_research/pipeline/knowledge_graph/adapter.py \
	src/med_research/pipeline/knowledge_graph/builder.py \
	src/med_research/pipeline/literature_mining/adapter.py \
	src/med_research/pipeline/literature_mining/crossref.py \
	src/med_research/pipeline/literature_mining/miner.py \
	src/med_research/pipeline/ml_predictor/adapter.py \
	src/med_research/pipeline/ml_predictor/predictor.py \
	src/med_research/pipeline/network_pharmacology/adapter.py \
	src/med_research/pipeline/network_pharmacology/analyzer.py \
	src/med_research/pipeline/semantic_search/adapter.py \
	src/med_research/pipeline/semantic_search/engine.py \
	src/med_research/pipeline/virtual_screening/adapter.py \
	src/med_research/pipeline/virtual_screening/docking.py \
	src/med_research/pipeline/virtual_screening/screening.py \
	src/med_research/pipeline/virtual_screening/screening_strategy.py \
	src/med_research/pipeline/virtual_screening/vina_setup.py \
	src/med_research/cli.py \
	src/med_research/web/dependencies.py \
	src/med_research/web/main.py \
	src/med_research/web/error_handlers.py \
	src/med_research/web/middleware.py \
	src/med_research/web/rate_limit.py \
	src/med_research/web/models/adverse_events.py \
	src/med_research/web/models/bioinformatics.py \
	src/med_research/web/models/biomarker.py \
	src/med_research/web/models/car_t.py \
	src/med_research/web/models/cross_disease.py \
	src/med_research/web/models/disease_admin.py \
	src/med_research/web/models/evidence.py \
	src/med_research/web/models/expression.py \
	src/med_research/web/models/extractor.py \
	src/med_research/web/models/jobs.py \
	src/med_research/web/models/kg.py \
	src/med_research/web/models/monitor.py \
	src/med_research/web/models/repurpose.py \
	src/med_research/web/models/semantic.py \
	src/med_research/web/models/shared.py \
	src/med_research/web/models/synergy.py \
	src/med_research/web/models/workspace.py \
	src/med_research/web/routers/adverse_events.py \
	src/med_research/web/routers/analysis.py \
	src/med_research/web/routers/auth.py \
	src/med_research/web/routers/biomarker.py \
	src/med_research/web/routers/bioinformatics.py \
	src/med_research/web/routers/car_t.py \
	src/med_research/web/routers/cross_disease.py \
	src/med_research/web/routers/disease_admin.py \
	src/med_research/web/routers/evidence.py \
	src/med_research/web/routers/expression.py \
	src/med_research/web/routers/export.py \
	src/med_research/web/routers/extractor.py \
	src/med_research/web/routers/jobs.py \
	src/med_research/web/routers/kg.py \
	src/med_research/web/routers/monitor.py \
	src/med_research/web/routers/repurpose.py \
	src/med_research/web/routers/semantic.py \
	src/med_research/web/routers/synergy.py \
	src/med_research/web/routers/system.py \
	src/med_research/web/routers/workspace.py \
	src/med_research/web/services/adverse_events_service.py \
	src/med_research/web/services/auth.py \
	src/med_research/web/services/bioinformatics_service.py \
	src/med_research/web/services/biomarker_service.py \
	src/med_research/web/services/car_t_service.py \
	src/med_research/web/services/cross_disease_service.py \
	src/med_research/web/services/disease_admin_service.py \
	src/med_research/web/services/evidence_service.py \
	src/med_research/web/services/expression_service.py \
	src/med_research/web/services/extractor_service.py \
	src/med_research/web/services/kg_service.py \
	src/med_research/web/services/monitor_service.py \
	src/med_research/web/services/notifications.py \
	src/med_research/web/services/registry_service.py \
	src/med_research/web/services/repurpose_service.py \
	src/med_research/web/services/review_export.py \
	src/med_research/web/services/review_links.py \
	src/med_research/web/services/semantic_service.py \
	src/med_research/web/services/shared_services.py \
	src/med_research/web/services/synergy_service.py \
	src/med_research/web/services/workspace_graph.py \
	src/med_research/web/services/workspace_store.py \
	src/med_research/web/tasks/analysis_tasks.py \
	src/med_research/biomed/__init__.py \
	src/med_research/biomed/database.py \
	src/med_research/biomed/errors.py \
	src/med_research/biomed/graph.py \
	src/med_research/biomed/identifiers.py \
	src/med_research/biomed/models.py \
	src/med_research/biomed/repository.py \
	src/med_research/biomed/schema.py \
	src/med_research/biomed/comparison/__init__.py \
	src/med_research/biomed/comparison/algorithm.py \
	src/med_research/biomed/comparison/fingerprint.py \
	src/med_research/biomed/comparison/hpo.py \
	src/med_research/biomed/comparison/models.py \
	src/med_research/biomed/comparison/service.py \
	src/med_research/biomed/imports/__init__.py \
	src/med_research/biomed/imports/contracts.py \
	src/med_research/biomed/imports/hpo.py \
	src/med_research/biomed/imports/hpoa.py \
	src/med_research/biomed/imports/models.py \
	src/med_research/biomed/imports/mondo.py \
	src/med_research/biomed/imports/service.py \
	src/med_research/biomed/legacy/__init__.py \
	src/med_research/biomed/legacy/adapter.py \
	src/med_research/biomed/legacy/checksums.py \
	src/med_research/biomed/legacy/compat.py \
	src/med_research/biomed/legacy/manifest.py \
	src/med_research/biomed/legacy/projector.py \
	src/med_research/biomed/legacy/report.py \
	src/med_research/web/dependencies_biomed.py \
	src/med_research/web/models/universal.py \
	src/med_research/web/routers/universal.py \
	src/med_research/web/services/universal_service.py \
	src/med_research/web/services/comparison_service.py

# ── Locked dependencies ────────────────────────────────────────────────────
# The dev lock is compiled against the runtime lock (-c requirements-lock.txt)
# so the two files can never disagree. lock-check enforces freshness and
# mutual consistency; lock-verify compares the installed venv against the
# runtime lock; venv-sync brings a local .venv back onto the lock via uv.

lock:  ## Regenerate requirements-lock.txt and requirements-dev-lock.txt
	python -m piptools compile --output-file=requirements-lock.txt requirements.in
	python -m piptools compile --output-file=requirements-dev-lock.txt requirements-dev.in -c requirements-lock.txt

lock-check:  ## Verify lock files are fresh and mutually consistent
	python -m piptools compile --quiet --dry-run --output-file=requirements-lock.txt requirements.in
	python -m piptools compile --quiet --dry-run --output-file=requirements-dev-lock.txt requirements-dev.in -c requirements-lock.txt
	python scripts/lock_verify.py --compare-locks requirements-dev-lock.txt

# Path to the venv interpreter (Windows uses Scripts/, Unix uses bin/)
VENV_PY := $(shell test -f .venv/Scripts/python.exe && echo .venv/Scripts/python.exe || echo .venv/bin/python)

lock-verify:  ## Verify .venv packages match requirements-lock.txt
	$(VENV_PY) scripts/lock_verify.py

venv-sync:  ## Sync .venv to the locked requirements (install uv: pip install uv)
	@test -f $(VENV_PY) || { echo "No venv found at $(VENV_PY) - create one first (e.g. uv venv)"; exit 1; }
	@command -v uv >/dev/null 2>&1 || { echo "uv is required for venv-sync (install with: pip install uv)"; exit 1; }
	uv pip install --python $(VENV_PY) -r requirements-lock.txt -r requirements-dev-lock.txt
	uv pip install --python $(VENV_PY) -e .
	@echo "Venv synced. Run 'make lock-verify' to confirm it matches the lock."

# ── Pipeline ─────────────────────────────────────────────────────────────

run-all:  ## Run the full pipeline for SLE
	python -m med_research.cli run-all --disease sle

run-all-html:  ## Run full pipeline + generate HTML reports
	python -m med_research.cli run-all --disease sle --export-html

kg:  ## Build the knowledge graph for SLE
	python -m med_research.cli kg --disease sle --analyze

repurpose:  ## Score drug repurposing candidates
	python -m med_research.cli repurpose --disease sle --top 15

bio:  ## Run all bioinformatics analyses
	python -m med_research.cli bioinformatics --disease sle --export-html

literature:  ## Mine disease-related articles
	python -m med_research.cli literature --disease sle --export-html

diseases:  ## List all available diseases
	python -m med_research.cli diseases

modules:  ## List all available pipeline modules
	python -m med_research.cli modules

serve:  ## Start the web API server
	python -m med_research.cli serve

# ── Docker ───────────────────────────────────────────────────────────────

docker-build:  ## Build the Docker image
	docker compose build

docker-up:  ## Start the web API server in Docker
	docker compose up

docker-test:  ## Run tests inside Docker
	docker compose run --rm pipeline test

# ── Biomedical store ─────────────────────────────────────────────────────

biomed-init:  ## Initialize the local canonical biomedical SQLite store
	python -m med_research.cli biomed init

biomed-import-fixtures:  ## Import pinned ontology fixtures into the local biomedical store
	python -m med_research.cli biomed import mondo --artifact tests/fixtures/biomed/mondo/minimal.json
	python -m med_research.cli biomed import hp --artifact tests/fixtures/biomed/hpo/minimal.json
	python -m med_research.cli biomed import hpoa --artifact tests/fixtures/biomed/hpoa/minimal.tsv

biomed-import:  ## Download and import full MONDO, HPO, and HPOA into the biomed store
	python scripts/setup_biomed_imports.py

biomed-migrate-legacy:  ## Project all seven legacy disease modules into the canonical store
	python -m med_research.cli biomed migrate legacy

biomed-verify:  ## Verify pinned fixture checksums and active ontology snapshots
	python scripts/verify_biomed_imports.py --from-fixtures --check-store

biomed-import-clinvar:  ## Import ClinVar fixture into the biomed store
	python -m med_research.cli biomed import clinvar --artifact tests/fixtures/biomed/clinvar/minimal.json

biomed-import-openfda:  ## Import openFDA fixture into the biomed store
	python -m med_research.cli biomed import openfda --artifact tests/fixtures/biomed/openfda/minimal.json

corpus-baseline:  ## Generate corpus baseline metrics report
	python scripts/generate_corpus_baseline.py

corpus-status:  ## Refresh corpus tier status report
	python -m med_research.cli disease corpus-status

# ── Cleanup ──────────────────────────────────────────────────────────────

clean:  ## Remove caches, build artifacts, and generated reports
	@echo "Cleaning cache files..."
	@rm -rf src/med_research/pipeline/*/data/*_cache.json 2>/dev/null || true
	@echo "Cleaning generated reports..."
	@find src/med_research/pipeline -name "report*.html" -delete 2>/dev/null || true
	@echo "Cleaning Python artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "Done."
