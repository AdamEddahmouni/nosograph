# API and operations reference

The FastAPI application is `med_research.web.main:app`. It serves the dashboard at `/` and the OpenAPI surface under `/api`.

## Start the server

```bash
python -m med_research.cli serve --host 127.0.0.1 --port 8000
```

The CLI parser defaults are `--host 0.0.0.0` and `--port 8000`; explicit CLI values therefore take precedence when using `med-research serve`. The web application configuration also reads `HOST`, `PORT`, and `DEBUG` from the environment when the app is launched directly. `--reload` is honored only when `DEBUG=true`; otherwise the CLI logs a warning and starts without reload.

Useful URLs:

- Dashboard: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/api/docs`
- ReDoc: `http://127.0.0.1:8000/api/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/api/openapi.json`
- Health: `GET /api/health`

The application preloads the default knowledge graph at startup. The app includes API-key and rate-limit middleware, but authentication is disabled when `API_KEY` is unset, and the limiter is in-memory and per process. Configure and review these policies before exposing the service publicly; do not treat the development defaults as production security.

## Environment settings

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address used by the app entry point. |
| `PORT` | `8000` | Bind port used by the app entry point. |
| `DEBUG` | `false` | Enables debug behavior, including guarded Uvicorn reload. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins. |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker. |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | Celery result backend. |
| `USE_CACHE` | `true` | Enables cache-aware service behavior. |
| `WORKSPACE_DB_PATH` | project `data/evidence_workspace.sqlite3` path | SQLite store for saved Workspace runs. |
| `API_KEY` | empty | When set, requires `X-API-Key` for POST/PUT/PATCH/DELETE and protected evidence/job endpoints; empty disables API-key authentication. |
| `RATE_LIMIT_REQUESTS` | `60` | In-memory requests per client IP per window. Set to `0` to disable. |
| `RATE_LIMIT_WINDOW` | `60` | Rate-limit window in seconds. |

The Celery application uses JSON task/result serialization, UTC, started-state tracking, a 10-minute hard task limit, and a 9-minute soft limit.

## Response and job models

### Job submission

All asynchronous analysis jobs return:

```json
{
  "job_id": "string",
  "status": "PENDING",
  "module": "workspace"
}
```

Workspace is submitted with a JSON `ResearchRequest` at `POST /api/jobs/workspace`; other job endpoints use query parameters.

### Job status

`GET /api/jobs/{job_id}` returns a `JobStatus` object:

```json
{
  "job_id": "string",
  "status": "PENDING | STARTED | PROGRESS | SUCCESS | FAILURE",
  "progress": {"percent": 55, "message": "..."},
  "result": {},
  "error": ""
}
```

Only fields relevant to the state are populated. A successful Workspace result contains `{ "dossier": {...}, "html": "..." }`.

The WebSocket `WS /api/jobs/{job_id}/ws` accepts the connection and emits state changes at approximately 500 ms intervals. It stops on `SUCCESS` or `FAILURE`, emits `ERROR` for orphaned/stream errors, and emits `TIMEOUT` after 1,200 polls (10 minutes). Clients must treat `SUCCESS`, `FAILURE`, `ERROR`, and `TIMEOUT` as terminal states. The HTTP `JobStatus` model documents ordinary Celery states; WebSocket clients should handle the additional `ERROR` and `TIMEOUT` messages.

## Evidence Workspace endpoints

