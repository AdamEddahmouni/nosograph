# API and operations reference

The FastAPI application is `med_research.web.main:app`. It serves the dashboard at `/` and the OpenAPI surface under `/api`.

## Start the server

```bash
python -m med_research.cli serve --host 127.0.0.1 --port 8000
```

The CLI parser defaults are `--host 0.0.0.0` and `--port 8000`; explicit CLI values therefore take precedence when using `med-research serve`. The web application configuration also reads `HOST`, `PORT`, and `DEBUG` from the environment when the app is launched directly. `--reload` is honored only when `DEBUG=true`; otherwise the CLI logs a warning and starts without reload.

Useful URLs:

- Dashboard: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/api/docs` (only when `OPENAPI_ENABLED` is truthy — enabled by default only when `DEBUG=true`)
- ReDoc: `http://127.0.0.1:8000/api/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/api/openapi.json`
Health: `GET /api/health`

````bash
curl http://127.0.0.1:8000/api/health
````

Example response:

````json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": "2026-08-22T14:03:11.123456"
}
````
- Readiness: `GET /api/ready`

The application preloads the default knowledge graph at startup. API-key middleware protects deployment-level mutation endpoints when `API_KEY` is set. Researcher ownership uses a separate server-derived principal: local deployments issue signed HttpOnly sessions, while production deployments can use a trusted identity-aware reverse proxy. Do not treat development compatibility behavior as production security.

## Environment settings

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address used by the app entry point. |
| `PORT` | `8000` | Bind port used by the app entry point. |
| `DEBUG` | `false` | Enables debug behavior, including guarded Uvicorn reload. |
| `OPENAPI_ENABLED` | `true` when `DEBUG=true`, else `false` | Serves `/api/docs`, `/api/redoc`, and `/api/openapi.json`. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins. |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker. |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | Celery result backend. |
| `USE_CACHE` | `true` | Enables cache-aware service behavior. |
| `WORKSPACE_DB_PATH` | project `data/evidence_workspace.sqlite3` path | SQLite store for saved Workspace runs, alert delivery state, and weekly digest delivery state. |
| `BIOMEDICAL_DB_PATH` | project `data/biomedical.sqlite3` path | Canonical biomedical knowledge store for versioned ontology snapshots, entities, claims, evidence, and research runs. Separate from the Evidence Workspace database. |

Initialize the biomedical store from the CLI:

```bash
python -m med_research.cli biomed init
python -m med_research.cli biomed init --db /path/to/biomedical.sqlite3
make biomed-init
```

Import pinned ontology or evidence artifacts (operator-supplied local files; choices: `mondo`, `hp`, `hpoa`, `clinvar`, `openfda`, `go`, `reactome`, `uberon`):

```bash
python -m med_research.cli biomed import mondo --artifact /path/to/mondo.json
python -m med_research.cli biomed import hp --artifact /path/to/hp.json
python -m med_research.cli biomed import hpoa --artifact /path/to/phenotype.hpoa.tsv
python -m med_research.cli biomed import clinvar --artifact /path/to/clinvar.json
python -m med_research.cli biomed import openfda --artifact /path/to/openfda.json
python -m med_research.cli biomed import go --artifact /path/to/go.json
python -m med_research.cli biomed import reactome --artifact /path/to/reactome.json
python -m med_research.cli biomed import uberon --artifact /path/to/uberon.json
python -m med_research.cli biomed snapshots list
python -m med_research.cli biomed snapshots list --resource mondo
make biomed-import-fixtures
```

Download and import the full MONDO/HPO/HPOA artifacts (parallel downloads, slim or full hierarchy, checksum-pinned):

```bash
python scripts/setup_biomed_imports.py            # slim import (pipeline-focused, default)
python scripts/setup_biomed_imports.py --full     # full hierarchy import (slower)
python scripts/setup_biomed_imports.py --from-fixtures  # minimal test fixtures
python scripts/setup_biomed_imports.py --mondo-only
make biomed-import
```

Migrate curated legacy disease modules into canonical claims (requires an active Mondo snapshot; legacy JSON loaders remain authoritative for existing modules):

