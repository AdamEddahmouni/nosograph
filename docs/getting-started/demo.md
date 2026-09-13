---
title: Demo
description: How to evaluate NosoGraph locally and the status of a public hosted demo.
---

# Demo

There is **no public hosted demo** in v0.2.1. GitHub Pages is MkDocs documentation. The FastAPI dashboard is local or self-hosted. Do not treat `https://adameddahmouni.github.io/nosograph/` as the application.

## Local evaluation

Use [Docker](docker.md) or [installation](install.md). Fixture-backed and snapshot paths are used in CI; live connectors may call public APIs if you enable them.

Label anything fixture-backed as a snapshot. Do not imply live coverage.

## `DEMO_MODE` (opt-in, default off)

`DEMO_MODE` is a **local/self-host guard** so a future public demo cannot accidentally expose writes, jobs, LLM, or live gather routes.

| Value | Effect |
|-------|--------|
| unset / `false` / `0` / `no` | Normal local/self-host (default). |
| `true` / `1` / `yes` / `on` | Read-only: mutations, `/api/jobs`, workspace writes, admin, cache, LLM, evidence gather, monitor, agent, and persisted Compare POSTs return `403 demo_read_only`. WebSockets close. |

This flag does **not** deploy an app, does not load a public dataset, and does not enable GitHub Pages as a demo. Keep it `false` unless you are operating an intentional read-only instance.

```bash
# .env — leave off for ordinary local use
DEMO_MODE=false
```

## Hosted demo (design)

See [public hosted demo](../deployment/public-demo.md) for the snapshot-first design. A `nosograph demo` command and a public URL are still deferred. Track hosting as a follow-up; do not ship an open proxy.
