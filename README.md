# Medical Research Platform

[![Tests](https://github.com/AdamEddahmouni/med-research/actions/workflows/test.yml/badge.svg)](https://github.com/AdamEddahmouni/med-research/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`med-research` is a multi-disease computational research platform for biomedical evidence exploration, drug discovery, and hypothesis generation. It combines disease-specific knowledge graphs, explainable scoring pipelines, literature and clinical-trial evidence, provenance metadata, and a FastAPI dashboard.

> **Research use only.** Outputs are computational prioritization hypotheses, not medical advice, treatment recommendations, or evidence of efficacy. Validate every finding against the cited source and appropriate experimental or clinical evidence.

## What is implemented

- **544 disease modules** in the registry (seven fully curated autoimmune modules — SLE, RA, MS, Sjögren's syndrome, systemic sclerosis, type 1 diabetes, and IBD — plus scaffolded modules across additional conditions).
- Disease-specific JSON knowledge-graph data and pipeline configuration under `src/med_research/diseases/`.
- Knowledge-graph construction and export, drug repurposing, bioinformatics, literature mining, virtual screening, clinical-trial tracking, ML target prediction, synergy, safety, network pharmacology, expression, CAR-T, biomarker, semantic search, evidence gathering, extraction, and monitoring.
- Evidence-to-Hypothesis Workspace with PubMed and ClinicalTrials.gov adapters, deterministic claims, optional LLM enrichment, explainable drug/target rankings, graph explanations, provenance fingerprints, saved history, comparison, trends, and JSON/HTML exports.
- FastAPI web API and vanilla JavaScript dashboard with asynchronous Celery jobs, WebSocket progress, HTTP polling fallback, source-level status, keyboard support, reduced-motion styles, and terminal failure recovery.

## Repository layout

```text
.
├── src/med_research/
│   ├── cli.py                         # Unified `med-research` CLI
│   ├── diseases/{id}/                 # Profiles, configs, and KG JSON data
│   ├── pipeline/                      # Analysis modules
│   │   └── evidence_workspace/        # Dossier schemas, adapters, ranking, reports
│   ├── web/                            # FastAPI app, routers, services, tasks
│   │   └── static/                     # Live dashboard
│   └── templates/                      # Server-rendered report templates
├── tests/                              # Unit, API, fixture, and Playwright tests
├── docs/                               # Current usage and API documentation
├── scripts/check_imports.py            # Stale internal-import audit
├── main.py                             # Compatibility wrapper for the unified CLI
├── pyproject.toml                      # Package metadata and dependencies
├── Makefile                            # Common development commands
└── docker-compose.yml / Dockerfile     # Containerized API, worker, Redis, and CLI
```

## Requirements and installation

- Python 3.11 or 3.12 (the locked numpy version requires 3.11+).
- A virtual environment is recommended.
- Redis and a Celery worker are required for asynchronous dashboard jobs. Pure Python tests and most CLI commands do not require Redis.
- Optional extras provide ML, cheminformatics, NLP, semantic-search, and development tooling.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

python -m pip install --upgrade pip
python -m pip install -e ".[all]"
```

The equivalent requirements-file setup — and the only one CI uses — installs the compiled lock files, not the loose `requirements.in` ranges:

```bash
python -m pip install -r requirements-lock.txt -r requirements-dev-lock.txt
python -m pip install -e .
```

Keep a local venv pinned exactly to the locked environment:

```bash
make venv-sync    # syncs .venv to the lock files via uv
make lock-verify  # fails if any installed package differs from requirements-lock.txt
make lock-check   # fails if the lock files are stale or disagree with each other
```

## Unified CLI

Use the installed command or the module form:

```bash
med-research --help
python -m med_research.cli --help
```

The root `main.py` remains a compatibility wrapper, so `python main.py ...` also delegates to the same CLI. New documentation uses `python -m med_research.cli`.

### Discover diseases and modules

```bash
python -m med_research.cli diseases
python -m med_research.cli modules
python -m med_research.cli disease validate --all --strict
python -m med_research.cli disease coverage ibd
```

`disease validate --all --strict` is the CI guard. `disease coverage <id>` is the stricter researcher-facing report: it distinguishes full, limited, and unsupported module coverage and prints the stable coverage fingerprint. A blocked module must not be interpreted as a successful empty analysis.

### Run analysis modules

Most analysis commands accept `--disease`/`-d`; the current default is `sle` for backwards compatibility.

```bash
python -m med_research.cli kg --disease ra --analyze --export
python -m med_research.cli repurpose --disease sle --top 15 --export-html
python -m med_research.cli bioinformatics --disease sle --export-html
python -m med_research.cli literature --disease ms --max 30 --export-html
python -m med_research.cli screening --disease sle --top 15 --export-html
python -m med_research.cli screening --disease ibd --top 15 --export-html
python -m med_research.cli trials --disease ra --top 20 --export-html
python -m med_research.cli ml --disease sle --top 15 --export-html
python -m med_research.cli cross-disease --disease ra --top 20 --export-html
```

Use `python -m med_research.cli <command> --help` for command-specific options. External-source modules may use caches and may require network access; use the workspace fixture tests for deterministic offline behavior.

### Run the full pipeline

```bash
# Default sequential run-all (core modules)
python -m med_research.cli run-all --disease sle --export-html

# Advanced modules + parallel DAG execution
python -m med_research.cli run-all --disease ra --full --parallel --export-html --skip-ml
```

`run-all` uses the same `execute_module()` dispatch primitive as the web API and Celery `run_module` task. Evidence and semantic modules are optional and excluded from the default step list; use individual CLI commands or `POST /api/jobs/{module_id}` when needed.

Virtual screening is strategy-driven for all seven diseases. Each run reports a strategy ID, deterministic fingerprint, coverage status, curated/inferred inputs, and limitations. A ready/full strategy means disease-specific pathway and drug inputs are present for this transparent property-based prioritization heuristic; it does not establish experimental binding, efficacy, or safety.

### Disease data management

```bash
python -m med_research.cli disease add crohns --name "Crohn's disease" --dry-run
python -m med_research.cli disease refresh ra --dry-run
python -m med_research.cli disease validate ra --strict
python -m med_research.cli disease backups ra
python -m med_research.cli disease restore ra --dry-run
```

Refresh/prune operations create backups before applying destructive changes. Review the prune plan or pass `--yes` only when the source scope is intentional.

## Evidence-to-Hypothesis Workspace

The Workspace turns a question into a cited dossier. The command supports disease selection, source selection, date filters, candidate type, evidence limits, optional LLM enrichment, and JSON/HTML export:

```bash
python -m med_research.cli workspace \
  --disease ra \
  --question "Which JAK interventions merit investigation for rheumatoid arthritis?" \
  --sources pubmed,clinical_trials \
  --candidate-type both \
  --max-evidence 50 \
  --no-llm \
  --json ra-workspace.json \
  --html ra-workspace.html
```

The default sources are `pubmed,clinical_trials`. The dossier preserves source statuses, native identifiers, citations, claims, supporting and contradictory evidence, ranking components, graph path/no-path explanations, warnings, limitations, and a reproducibility fingerprint. See [`docs/evidence-workspace.md`](docs/evidence-workspace.md) for the request contract, dashboard flow, saved-run API, and export behavior.

## Web API and dashboard

Start the API locally:

```bash
python -m med_research.cli serve --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/> for the dashboard. OpenAPI documentation is available at <http://127.0.0.1:8000/api/docs> and the schema at <http://127.0.0.1:8000/api/openapi.json>.

For async dashboard jobs, start Redis and a worker separately:

```bash
redis-server
celery -A med_research.web.tasks.analysis_tasks worker --loglevel=info --concurrency=2
python -m med_research.cli serve --host 127.0.0.1 --port 8000
```

The dashboard's main workspace endpoints are:

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/jobs/workspace` | Submit a validated workspace request |
| `GET` | `/api/jobs/{job_id}` | Poll job state/result |
| `WS` | `/api/jobs/{job_id}/ws` | Stream job progress and terminal state |
| `GET` | `/api/workspace/runs` | List saved runs |
| `GET` | `/api/workspace/runs/{run_id}` | Load one saved run and HTML |
| `DELETE` | `/api/workspace/runs/{run_id}` | Delete a saved run |
| `GET` | `/api/workspace/compare?left=...&right=...` | Compare two runs |
| `GET` | `/api/workspace/trends` | Inspect ranking/source trends |

The complete route inventory and environment settings are in [`docs/api-reference.md`](docs/api-reference.md). The dashboard uses delegated `data-action` controls rather than inline event attributes, so deployments can enable `DASHBOARD_CSP_MODE=enforce` (or `DASHBOARD_CSP=true`) without allowing inline scripts.

## Testing and quality checks

Test tiers (see `pyproject.toml` markers):

| Tier | Command | Scope |
|---|---|---|
| Offline unit | `make test-offline` | Fast suite; excludes `slow` and `integration` |
| Integration | `make test-integration` | Fixture-backed E2E, CLI smoke, web API (no live APIs) |
| Slow/live | `make test-slow` | External API calls; scheduled CI only |

Copy `.env.example` to `.env` for local web/Celery configuration before running dashboard jobs.

```bash
# Fast offline CI-equivalent suite
make test-offline

# Integration (mocked HTTP, full-pipeline E2E for sle/ra/ibd)
make test-integration

# Focused workspace and browser tests
python -m pytest tests/test_evidence_workspace*.py -q

# All configured browser tests (Playwright is installed by requirements-dev.txt)
python -m pytest tests/test_evidence_workspace_browser.py -q

# Slow/live integrations, when external services are available
make test-slow

# Static checks
make lint
make typecheck
make lock-check
python scripts/check_imports.py
python -m compileall -q src/med_research
git diff --check
```

CI runs lint, lock-check, the offline suite with an **80% coverage gate**, integration tests, and disease validation on Python 3.11–3.12, and verifies the installed packages match `requirements-lock.txt` on every push. Slow/live tests run only on scheduled or manually dispatched workflows.

## Docker

Copy the environment template before starting the stack:

```bash
cp .env.example .env
```

The Compose file defines `redis`, `worker`, `web`, and `pipeline` services. The services are under the `full` and `cli` profiles:

```bash
# API, worker, and Redis
docker compose --profile full up --build

# CLI container
 docker compose --profile cli run --rm pipeline diseases
 docker compose --profile cli run --rm pipeline workspace \
   --question "Which interventions merit investigation for SLE?" \
   --no-llm
```

The web service listens on port 8000. Copy `.env.example` to `.env` before `docker compose up`. Set `DOCKER_SKIP_DISEASE_VALIDATE=1` as a build arg for faster local image builds when disease validation is not needed.

Configure `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `USE_CACHE`, `HOST`, `PORT`, `DEBUG`, `CORS_ORIGINS`, `WORKSPACE_DB_PATH`, `API_KEY`, `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW`, and `REDIS_RATE_LIMIT_URL` through the environment as needed. The rate limiter is distributed via Redis when `REDIS_RATE_LIMIT_URL` (default: the Celery broker URL) is reachable and falls back to per-process in-memory limiting otherwise. When using `med-research serve`, explicit `--host`/`--port` values (including their parser defaults) take precedence over `HOST`/`PORT`; see [`docs/api-reference.md`](docs/api-reference.md) for the distinction and security caveats.

## Documentation map

- [`docs/evidence-workspace.md`](docs/evidence-workspace.md) — Workspace tutorial and reference.
- [`docs/disease-curation.md`](docs/disease-curation.md) — Disease validate/coverage/refresh workflow and curation checklist.
- [`docs/deployment.md`](docs/deployment.md) — Self-hosted Docker Compose setup and production env guidance.
- [`docs/licensing.md`](docs/licensing.md) — MIT license and third-party data attribution.
- [`docs/api-reference.md`](docs/api-reference.md) — Current server, job, history, export, and admin endpoints.
- [`docs/superpowers/specs/`](docs/superpowers/specs/) — Historical design specifications.
- [`docs/superpowers/plans/`](docs/superpowers/plans/) — Historical implementation plans and verification records.
- [`CHANGELOG.md`](CHANGELOG.md) — Historical changes; current commands are maintained in this README and `docs/`.
- [`TECHNICAL_DEBT_ISSUES.md`](TECHNICAL_DEBT_ISSUES.md) — Technical audit and remaining follow-up work; resolved findings are labeled.

## Security

This platform is for **research-only public biomedical knowledge** — not for storing or processing patient-identifiable data. When exposing the API beyond localhost, set `DEBUG=false` and a strong `API_KEY`. See [SECURITY.md](SECURITY.md) for the vulnerability reporting process and [docs/deployment.md](docs/deployment.md) for self-hosted setup.

## License and contribution

The project is released under the [MIT License](LICENSE). Contributions in computational biology, immunology, data science, software engineering, testing, and documentation are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, testing expectations, and contribution guidelines. Third-party data licenses are summarized in [docs/licensing.md](docs/licensing.md). Keep source provenance explicit, preserve disease context, avoid overstating computational results, and add deterministic tests for new behavior.
