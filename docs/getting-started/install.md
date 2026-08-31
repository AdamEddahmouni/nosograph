---
title: Installation
description: Run NosoGraph locally with the recommended Docker stack or an editable Python installation.
---

# Installation

This page is procedural: choose one local path, verify that it works, then continue to the [five-minute tutorial](tutorial.md). NosoGraph is distributed from source during the Public Alpha period; it is not published on PyPI.

## Prerequisites

- Git
- Docker Compose v2 for the recommended dashboard path, or Python 3.11/3.12 for the CLI path
- A local checkout with access to `.env.example`

## Recommended: Docker local stack

Use this path when you want the dashboard, API, worker, and Redis services together.

```bash
git clone https://github.com/AdamEddahmouni/nosograph.git
cd nosograph
cp .env.example .env
docker compose --profile full up --build
```

The `full` profile starts the `web`, `worker`, and `beat` services. When the stack is ready, open <http://localhost:8000>. The local dashboard is the success criterion for this path; the image build does not imply that a public hosted demo exists.

For profile details and production considerations, see [Docker](docker.md) and [self-hosted deployment](../deployment.md).

## Alternative: editable Python install

Use this path for CLI work or contributor development. It does not start Redis or the dashboard by itself.

```bash
git clone https://github.com/AdamEddahmouni/nosograph.git
cd nosograph
python -m venv .venv
# Windows (Git Bash): source .venv/Scripts/activate
# macOS/Linux: source .venv/bin/activate
pip install -e .
cp .env.example .env
nosograph --help
```

The success criterion is a working `nosograph --help` invocation. To validate the repository-backed SLE module, run:

```bash
nosograph disease validate sle --strict
```

The canonical product command is `nosograph`; the Python distribution remains `med-research` and the import path remains `med_research` for compatibility. `pip install nosograph` and `pip install med-research` from PyPI are not supported installation paths.

## Contributor setup

For the repository's locked development environment and local gate:

```bash
make venv-sync
make ci-local
```

Redis is needed for asynchronous dashboard jobs and the integration tier, not for pure offline CLI tests. Continue with [local development](../developers/local.md) or [testing](../developers/testing.md).

## Next step

Once one success criterion passes, follow the [five-minute tutorial](tutorial.md). It ends by routing researchers to evidence inspection and developers to the architecture/API path.
