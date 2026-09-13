---
title: Current status
description: Current NosoGraph release, maturity, repository metrics, and supported local research surfaces.
---

# Current status

**NosoGraph v0.2.1 · Public Alpha · 2026-08-22**

NosoGraph is open-source research software for connecting biomedical knowledge, evidence, and provenance. It is for research use only, not medical advice, diagnosis, or clinical decision support. Live documentation is whatever SHA GitHub Pages currently serves from `master`; **GitHub Pages is documentation, not the FastAPI app**. The dashboard is local or self-hosted. There is **no hosted public demo**. Community/patient posting is not implemented.

## Repository snapshot

| Metric | Value | Kind |
|---|---:|---|
| Discoverable modules | 10,404 | full-corpus (`Disease.list_all()`) |
| On-disk module directories | 10,406 | full-corpus (includes 2 blocked slugs) |
| Harvest catalog entries | 10,391 | full-corpus (`disease_registry.json`) |
| Strict L2-validated modules | 88 | **n=500 sample** |
| L3 expression-curated (sample) | 2 | **n=500 sample** (`ad`, `acute_myeloid_leukemia`) |
| L3 consensus membership | 23 | full-corpus (`CURATED_CONSENSUS_DISEASES`) |
| Reference modules | 6 | full-corpus |
| CI-validated modules | 8 | full-corpus; hosted CI `--strict` |
| Registered pipeline adapters | 25 | full-corpus (`list_modules()`) |
| Offline tests selected in v0.2.1 suite | 2,445 | snapshot (suite has grown; not a live collect-gate) |

Authoritative file: [`public-status.yaml`](../generated/public-status.yaml). Regeneration: `python scripts/refresh_public_status.py`. Harvest drift: `python scripts/check_registry_harvest.py`. Definitions: [coverage](../data/coverage.md).

Registry breadth is not curation depth. L2=88 is not “88 of 88 of the whole registry.” The retired “40+ pipelines” slogan mixed unregistered packages with adapters.

## Capability maturity

| Surface | State | Use it for |
|---|---|---|
| `nosograph` CLI | `STABLE` | Task-oriented local exploration and validation. |
| FastAPI API + dashboard | `BETA` | Local / self-hosted research interfaces. **Not** on GitHub Pages. |
| Evidence Explorer | `PUBLIC_ALPHA` | Read-only claim → evidence → provenance → source inspection (needs imported store). |
| Evidence Workspace | `BETA` | Multi-source evidence, claims, and ranked research hypotheses. |
| NosoGraph Compare | `BETA` | Deterministic 2–5-condition comparison with explicit missingness and exports. |
| Literature mining | implemented | Adapter + PubMed/Europe PMC connectors; not a separate “intelligence product.” |
| Open Targets synchronization | `EXPERIMENTAL` | A limited vertical sync slice and dry-run workflow. |
| `DEMO_MODE` | implemented, default off | Local opt-in write/job block. **Not deployed.** |
| Public hosted demo | `PLANNED` | Not deployed. No public app URL. |
| Optional LLM enrichment | `EXPERIMENTAL` | Not required for deterministic core workflows. |
| FHIR / OMOP / Phenopackets | `NOT_IMPLEMENTED` | No current interoperability implementation. |
| PyPI package | `NOT_IMPLEMENTED` | Install from source. |

Maturity describes NosoGraph implementation state. Source maturity is tracked separately in the [source matrix](../data/sources.md).

## Continue

- [What is NosoGraph?](../getting-started/what-is.md)
- [Installation](../getting-started/install.md)
- [Evidence Explorer](../using/evidence-explorer.md)
- [Compare](../using/compare.md)
- [Roadmap](roadmap.md) and [current releases](releases.md)
