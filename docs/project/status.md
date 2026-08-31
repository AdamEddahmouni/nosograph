---
title: Current status
description: Current NosoGraph release, maturity, repository metrics, and supported local research surfaces.
---

# Current status

**NosoGraph v0.2.1 · Public Alpha · 2026-08-22**

NosoGraph is open-source research software for connecting biomedical knowledge, evidence, and provenance. It is for research use only, not medical advice, diagnosis, or clinical decision support.

## Repository snapshot

| Metric | Value |
|---|---:|
| Registry modules | 10,407 |
| Strict L2-validated modules | 88 |
| Reference modules | 6 |
| CI-validated modules | 8 |
| Analysis pipelines | 40+ |
| Offline tests selected in v0.2.1 suite | 2,445 |

These values come from [`public-status.yaml`](../generated/public-status.yaml). Registry breadth is not curation depth; most registry modules are scaffolds. The pipeline count reflects varied legacy and current module packages, not a claim that every pipeline is production-grade. Test counts describe software validation coverage, not scientific validity.

## Capability maturity

| Surface | State | Use it for |
|---|---|---|
| `nosograph` CLI | `STABLE` | Task-oriented local exploration and validation. |
| FastAPI API + dashboard | `BETA` | Local research interfaces and documented API routes. |
| Evidence Explorer | `PUBLIC_ALPHA` | Read-only claim -> evidence -> provenance -> source inspection. |
| Evidence Workspace | `BETA` | Multi-source evidence, claims, and ranked research hypotheses. |
| NosoGraph Compare | `BETA` | Deterministic 2-5-condition comparison with explicit missingness and exports. |
| Open Targets synchronization | `EXPERIMENTAL` | A limited vertical sync slice and dry-run workflow. |
| Public hosted demo | `PLANNED` | Not deployed. |
| Optional LLM enrichment | `EXPERIMENTAL` | Not required for deterministic core workflows. |
| FHIR / OMOP / Phenopackets | `NOT_IMPLEMENTED` | No current interoperability implementation. |

Maturity describes NosoGraph implementation state. Source maturity is tracked separately in the [source matrix](../data/sources.md).

## Continue

- [What is NosoGraph?](../getting-started/what-is.md)
- [Installation](../getting-started/install.md)
- [Evidence Explorer](../using/evidence-explorer.md)
- [Compare](../using/compare.md)
- [Roadmap](roadmap.md) and [current releases](releases.md)
