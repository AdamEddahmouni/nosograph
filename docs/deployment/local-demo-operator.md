# Local read-only demo (operator)

**Status:** Local/self-host only. There is **no hosted public demo** in the repository. GitHub Pages serves MkDocs documentation, not the FastAPI dashboard.

## What you get

- `DEMO_MODE=true`: blocks writes, async jobs, LLM, gather, and related routes (see [Demo](../getting-started/demo.md)).
- A **fixture-backed** biomedical SQLite snapshot focused on the eight **ci_validated** disease modules, built from checked-in test fixtures (not live PubMed/Open Targets pulls).
- Optional Docker Compose **`demo`** profile: Redis + read-only web (`web-demo`).

## Build the snapshot

From a git checkout with `.venv` activated:

```bash
nosograph demo build
# default output: data/demo/biomedical.sqlite3 (+ .manifest.json)
```

Equivalent script entrypoint:

```bash
python scripts/build_demo_snapshot.py
```

## Run locally (CLI)

```bash
nosograph demo serve --host 127.0.0.1 --port 8000
```

This sets `DEMO_MODE=true` and `BIOMEDICAL_DB_PATH` to the demo snapshot, then starts the dashboard at `/`.

## Run with Docker Compose

```bash
cp .env.example .env
docker compose --profile demo run --rm pipeline demo build
docker compose --profile demo up web-demo --build
```

Open http://localhost:8000. The `web-demo` service does not start Celery workers; mutations remain blocked by `DEMO_MODE` even if misconfigured.

## Hosting

Deploying a **public** URL is an **owner-operated** decision (abuse budget, API key policy, snapshot refresh). Merging this tooling does not publish a demo. See [public hosted demo](public-demo.md) for design notes (repo-only; excluded from GitHub Pages).
