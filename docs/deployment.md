---
title: Self-hosted deployment
description: Operate NosoGraph locally or on a private server with Docker Compose and explicit security boundaries.
---

# Self-Hosted Deployment

This is the canonical deployment guide for local or privately operated NosoGraph instances. **A public hosted demo is not deployed.** GitHub Pages is documentation only. For first-time local setup, use [Installation](getting-started/install.md); for API routes, use the [API reference](api-reference.md).

This platform is research software. It is not HIPAA/GDPR/FDA certified by this repository.

## Security assumptions (self-host)

These are practical defaults, not a compliance program:

| Control | Default | Intent |
|---------|---------|--------|
| `DEBUG=false` | Requires `API_KEY` | Fail-fast outside local debug |
| Dashboard CSP | `DASHBOARD_CSP_MODE=enforce` | Dashboard + satellite HTML. Allows `'self'` plus cdnjs for 3Dmol/Cytoscape. Pipeline HTML reports may still load Google Fonts and are **not** covered by this document CSP. |
| Rate limit | 60 req / 60s / IP | Redis when reachable; **in-memory fallback** if Redis is down. `RATE_LIMIT_FAIL_CLOSED=false` is **intentional** so a Redis outage does not make the app unusable. Set `true` only if you would rather 429 than fail open. |
| GET APIs | Public except `PROTECTED_PREFIXES` | When `API_KEY` is set, mutations and `/api/jobs`, `/api/llm/extract`, `/api/evidence/gather`, `/api/system/cache` require the key. Other GETs stay public **by design** for local research. Do not assume this is safe on the public internet. |
| `DEMO_MODE` | `false` | Opt-in read-only guard. Not a hosted demo. |
| Researcher auth | `AUTH_MODE=local` | Cookie sessions or trusted proxy. Not SSO. DEBUG uses a weak session fallback — do not expose DEBUG. |
| Redis in Compose | published `6379:6379` | Bind to localhost in production; do not expose Redis to the internet. |

No new authentication system is introduced. This is not a multi-tenant SaaS.

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

### Read-only demo profile (local)

Fixture-backed snapshot + `DEMO_MODE=true`. This does **not** publish a hosted demo.

```bash
docker compose --profile demo run --rm pipeline demo build
docker compose --profile demo up web-demo --build
```

`pipeline demo build` writes `data/demo/biomedical.sqlite3` and its manifest into
the mounted `./data` directory. The `web-demo` service sets
`DEMO_SNAPSHOT_PATH`/`DEMO_SNAPSHOT_MANIFEST` to those `/app/data/demo/...`
paths and `DEMO_REQUIRE_MODE=true`; startup refuses to boot if the snapshot is
missing or inconsistent. The single-container `docker-compose.demo.yml` bakes the
snapshot into the image instead.

See [Demo](getting-started/demo.md). Operator notes live in the repository at `docs/deployment/local-demo-operator.md` (excluded from GitHub Pages).

## Environment variables

| Variable | Local default | Production recommendation |
|----------|---------------|---------------------------|
| `DEBUG` | `true` | `false` |
| `API_KEY` | empty | Strong random secret (required when `DEBUG=false`) |
| `AUTH_SESSION_SECRET` | empty | Random secret for workspace sessions |
| `CORS_ORIGINS` | localhost origins | Your front-end origin(s) only |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Internal Redis URL |
| `DASHBOARD_CSP` / `DASHBOARD_CSP_MODE` | `true` / `enforce` | `off` only if you must disable document CSP |
| `RATE_LIMIT_FAIL_CLOSED` | `false` | `true` only if Redis outage should 429 instead of in-memory fallback |
| `DEMO_MODE` | `false` | `true` only for an intentional read-only instance |
| `OPENAPI_ENABLED` | follows `DEBUG` | `false` to hide `/api/docs` |
| `BIOMEDICAL_DB_PATH` | `<repo>/data/biomedical.sqlite3` | Persistent volume path for the universal biomedical store |