```bash
python -m med_research.cli biomed migrate legacy
python -m med_research.cli biomed migrate legacy --disease sle --report /tmp/parity.json
make biomed-migrate-legacy
```

Pinned artifact imports and verification:

```bash
make biomed-import-fixtures
make biomed-import
make biomed-verify
python scripts/setup_biomed_imports.py --from-fixtures
python scripts/verify_biomed_imports.py --from-fixtures --check-store
```

`data/biomed/pinned-artifacts.json` pins both the minimal fixture checksum (`fixture_checksum`) and the full downloaded artifact checksum (`download_checksum`) for MONDO, HPO, and HPOA. `setup_biomed_imports.py` verifies the source artifact against the matching pin before importing; `verify_biomed_imports.py` re-checks the artifact files and active store snapshots, accepting either the fixture or the full-download checksum so both a fixture-backed and a full-import store verify cleanly.

Set `BIOMED_LEGACY_PROJECTION=1` to enable optional read-only canonical claim diagnostics when a `legacy-curated` snapshot is active. Graph construction continues to use the JSON loaders by default.

Mondo is CC BY 4.0 redistributable. HPO and HPO annotation releases are operator-supplied under their upstream licenses. Imports are checksum-verified, idempotent, and activate the new snapshot on success. HPOA joins disease identifiers to Mondo through exact published mappings only.

The store is research-only public biomedical knowledge. It does not accept patient or case data. Imported snapshots, claims, evidence links, and terminal research runs are immutable; corrections create new records rather than rewriting history.

### Universal biomedical API (`/api/v1`)

Versioned read-only condition endpoints backed by the canonical biomedical store. Every response includes a `disclaimer` field with research-only language. Pagination defaults to `limit=50` (allowed range `1–200`). Hierarchy traversal accepts `depth` `0–3`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/conditions/search` | Search imported conditions by label or synonym |
| GET | `/api/v1/conditions/{curie}` | Condition summary, mappings, readiness, active snapshots |
| GET | `/api/v1/conditions/{curie}/hierarchy` | Parent/child `IS_A` nodes up to `depth` |
| GET | `/api/v1/conditions/{curie}/claims` | Claims with optional `predicate` and `evidence_direction` filters |
| GET | `/api/v1/snapshots` | List resource snapshots with active flags |
| GET | `/api/v1/snapshots/{snapshot_id}/report` | Import report metadata for a snapshot |
| POST | `/api/v1/comparisons` | Compare two condition CURIEs and persist a research run |
| GET | `/api/v1/comparisons/{run_id}` | Fetch a persisted comparison research run |
| GET | `/api/v1/analytics/stats` | Overall biomedical store summary statistics and entity/predicate distributions |
| GET | `/api/v1/analytics/targets/{curie}` | Prioritize disease targets using vectorized evidence and degree scoring (`top_k` 1–100) |
| GET | `/api/v1/analytics/shared-mechanisms` | Compute shared biological pathways, genes, and Jaccard similarity between two condition CURIEs |
| GET | `/api/v1/analytics/subgraph/{curie}` | Multi-hop subgraph traversal around an entity CURIE (`max_hops` 1–4, `limit` 1–500) |
| GET | `/api/v1/biomed/pathways` | Find claim paths between a `start_curie` and `target_curie` (`max_depth` 1–5, `limit` 1–50) |
| GET | `/api/v1/biomed/target-prioritization/{disease_curie}` | Rank targets for a disease by supporting/contradictory evidence and normalized centrality (`top_k` 1–50) |

Examples:

```bash
curl "http://127.0.0.1:8000/api/v1/conditions/search?q=lupus&limit=5"
curl "http://127.0.0.1:8000/api/v1/conditions/MONDO:0007915"
curl "http://127.0.0.1:8000/api/v1/conditions/MONDO:0007915/hierarchy?depth=2"
curl "http://127.0.0.1:8000/api/v1/conditions/MONDO:0007915/claims?predicate=HAS_PHENOTYPE&limit=20"
curl "http://127.0.0.1:8000/api/v1/snapshots?resource=mondo"
curl -X POST "http://127.0.0.1:8000/api/v1/comparisons" \
  -H "Content-Type: application/json" \
  -d '{"left_curie":"MONDO:0007915","right_curie":"MONDO:0008390"}'
