---
title: Demo
description: How to evaluate NosoGraph locally and the status of a public hosted demo.
---

# Demo

There is **no public hosted demo** in v0.2.1. GitHub Pages is MkDocs documentation. The FastAPI dashboard is local or self-hosted. Do not treat `https://adameddahmouni.github.io/nosograph/` as the application.

## Local evaluation

Use [Docker](docker.md) or [installation](install.md). Fixture-backed and snapshot paths are used in CI; live connectors may call public APIs if you enable them.

Label anything fixture-backed as a snapshot. Do not imply live coverage.

## Quick start (read-only demo)

Build the small **ci_validated-focused** fixture snapshot, then serve with `DEMO_MODE` enabled:

```bash
nosograph demo build
nosograph demo serve --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/. This is a **local** read-only instance, not a product hosted by the project.

With Docker Compose, use the **`demo`** profile (see [Docker](docker.md#read-only-demo-profile)).

Operator details: [local demo operator notes](../deployment/local-demo-operator.md) (repository copy; not a claim of a public URL).

## `DEMO_MODE` (opt-in, default off)

`DEMO_MODE` is a **local/self-host guard** so a future public demo cannot accidentally expose writes, jobs, LLM, or live gather routes.

| Value | Effect |
|-------|--------|
| unset / `false` / `0` / `no` | Normal local/self-host (default). |
| `true` / `1` / `yes` / `on` | Read-only: mutations, `/api/jobs`, workspace writes, admin, cache, LLM, evidence gather, monitor, agent, and persisted Compare POSTs return `403 demo_read_only`. WebSockets close. |

This flag does **not** deploy an app, does not load a public dataset by itself, and does not enable GitHub Pages as a demo. Pair `DEMO_MODE=true` with `BIOMEDICAL_DB_PATH` pointing at a built demo snapshot (or use `nosograph demo serve`).

```bash
# .env — leave off for ordinary local use
DEMO_MODE=false
BIOMEDICAL_DB_PATH=data/biomedical.sqlite3
```

## Hosted demo (design only)

See [public hosted demo](../deployment/public-demo.md) for snapshot-first **design** notes. A public URL requires explicit operator deploy and is **not** offered by merging code alone. Do not ship an open proxy.
