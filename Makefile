.PHONY: help test test-quiet test-fast test-offline test-unit test-integration test-integration-all test-slow test-cov lint lint-fix check-imports typecheck lock lock-check lock-verify venv-sync run-all kg repurpose bio literature docker-build docker-up docker-test clean install

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
	python -m pytest tests/ -m "not slow and not integration" -q --tb=short

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
	src/med_research/pipeline/registry.py \
	src/med_research/pipeline/base.py \
	src/med_research/pipeline/scheduler.py \
	src/med_research/pipeline/results.py \
	src/med_research/pipeline/adapter_options.py \
	src/med_research/exceptions.py \
	src/med_research/pipeline_errors.py \
	src/med_research/cache.py \
	src/med_research/rate_limiter.py \
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
	src/med_research/web/error_handlers.py \
	src/med_research/web/middleware.py \
	src/med_research/web/rate_limit.py \
		src/med_research/web/models/jobs.py \
		src/med_research/web/routers/jobs.py \
		src/med_research/web/services/registry_service.py

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
