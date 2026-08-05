.PHONY: help test test-quiet test-cov lint lint-fix check-imports run-all kg repurpose bio literature docker-build docker-up docker-test clean install

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

test-cov:  ## Run tests with coverage
	python -m pytest tests/ --cov=src/med_research --cov-report=term-missing

# ── Linting ──────────────────────────────────────────────────────────────

lint:  ## Run ruff linter
	python -m ruff check src/ tests/

lint-fix:  ## Auto-fix ruff lint issues
	python -m ruff check src/ tests/ --fix

check-imports:  ## Audit for stale/dead internal med_research imports
	python scripts/check_imports.py

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
	python -m med_research.cli serve --reload

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
