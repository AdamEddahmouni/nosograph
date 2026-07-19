.PHONY: help test test-quiet test-cov lint lint-fix run-all run-all-html kg repurpose bio literature docker-build docker-run docker-up docker-test clean

# ── Lupus Research Platform Makefile ──────────────────────────────────────

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Testing ──────────────────────────────────────────────────────────────

test:  ## Run all tests (verbose)
	python -m pytest tests/ -v --tb=short

test-quiet:  ## Run all tests (quiet)
	python -m pytest tests/ -q --tb=line

test-cov:  ## Run tests with coverage report
	python -m pytest tests/ --cov=. --cov-report=term-missing --cov-report=html

# ── Linting ──────────────────────────────────────────────────────────────

lint:  ## Run ruff linter
	python -m ruff check .

lint-fix:  ## Auto-fix ruff lint issues
	python -m ruff check . --fix

# ── Pipeline ─────────────────────────────────────────────────────────────

run-all:  ## Run the full pipeline
	python main.py run-all

run-all-html:  ## Run full pipeline + generate all HTML reports
	python main.py run-all --export-html

kg:  ## Build and analyze the knowledge graph
	python main.py kg --analyze

repurpose:  ## Score drug repurposing candidates (top 15)
	python main.py repurpose --top 15

bio:  ## Run all bioinformatics analyses
	python main.py bioinformatics --export-html

literature:  ## Mine PubMed for SLE articles
	python main.py literature --export-html

# ── Docker ───────────────────────────────────────────────────────────────

docker-build:  ## Build the Docker image
	docker compose build

docker-run:  ## Run full pipeline in Docker
	docker compose run --rm pipeline run-all --export-html

docker-up:  ## Start the knowledge graph web server
	docker compose up kg-web

docker-test:  ## Run tests inside Docker
	docker compose run --rm pipeline test

# ── Cleanup ──────────────────────────────────────────────────────────────

clean:  ## Remove caches, build artifacts, and generated reports
	@echo "Cleaning cache files..."
	@rm -rf bioinformatics/data/*_cache.json
	@rm -rf literature_mining/data/*_cache.json
	@echo "Cleaning generated reports..."
	@rm -f drug_repurposing/report.html
	@rm -f bioinformatics/bioinformatics_report.html
	@rm -f bioinformatics/data/ppi_interactive.html
	@rm -f literature_mining/literature_report.html
	@echo "Cleaning Python artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaning coverage..."
	@rm -rf htmlcov .coverage
	@echo "Done."
