---
title: Current status
description: Current NosoGraph release, maturity, capabilities, and repository snapshot.
---

# Current status

**NosoGraph v2.4.0 · Public Alpha · 2026-08-22**

NosoGraph is research software under active development. It connects biomedical knowledge, evidence, and provenance for exploratory research—not medical advice, diagnosis, or clinical decision support.

## Repository snapshot

| Metric | Value |
|---|---:|
| Registry modules | 10,407 |
| Strict L2-validated modules | 88 |
| Reference modules | 6 |
| CI-validated modules | 8 |
| Analysis pipelines | 40+ |
| Offline tests in v2.4.0 suite | 2,391 |

Canonical source: [`public-status.yaml`](../generated/public-status.yaml). Registry breadth is not curation depth; most registry modules are scaffolds. Recompute corpus values with `nosograph disease corpus-status` before publishing a new release.

## Capability maturity

| Surface | State |
|---|---|
| `nosograph` CLI | Stable |
| FastAPI API + dashboard | Beta |
| Evidence Explorer | Public Alpha; shipped in v2.4.0 |
| Evidence Workspace | Beta |
| NosoGraph Compare | Experimental initial slice |
| Open Targets source synchronization | Experimental vertical slice |
| Public hosted demo | Planned; not deployed |
| Optional LLM enrichment | Experimental; not required |
| FHIR / OMOP / Phenopackets | Not implemented |

See the [release notes](releases.md), [roadmap](roadmap.md), and [Evidence Explorer guide](../using/evidence-explorer.md).