curl "http://127.0.0.1:8000/api/v1/comparisons/{run_id}"
```

CLI comparison and graph analytics:

```bash
python -m med_research.cli biomed compare --left MONDO:0007915 --right MONDO:0008390 --db data/biomedical.sqlite3
python -m med_research.cli biomed analytics --disease MONDO:0007915 --top 20
python -m med_research.cli biomed analytics --disease MONDO:0007915 --compare-with MONDO:0008390
python -m med_research.cli biomed analytics --stats
```

Live condition/gene lookups against external providers use the `live` command:

```bash
python -m med_research.cli live --target JAK2 --disease ra --source all
```

`live` supports `opentargets`, `gtex`, `chembl`, `uniprot`, and `biorxiv` sources through the `pipeline.external` connectors. The biomedical store import CLI accepts `mondo`, `hp`, `hpoa`, `clinvar`, `openfda`, `go`, `reactome`, and `uberon` (ClinVar/openFDA use pinned fixtures by default; see `make biomed-import-clinvar`).

Corpus readiness tiers (L0–L3) are reported by `med-research disease corpus-status` and exposed at `GET /api/system/corpus-status`. Disease list responses include `mondo_curie`, `efo_id`, and `readiness_tier` when available.

Absent imported data is returned as empty lists or `No data imported for this section` placeholders in the dashboard explorer; it is never treated as contradictory evidence. Legacy `/api/*` routes remain unchanged.

Additional environment settings:

| Variable | Default | Purpose |
|---|---|---|
| `ALERT_SMTP_HOST` | empty | Enables email delivery when a researcher opts in and configures an email address. |
| `ALERT_SMTP_PORT` | `587` | SMTP port; port `465` uses implicit TLS. |
| `ALERT_SMTP_USERNAME` | empty | Optional SMTP username. |
| `ALERT_SMTP_PASSWORD` | empty | Optional SMTP password. Keep this in deployment secrets. |
| `ALERT_SMTP_FROM` | username or `alerts@localhost` | Optional sender address. |
| `ALERT_SMTP_USE_TLS` | `true` | Start TLS for non-465 SMTP connections unless set to `false`. |
| `WORKSPACE_PUBLIC_URL` | `http://127.0.0.1:8000` | Public dashboard origin used in signed digest review links. |
| `WORKSPACE_REVIEW_LINK_SECRET` | empty | HMAC secret for expiring review links; required unless `API_KEY` is used as the fallback secret. Keep it in deployment secrets. |
| `API_KEY` | empty | When set, requires `X-API-Key` for POST/PUT/PATCH/DELETE and protected evidence/job/cache endpoints; empty disables API-key authentication. |
| `RATE_LIMIT_REQUESTS` | `60` | Requests per client IP per window. Distributed via Redis when reachable, with an in-memory per-process fallback. Set to `0` to disable. |
| `RATE_LIMIT_WINDOW` | `60` | Rate-limit window in seconds. |
| `RATE_LIMIT_FAIL_CLOSED` | `false` | When the Redis rate-limit store is unreachable, deny requests instead of failing open. |
| `REDIS_RATE_LIMIT_URL` | `CELERY_BROKER_URL`, else `redis://localhost:6379/0` | Redis URL for the distributed sliding-window rate-limit store. When unreachable, the limiter falls back to per-process in-memory limiting. |
| `MAX_REQUEST_BODY_BYTES` | `10485760` | Maximum accepted request body size (10 MiB) for POST/PUT/PATCH. |
| `AUTH_MODE` | `local` | Researcher authentication mode: `local` signed sessions or `proxy` trusted reverse-proxy identity. |
| `LOCAL_AUTH_USERS` | empty | Development-only JSON map such as `{"alice":"password"}` or comma-separated `alice=password` accounts. Store it as a deployment secret. |
| `AUTH_SESSION_SECRET` | empty | HMAC secret for local researcher session cookies; required outside `DEBUG` unless `API_KEY` is used as a fallback. |
| `AUTH_TRUSTED_PROXY_IPS` | empty | Comma-separated proxy source IPs allowed to provide `X-Authenticated-User`, `X-Auth-Request-User`, or `Remote-User` when `AUTH_MODE=proxy`. |
| `DASHBOARD_CSP_MODE` | `off` | Dashboard document CSP mode: `off`, `report-only`, or `enforce`. `DASHBOARD_CSP=true` is an alias for `enforce`. |

Researcher ownership is server-derived. In `AUTH_MODE=local`, call `POST /api/auth/login` with a configured local account; the API sets an expiring HttpOnly session cookie. In `AUTH_MODE=proxy`, the application accepts an identity header only from a source address listed in `AUTH_TRUSTED_PROXY_IPS`. The historical `X-Researcher-ID` header is accepted only in `DEBUG=true` compatibility mode and is never an authentication mechanism in production.

The Celery application uses JSON task/result serialization, UTC, started-state tracking, a 10-minute hard task limit, and a 9-minute soft limit. Celery Beat publishes the digest dispatcher every 60 seconds; run one Beat process alongside the worker in production.

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

Server-Sent Events `GET /api/stream/jobs/{job_id}` is an alternative to the WebSocket: it polls Celery every 500 ms and emits `event: job_status` JSON messages, terminating on `SUCCESS`, `FAILURE`, or `REVOKED`.

## Evidence Workspace endpoints

See [`evidence-workspace.md`](evidence-workspace.md) for the full request and dossier contract.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Local mode only; exchange a configured development username/password for an HttpOnly researcher session. |
| `GET` | `/api/auth/me` | Return the current server-derived authentication state. |
| `POST` | `/api/auth/logout` | Clear the current researcher session cookie. |
| `POST` | `/api/jobs/workspace` | Queue a Workspace dossier and bind it to the authenticated researcher principal. Body: `ResearchRequest`. |
| `GET` | `/api/jobs/{job_id}` | Poll the job. |
| `WS` | `/api/jobs/{job_id}/ws` | Stream progress. |
| `GET` | `/api/workspace/alerts` | List the requesting researcher's unread/all review reminders (`unread_only`, `limit`, `offset`); dispatches configured pending notifications. |
| `POST` | `/api/workspace/alerts/{alert_id}/read` | Mark one owned review reminder as read. |
| `GET` | `/api/workspace/notifications` | Load owned email/Slack notification settings and latest delivery status (Slack secrets are never returned). |
| `PUT` | `/api/workspace/notifications` | Save owned notification settings, thresholds, weekly digest opt-in/schedule, and attempt pending email/Slack deliveries. Supports metric thresholds, `weekly_digest_enabled`, weekday/hour/minute, and an IANA timezone. |
| `GET` | `/api/workspace/digest` | Preview the previous completed UTC calendar week's new evidence, unresolved reminders, and changed decisions. |
| `POST` | `/api/workspace/digest/send` | Send the opt-in weekly digest through configured channels; `force=true` manually retries an already delivered period. |
| `GET` | `/api/workspace/digest/delivery-history` | List researcher-owned digest delivery attempts and failure details (`limit` 1–200). |
| `GET` | `/api/workspace/digest/review` | Validate an expiring signed review token and redirect to the researcher dashboard context. |
| `GET` | `/api/workspace/runs` | List saved run summaries (`limit`, `offset`). |
| `GET` | `/api/workspace/runs/{run_id}` | Load one saved request/dossier/HTML. |
| `DELETE` | `/api/workspace/runs/{run_id}` | Delete one saved run and its review history. |
| `GET` | `/api/workspace/runs/{run_id}/reviews` | Load the requesting researcher's candidate notes, tags, decisions, and provenance. |
| `GET` | `/api/workspace/runs/{run_id}/review-events` | Load the requesting researcher's append-only decision history for a run. |
| `GET` | `/api/workspace/runs/{run_id}/graph` | Return the interactive evidence graph for candidates, claims, citations, pathways, and owned review decisions. |
| `PUT` | `/api/workspace/runs/{run_id}/reviews` | Save a candidate decision, rationale, notes, tags, and “what changed my mind?” entry. |
| `GET` | `/api/workspace/runs/{run_id}/review-bundle` | Download a citation-ready ZIP containing Markdown, CSV citations, exact dossier JSON, reviews, review events, and provenance. |
| `GET` | `/api/workspace/candidate-history` | Track one candidate’s ranking, evidence additions/removals, and reviews across runs. |
| `GET` | `/api/workspace/compare` | Compare runs with required `left` and `right` query parameters, including candidate evidence and review changes. |
| `GET` | `/api/workspace/trends` | Trend run IDs, rankings, and candidate evidence changes; accepts repeated `run_ids` and `limit`. |

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
| `/api/cross-disease/overlap` | — | Shared biology and similarity across the curated disease set. |
| `/api/cross-disease/similarity` | — | Disease similarity matrix. |
| `/api/cross-disease/drugs` | `top` | Multi-disease drug rankings. |
| `/api/cross-disease/modules` | `top_synergy` | Comparative module results. |
| `/api/system/diseases` | — | Discovered disease registry and counts (10,403 modules). |
| `/api/system/corpus-status` | — | Corpus readiness tier aggregate from latest batch report. |
| `/api/system/modules` | `disease` (default `sle`) | Pipeline module catalog (registry module IDs, aliases, request schemas, contracts). |
| `/api/ready` | — | Readiness check across Redis, Celery, workspace DB, and KG preload. |
| `/api/stats` | `disease_id` where supported | Platform summary statistics (disease, modules, KG counts, coverage summary). |

The exact parameter constraints and response schemas are authoritative in `/api/openapi.json`. Workspace review, alert, notification, digest, graph, history, and export routes use the authenticated session/proxy principal; they no longer accept a researcher identity from dashboard request headers.

### Asynchronous analysis job submissions

All registry-backed modules can be queued via the unified endpoint:

`POST /api/jobs/{module_id}` — query parameters validated by `GenericModuleJobRequest` (`disease_id`, module-specific opts). Dispatches through `task_run_module` → `registry_service.run_module_job()` → `execute_module()`. Registered modules include `admet`, `crispr`, `multi_omics`, and `structure_3d` alongside the classic modules; the exact request options are generated from the registry catalog and surfaced in `/api/openapi.json`.

Legacy aliases remain for dashboard compatibility: `/api/jobs/gwas`, `/api/jobs/enrichment`, `/api/jobs/ppi`, `/api/jobs/literature`, `/api/jobs/screening`, `/api/jobs/trials`, `/api/jobs/ml`, `/api/jobs/synergy`, and `/api/jobs/safety`. These thin wrappers delegate to the same `run_module` Celery task.

`POST /api/jobs/workspace` accepts a JSON `ResearchRequest` body for evidence workspace dossiers.

`POST /api/jobs/run-all` queues a full pipeline orchestration (mirrors CLI `run-all`). Query parameters: `disease_id`, `full`, `parallel`, `skip_ml`, `export_html`, `no_cache`. Dispatches `task_run_all` → `registry_service.run_all_pipeline()` → `scheduler.py` + `execute_module()`. Successful Celery results include `modules_completed`, `report_paths` (when `export_html=true`), and any per-module `errors`.

When `export_html=true` on `POST /api/jobs/{module_id}`, the Celery result includes `report_path` in the task result payload.

### Error responses

Validation failures return HTTP 422 with Pydantic error detail. Blocked pipeline modules on synchronous routes raise `ModuleNotAvailableError` and return **HTTP 409** with `{ "detail": "...", "error_type": "ModuleNotAvailableError" }`. Other pipeline execution failures from job handlers use structured errors via `error_handlers.py`.

## Cache administration

Auth-protected when `API_KEY` is set (prefix `/api/system/cache`).

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/system/cache/stats` | Namespace entry counts and byte sizes. |
| `DELETE` | `/api/system/cache` | Clear all cache namespaces. |
| `DELETE` | `/api/system/cache/{namespace}` | Clear one namespace (e.g. `gwas`, `literature_mining`). |

Response for deletes: `{ "removed": <int>, "namespace": <str|null> }`.

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

The Compose `web` service exposes port 8000. The `worker` service runs `celery -A med_research.web.tasks.analysis_tasks worker --loglevel=info --concurrency=2`, and the `beat` service runs the one required scheduler process. Do not run multiple Beat instances against the same deployment.
