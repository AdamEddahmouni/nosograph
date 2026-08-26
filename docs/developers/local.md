---
title: Local development
description: Set up the NosoGraph repository, run local services, and validate changes before contribution.
---

# Local development

Use this page after reading the [architecture overview](../architecture/overview.md). It covers the repository setup and validation boundary; use the [API reference](../api-reference.md) for endpoint details.

## Prerequisites

- Python 3.11 or 3.12
- The repository virtual environment at `.venv`
- Redis for async dashboard jobs and integration tests
- Chromium installed for browser tests

The repository's environment instructions use `.venv` and the lock files. For a new checkout, use the contributor setup before running the local gate.

## Prepare the environment

```bash
make venv-sync
set -a && . ./.env && set +a
```

Create `.env` from `.env.example` first. The server reads configuration from the environment; sourcing the file is required before serving. On Windows, use the equivalent environment-loading command for your shell.

## Run the local interfaces

Start the dashboard/API:

```bash
python -m med_research.cli serve --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/>. The API documentation is available at `/api/docs` when `DEBUG=true` or `OPENAPI_ENABLED` enables it. Redis and a Celery worker are required for asynchronous Workspace jobs; the CLI and static docs do not depend on them.

## Validate changes

Focused repository validation:

```bash
nosograph --help
nosograph disease validate sle --strict
make ci-local
```

Documentation validation:

```bash
.venv/Scripts/python.exe -m mkdocs build --strict
```

On macOS/Linux, replace `.venv/Scripts/python.exe` with `.venv/bin/python`.

## Continue

- [Testing](testing.md) for offline, integration, and browser tiers.
- [API reference](../api-reference.md) for current routers and examples.
- [Code contributions](../contributing/code.md) for the pull-request path.
