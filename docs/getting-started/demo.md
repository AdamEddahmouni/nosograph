---
title: Demo
description: The read-only public demo mode, how to run it locally, and the status of a hosted demo.
---

# Demo

A read-only **public demo mode** (`DEMO_MODE`) is implemented for the v0.3.0 development line (after v0.2.1). It exposes the
Condition Explorer, Evidence Explorer, snapshot/source metadata, and a
non-persisting Compare preview against a fixed fixture-built snapshot, with
all mutation, job, admin, and live-connector surfaces blocked server-side
(`403 demo_read_only`).

A **public hosted demo is not deployed**; hosting requires owner setup. Until
a hosted smoke test passes, there is no public URL to share.

## Run the demo locally (recommended)

The one-container profile needs no Redis or Celery:

```bash
docker build -f Dockerfile.demo -t nosograph-demo .
docker compose -f docker-compose.demo.yml up --build
# open http://localhost:8000
docker compose -f docker-compose.demo.yml down
```

The dashboard shows a `PUBLIC DEMO · FIXED RESEARCH SNAPSHOT` banner with the
snapshot date; the disease picker is limited to the snapshot's supported
diseases; Workspace, Jobs, admin, and live-connector controls are hidden and
their endpoints return `403`.

## Run the demo without Docker

```bash
# from the repository root, with the venv active
.venv/bin/python scripts/build_demo_snapshot.py --output /tmp/demo/biomedical.sqlite3
export DEMO_MODE=true
export DEMO_SNAPSHOT_PATH=/tmp/demo/biomedical.sqlite3
export DEMO_SNAPSHOT_MANIFEST=/tmp/demo/biomedical.manifest.json
export DEMO_SNAPSHOT_VERSION="$(python -c "import json;print(json.load(open('/tmp/demo/biomedical.manifest.json'))['snapshot_version'])")"
python -m med_research.cli serve --host 127.0.0.1 --port 8000
```

## Hosted demo (not yet deployed)

Deployment is documented in [deployment-demo](../deployment-demo.md): a
manual-only GitHub Actions workflow deploys the immutable demo image to
Heroku (Azure Container Apps as fallback), with cost monitoring and shutdown
procedures. The public URL stays unclaimed until a hosted smoke test passes.