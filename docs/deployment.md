# Self-Hosted Deployment

This guide covers running NosoGraph locally or on a private server with Docker Compose. For API details, see [api-reference.md](api-reference.md).

## Prerequisites

- Docker and Docker Compose v2
- At least 4 GB RAM (more for full disease validation builds)
- Optional: Redis reachable at `CELERY_BROKER_URL` when not using Compose

## Quick start

1. Clone the repository and copy the environment template:

   ```bash
   git clone https://github.com/AdamEddahmouni/nosograph.git
   cd nosograph
   cp .env.example .env
   ```

2. Edit `.env` for your environment. For local development, defaults are sufficient (`DEBUG=true`, empty `API_KEY`).

3. Start the stack:

   ```bash
   docker compose --profile full up --build
   ```

4. Open the dashboard at `http://localhost:8000`.

## Environment variables

| Variable | Local default | Production recommendation |
|----------|---------------|---------------------------|
| `DEBUG` | `true` | `false` |
| `API_KEY` | empty | Strong random secret (required when `DEBUG=false`) |
| `AUTH_SESSION_SECRET` | empty | Random secret for workspace sessions |
| `CORS_ORIGINS` | localhost origins | Your front-end origin(s) only |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Internal Redis URL |
| `OPENAPI_ENABLED` | follows `DEBUG` | `false` to hide `/api/docs` |
| `BIOMEDICAL_DB_PATH` | `<repo>/data/biomedical.sqlite3` | Persistent volume path for the universal biomedical store |

See [.env.example](https://github.com/AdamEddahmouni/nosograph/blob/master/.env.example) for the full list.

## Authentication modes

The platform uses two complementary auth layers:

1. **API key (`X-API-Key` header)** — protects job submission, cache admin, and job status/WebSocket streams when `API_KEY` is set. WebSocket clients may pass `?api_key=` as a query parameter.

2. **Researcher sessions** — Evidence Workspace routes require login via `/api/auth/login` (`AUTH_MODE=local`) or a trusted reverse proxy (`AUTH_MODE=proxy`).

## Health checks

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Liveness — process is running |
| `GET /api/ready` | Readiness — Redis, Celery, workspace DB, and KG preload |

Docker Compose configures a healthcheck on the `web` service using `/api/health`.

## Faster Docker builds

The Dockerfile runs `disease validate --all --strict` at image build time. With the full 10,000+ module registry this is slow and, because scaffolded modules report config gaps, strict mode exits non-zero. For iterative dev builds, skip validation:

```bash
docker compose build --build-arg DOCKER_SKIP_DISEASE_VALIDATE=1 web
```

Gate release builds on an individual curated module instead:

```bash
python -m med_research.cli disease validate sle --strict
```

GitHub Actions runs on push/PR when the repository is **public** (free hosted runners).
While private, quota may block jobs — see [public launch readiness](public-launch.md).
Use `make ci-local` locally before pushing. The workflow does **not** run
`disease validate --all --strict` (scaffolds fail that check by design).

## Data persistence

Runtime data lives under `./data` (mounted to `/app/data` in containers):

- `evidence_workspace.sqlite3` — workspace run history
- `biomedical.sqlite3` — universal biomedical store
- Pipeline caches and report outputs

Back up this directory before upgrades. It is listed in `.gitignore` and is not version-controlled.

Initialize and populate the universal biomedical store on first boot if `/api/v1` condition features are needed:

```bash
python -m med_research.cli biomed init
python -m med_research.cli biomed import mondo --artifact /path/to/mondo.json
python -m med_research.cli biomed import hp --artifact /path/to/hp.json
python -m med_research.cli biomed import hpoa --artifact /path/to/phenotype.hpoa.tsv
```

For test/demo data, `make biomed-import-fixtures` loads the minimal checked-in fixture bundle; `make biomed-verify` validates checksums and active store snapshots.

## Research-only policy

This platform is for **public biomedical knowledge and computational research**. Do not store or process patient-identifiable data (PHI). See [SECURITY.md](https://github.com/AdamEddahmouni/nosograph/blob/master/SECURITY.md) and [licensing.md](licensing.md).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Web container exits on start | `DEBUG=false` without `API_KEY` | Set `API_KEY` or `DEBUG=true` in `.env` |
| Jobs stay `PENDING` | Worker not running | `docker compose --profile full up worker` |
| `429 Too Many Requests` | Rate limit hit | Raise `RATE_LIMIT_REQUESTS` or wait |
| `/api/ready` returns 503 | Redis/Celery unreachable | Check `redis` service and broker URLs |
