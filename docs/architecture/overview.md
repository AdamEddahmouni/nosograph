---
title: Architecture overview
description: A repository-aligned view of NosoGraph's sources, domain stores, evidence services, and local interfaces.
---

# Architecture overview

NosoGraph is a Python research platform whose local runtime connects source data to structured disease and biomedical records, evidence-aware services, and user-facing interfaces. This page provides the developer mental model; the [API reference](../api-reference.md) and [data model](data-model.md) provide the operational details.

> **Research scope.** The platform exposes computational research artifacts. It is not a diagnostic system or clinical decision-support system.

## Layered model

```text
upstream sources and local artifacts
        ↓
disease modules + universal biomedical store
        ↓
typed claims + evidence + provenance
        ↓
pipeline and analysis services
        ↓
CLI + FastAPI/API + dashboard + asynchronous workers
```

The layers are repository components, not a promise that every source or pipeline has the same maturity.

## Major components

| Layer | Repository surface | Role | Maturity |
|---|---|---|---|
| Sources | `data/sources/`, import adapters, local artifacts | Acquire or stage upstream records and snapshots. | Per-source; see [source matrix](../data/sources.md). |
| Disease registry | `src/med_research/diseases/` | Disease-specific JSON/config modules and readiness validation. | Mixed; registry breadth is not curation depth. |
| Biomedical store | `src/med_research/biomed/` and local SQLite | Ontology entities, typed claims, evidence links, and resource snapshots. | Beta. |
| Evidence services | `src/med_research/pipeline/` and Evidence Workspace | Gather records, normalize evidence, build research artifacts, and preserve provenance. | Mixed; Workspace is Beta and optional LLM enrichment is Experimental. |
| Interfaces | `src/med_research/cli.py`, `src/med_research/web/` | CLI, versioned API slices, dashboard, and async job surface. | CLI Stable; API/dashboard Beta. |

## Typical data flow

1. A user selects a disease or condition through the CLI, dashboard, or API.
2. The relevant disease module or active biomedical snapshot is loaded.
3. Services normalize records into typed claims and attach evidence/source context where supported.
4. Provenance records source, retrieval/import context, and stable fingerprints where available.
5. The CLI, API, dashboard, or Workspace renders a research artifact with explicit warnings and missingness.

## Run and validate locally

For the dashboard/API path, use the [installation](../getting-started/install.md) or [self-hosted deployment](../deployment.md) guide. The canonical server command is:

```bash
python -m med_research.cli serve --host 127.0.0.1 --port 8000
```

For a focused repository validation path:

```bash
nosograph disease validate sle --strict
make ci-local
```

Redis is required for asynchronous jobs and integration tests, not for the offline CLI validation command.

## Extension points

- Add or revise disease modules under the disease curation workflow.
- Add a source adapter with source-specific terms, tests, and honest maturity labels.
- Extend typed biomedical services or API routers while preserving schema and provenance contracts.
- Improve docs, fixtures, and browser tests for user-facing workflows.

See [local development](../developers/local.md), [testing](../developers/testing.md), [code contributions](../contributing/code.md), [disease curation](../contributing/curation.md), and [source contributions](../contributing/sources.md).