See [`evidence-workspace.md`](evidence-workspace.md) for the full request and dossier contract.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/jobs/workspace` | Queue a Workspace dossier. Body: `ResearchRequest`. |
| `GET` | `/api/jobs/{job_id}` | Poll the job. |
| `WS` | `/api/jobs/{job_id}/ws` | Stream progress. |
| `GET` | `/api/workspace/runs` | List saved run summaries (`limit`, `offset`). |
| `GET` | `/api/workspace/runs/{run_id}` | Load one saved request/dossier/HTML. |
| `DELETE` | `/api/workspace/runs/{run_id}` | Delete one saved run. |
| `GET` | `/api/workspace/compare` | Compare runs with required `left` and `right` query parameters. |
| `GET` | `/api/workspace/trends` | Trend run IDs and rankings; accepts repeated `run_ids` and `limit`. |

## Core analysis endpoints

All routes below are `GET` unless stated otherwise. Disease-query support is listed per endpoint; routes that do not list a disease parameter use the service's current/default context.

| Path | Main query parameters | Description |
|---|---|---|
| `/api/kg/stats` | `disease_id` | Knowledge-graph counts. |
| `/api/kg/graph` | `disease_id` | Graph nodes and edges. |
| `/api/kg/search` | query/filter parameters | Search graph entities. |
| `/api/kg/node/{node_id}` | `disease_id` | Get one node. |
| `/api/kg/path` | path query parameters | Explain a graph path. |
| `/api/kg/neighbors/{node_id}` | `disease_id` | Get neighboring nodes. |
| `/api/kg/centrality` | `metric`, `top_n`, `disease_id` | Centrality scores. |
| `/api/kg/communities` | `disease_id` | Community detection. |
| `/api/repurpose/candidates` | `top_n`, `gene_id`, `disease_id` | Ranked repurposing candidates. |
| `/api/repurpose/gene/{gene_id}` | `disease_id` | Candidate detail for a gene. |
| `/api/bioinformatics/gwas` | `max_studies`, `no_cache` | GWAS annotation; current router uses its configured disease context. |
| `/api/bioinformatics/enrichment` | `untargeted_only`, `no_cache` | Pathway enrichment; current router uses its configured disease context. |
| `/api/bioinformatics/ppi` | `confidence`, `no_cache` | STRING PPI network; current router uses its configured disease context. |
| `/api/literature` | `max_articles`, `targeted`, `no_cache`, `disease_id` | PubMed mining. |
| `/api/screening` | `gene_id`, `top_n`, `use_vina`, `disease_id` | Virtual screening. |
| `/api/trials` | `max_trials`, `query`, `no_cache`, `disease_id` | ClinicalTrials.gov tracking. |
| `/api/ml/predict` | `top_n`, `no_shap` | ML target prediction. |
| `/api/synergy/pairs` | `top_n`, `disease_id` | Drug synergy pairs. |
| `/api/safety/profiles` | `drug_id`, `disease` | Adverse-event safety profiles. |
| `/api/expression/correlate` | `top_n`, `disease_id` | Gene-expression/drug correlation. |
| `/api/cart/suitability` | `top_n`, `disease` | CAR-T suitability. |
| `/api/biomarker/discover` | `top_n`, `disease_id` | Cross-module biomarkers. |
| `/api/semantic/search` | query/top-k/disease parameters | Semantic literature search. |
| `/api/evidence/gather` | `q`, `sources`, `max_per_source`, `use_cache`, `disease_id` | Multi-source evidence gathering. |
| `/api/llm/extract` | extractor query parameters | Optional LLM extraction. |
| `/api/monitor/diff` | monitor query parameters | Evidence-monitor comparison. |
| `/api/monitor/status` | monitor query parameters | Monitor status. |
| `/api/monitor/snapshot` | no body | Trigger a monitor snapshot immediately. |
| `/api/cross-disease/overlap` | — | Shared biology and similarity across seven diseases. |
| `/api/cross-disease/similarity` | — | Disease similarity matrix. |
| `/api/cross-disease/drugs` | `top` | Multi-disease drug rankings. |
| `/api/cross-disease/modules` | `top_synergy` | Comparative module results. |
| `/api/system/diseases` | — | Discovered disease registry and counts. |
| `/api/stats` | `disease_id` where supported | Platform summary statistics. |

The exact parameter constraints and response schemas are authoritative in `/api/openapi.json`.

### Asynchronous analysis job submissions

In addition to Workspace, the following `POST /api/jobs/...` endpoints queue Celery jobs and return the same `JobSubmitResponse` shape: `/api/jobs/gwas`, `/api/jobs/enrichment`, `/api/jobs/ppi`, `/api/jobs/literature`, `/api/jobs/screening`, `/api/jobs/trials`, `/api/jobs/ml`, `/api/jobs/synergy`, and `/api/jobs/safety`. Their query parameters are visible in OpenAPI and mirror the corresponding analysis service options.

## Disease administration endpoints

These endpoints manage source refresh/prune backups and should be treated as administrative operations:

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/admin/diseases/{disease_id}/backups` | List pruned backups. |
| `POST` | `/api/admin/diseases/{disease_id}/prune` | Preview or apply refresh/prune based on the request's `apply` field. |
| `POST` | `/api/admin/diseases/{disease_id}/restore` | Preview or apply backup restoration. |
| `GET` | `/api/admin/diseases/{disease_id}/audit` | Read prune/restore audit entries; `limit` is clamped to 1–500. |

## Export endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/export/modules` | List known module result files and availability. |
| `GET` | `/api/export/json/{module}` | Parse and return the latest module JSON. |
| `GET` | `/api/export/raw/{module}` | Download the original JSON file. |
| `GET` | `/api/export/report/{module}` | Download a generated HTML report. |
| `GET` | `/api/export/report/{module}/print.css` | Return the shared print stylesheet. |

Export modules are configured in `src/med_research/web/routers/export.py`; a missing result/report returns HTTP 404 rather than an empty success response.

## Container operations

```bash
# Start Redis, the API, and the worker
 docker compose --profile full up --build

# Run a CLI command in the pipeline container
 docker compose --profile cli run --rm pipeline diseases
```

The Compose `web` service exposes port 8000. The `worker` service runs `celery -A med_research.web.tasks.analysis_tasks worker --loglevel=info --concurrency=2`.