See [.env.example](https://github.com/AdamEddahmouni/nosograph/blob/master/.env.example) for the full list. `DEMO_MODE` must stay false unless you are operating an intentional read-only instance. There is no hosted public app.

## Authentication modes

The platform uses two complementary auth layers:

1. **API key (`X-API-Key` header)** — protects job submission, cache admin, and job status/WebSocket streams when `API_KEY` is set. WebSocket clients may pass `?api_key=` as a query parameter.

2. **Researcher sessions** — Evidence Workspace routes require login via `/api/auth/login` (`AUTH_MODE=local`) or a trusted reverse proxy (`AUTH_MODE=proxy`).

## Port contract

The application resolves its listen port from `PORT` in one place
(`med_research.web.config.resolve_port`):

| Value | Result |
|-------|--------|
| unset / empty | `8000` (`DEFAULT_PORT`) |
| integer `1`–`65535` | that port, everywhere |
| non-integer, `0`, negative, or `>65535` | startup fails with an actionable error |

Both Dockerfiles declare `ENV PORT=8000` and run `serve --host 0.0.0.0` with no
hard-coded port. Both Compose files publish, listen on, and probe the same
`${PORT:-8000}` value, so a platform that injects `PORT` (Heroku, Railway, Fly,
Cloud Run, App Runner) needs no Dockerfile override. Bind the host publish to
loopback when the instance is not meant to be reachable beyond the machine.

Do not set `PORT` in `.env` for Compose *and* pass a different `--port` to the
CLI at the same time; the environment value wins and the mismatch is a common
source of "container is healthy but nothing answers on my expected port".

## Health and readiness probes

| Endpoint | Purpose | Dependency-aware |
|----------|---------|------------------|
| `GET /api/health` | Liveness — the process is running | No. It never touches Redis, Celery, or the database, so a dependency outage cannot restart a healthy container. |
| `GET /api/ready` | Readiness — safe to send traffic | Yes. Checks Redis, Celery, workspace DB, and KG preload; returns `503` unless every component is `ok`. In demo mode it validates the baked snapshot instead and skips the probes the demo image does not ship. |

Docker Compose configures the container healthcheck against `/api/health`, and
the injected `PORT` is used in the probe URL. Use `/api/ready` for load-balancer
target groups: a `503` means "do not route traffic yet", not "restart me".

## Environment validation

Startup validates the environment once and raises a single error listing **every**
problem, not only the first. Each of these is rejected:

| Condition | Why it fails |
|-----------|--------------|
| `DEBUG=false` and no `API_KEY` | Would expose mutation/admin routes without authentication |
| `PORT` not an integer in `1`–`65535` | Would bind a different port than the platform routed to |
| `CORS_ORIGINS` explicitly empty when `DEBUG=false` | Browser clients are silently disabled (unset falls back to the documented default) |
| `CORS_ORIGINS` contains `*` when `DEBUG=false` | Wildcard origins with credentialed requests |
| `DEMO_MODE=true` with `DEMO_ALLOW_WRITES` / `ALLOW_WRITES` / `DEMO_WRITE_ENABLED` | The read-only demo refuses write-enabled configuration; no write path is added |

`DEMO_MODE=true` exempts the `API_KEY` requirement because the demo middleware
rejects mutating routes regardless of credentials. Validate the same rules
without starting the app:

```bash
python -c "from med_research.web.config import validate_runtime_config; print(validate_runtime_config())"
```

An empty list means valid. The check is pure when passed a mapping, which is how
the unit tests exercise it.

## Faster Docker builds

The Dockerfile runs `disease validate --all --strict` at image build time. With the full 10,000+ module registry this is slow and, because scaffolded modules report config gaps, strict mode exits non-zero. For iterative dev builds, skip validation:

```bash
docker compose build --build-arg DOCKER_SKIP_DISEASE_VALIDATE=1 web
```

Gate release builds on an individual curated module instead:

```bash
python -m med_research.cli disease validate sle --strict
```

GitHub Actions runs on push/PR when the repository is **public** (free hosted runners). Use `make ci-local` locally before pushing. The workflow does not run `disease validate --all --strict` (scaffolds fail that check by design).

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

## Container smoke test

`scripts/docker_smoke.py` builds (or reuses) one image, boots it with an
injected `PORT`, and verifies the probes on that port. It uses only the Python
standard library, prints one JSON object, and always removes the container in a
`finally` block, including when a check fails.

```bash
# Full image: build, boot on 8080, require liveness
python scripts/docker_smoke.py --port 8080

# Verify only that the image builds, on a hard time bound
python scripts/docker_smoke.py --build-only --image nosograph-smoke:local --build-timeout 900

# Existing demo image: assert the read-only guards as well
python scripts/docker_smoke.py --no-build --image nosograph-demo:latest --demo

# Require readiness too (the full image needs Redis for that)
python scripts/docker_smoke.py --require-ready
```

| Flag | Meaning |
|------|---------|
| `--port` | Injected `PORT`; `0` picks a free loopback port |
| `--image` | Tag to build and run (default `nosograph-smoke:<port>`) |
| `--dockerfile` | Dockerfile for the build (default `Dockerfile`) |
| `--target` | Build stage to build, so a cached runtime stage is reused |
| `--timeout` | Application readiness timeout in seconds |
| `--build-timeout` | Hard bound for the image build (default 900 s) |
| `--daemon-timeout` | Hard bound for `docker info` (default 60 s) |
| `--cleanup-timeout` | Hard bound for each container/image removal |
| `--build-only` | Verify the build and stop; mutually exclusive with `--no-build` |
| `--no-build` | Reuse an existing image (requires `--image`) |
| `--validate-diseases` | Run the full-registry strict validation during the build. Off by default because that gate walks 10k+ modules and exits non-zero on generated scaffolds by design; the default build passes `DOCKER_SKIP_DISEASE_VALIDATE=1`. |
| `--demo` | Mirror the demo contract (`DEBUG=false`, `DEMO_MODE=true`, `DEMO_REQUIRE_MODE=true`) and require `403 demo_read_only` on job submission and cache admin |
| `--require-ready` | Fail unless `/api/ready` returns `200` |
| `--env KEY=VALUE` | Extra container environment (repeatable) |
| `--report PATH` | Also write the JSON report to `PATH` |
| `--verbose` | Echo command diagnostics to stderr |
| `--keep` | Leave the container and image behind for inspection |

Every command the harness runs is bounded. Output is captured through
temporary files rather than pipes, because `subprocess.run(capture_output=True,
timeout=...)` does not bound a hung `docker build` — on timeout CPython kills
the direct child and then re-reads the pipes with no timeout, so a grandchild
holding the inherited write handle blocks forever. On a timeout the harness
kills the whole process tree, records `timed_out`, and returns.

Containers are named with a per-run token and labelled
`dev.nosograph.smoke=1`; only those are ever removed. Unrelated containers are
never touched. A reused `--no-build` image is reported as
`image_origin: "reused"` with its creation timestamp, so a cached image is
never presented as built from the current source tree.

A check with `required: false` (``/api/ready`` unless `--require-ready` is
passed) is reported truthfully in `observed_not_ok` without failing the run: a
bare container legitimately answers `503` because it ships no Redis, Celery
worker, or database. Deep-link the report to the failing components — the
detail names them (for example `not_ok=celery,redis,workspace_db`).

`--demo` expects the demo image. Point it at `--dockerfile Dockerfile.demo` (or
`--no-build --image nosograph-demo:latest`), because the demo contract requires
the snapshot baked in at build time.

The smoke test proves the container starts and answers on the injected port. It
does **not** prove a hosted deployment exists, and it does not replace
`/api/ready` monitoring in the target environment.

## Staging checklist (provider-neutral)

Nothing in this repository is deployed, and no paid infrastructure is created by
the project. If you choose to run a staging instance, treat each row as a
separate decision:

| Layer | What staging needs | Notes |
|-------|--------------------|-------|
| Documentation site | Static MkDocs hosting (GitHub Pages today) | Documentation only. It does not serve the FastAPI app. |
| Application | Container host that honours an injected `PORT` | Must support a long-running process, not only static/edge functions. Healthcheck against `/api/health`; route traffic on `/api/ready`. |
| Background worker | Same image, `celery -A med_research.web.tasks.analysis_tasks worker` | Async jobs stay `PENDING` without it. Scale separately from the web process. |
| Scheduler | Same image, `celery ... beat` | Only needed for the weekly digest. Run exactly one. |
| Redis | Managed or private Redis reachable from app and worker | Required for the queue, results, and the distributed rate limiter. App falls back to an in-memory limiter (fail-open) if Redis is down. Do not expose Redis to the internet. |
| Persistent data | Volume mounted at `/app/data` | Holds `biomedical.sqlite3`, `evidence_workspace.sqlite3`, and pipeline outputs. Losing it loses run history and the imported store. |
| Secrets | Platform secret store, injected at runtime | `API_KEY`, `AUTH_SESSION_SECRET`, broker URL, SMTP credentials. Never bake them into the image or commit `.env`. |
| Monitoring | Uptime check on `/api/health`, alert on `/api/ready` failures and worker queue depth | Liveness and readiness mean different things; alert on them separately. |
| TLS / proxy | Reverse proxy terminating TLS in front of the app | Keep `CORS_ORIGINS` on the public origin. If `AUTH_MODE=proxy`, set `AUTH_TRUSTED_PROXY_IPS` to the proxy addresses only. |
| Demo instance (optional) | `Dockerfile.demo` or the `demo` profile | Read-only by construction. Do not mount writable `./data` into the single-container image. |

Before promoting a staging build, run `make ci-local`, the browser tier, and
`python scripts/docker_smoke.py --demo` against the demo image, or
`python scripts/docker_smoke.py --dockerfile Dockerfile.demo --demo --no-build --image <tag>`
when the demo image was built separately. Use `--validate-diseases` when the
build-time curation gate itself is what you are verifying.

## Research-only policy

This platform is for **public biomedical knowledge and computational research**. Do not store or process patient-identifiable data (PHI). See [SECURITY.md](https://github.com/AdamEddahmouni/nosograph/blob/master/SECURITY.md) and [data licensing](legal/data-licenses.md).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Web container exits on start | Invalid runtime configuration (usually `DEBUG=false` without `API_KEY`) | The startup error lists every problem; fix all of them, or set `API_KEY` / `DEBUG=true` in `.env` |
| Web container exits with a `PORT` error | Injected or Compose `PORT` is not an integer in `1`–`65535` | Unset it or set a valid port; do not rely on a silent fallback |
| Healthcheck passes but the port is unreachable | Host publish and `PORT` disagree | Use the same `${PORT}` for publish, listen, and probe |
| Jobs stay `PENDING` | Worker not running | `docker compose --profile full up worker` |
| `429 Too Many Requests` | Rate limit hit | Raise `RATE_LIMIT_REQUESTS` or wait |
| `/api/ready` returns 503 | Redis/Celery unreachable | Check `redis` service and broker URLs |
