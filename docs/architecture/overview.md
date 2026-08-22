# NosoGraph Architecture Overview

**Status:** BETA (research platform)  
**Package import path:** `med_research` (compatibility alias — see branding policy)

## What NosoGraph is

NosoGraph is open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources. The Python platform combines disease-specific knowledge graphs, a universal biomedical ontology store, evidence gathering pipelines, and a FastAPI web dashboard for exploratory research.

> **Research use only.** Outputs are computational hypotheses, not medical advice.

## System context

```text
┌─────────────────────────────────────────────────────────────────┐
│                     NosoGraph Platform                          │
├──────────────┬──────────────────────┬───────────────────────────┤
│  CLI         │  FastAPI Web API     │  Celery Workers           │
│  med-research│  + Dashboard (JS)    │  (async analysis jobs)    │
├──────────────┴──────────────────────┴───────────────────────────┤
│  Pipeline modules (40+): KG, repurposing, expression, screening,│
│  evidence workspace, virtual screening, clinical trials, …      │
├────────────────────────────┬────────────────────────────────────┤
│  Disease modules (10k+)    │  Universal Biomedical Store (SQLite)│
│  JSON KG + config.py       │  MONDO/HPO/GO/Reactome/… imports   │
└────────────────────────────┴────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
   External public APIs              Local parquet / fixture imports
   (PubMed, CT.gov, Open Targets, …)
```

## Major components

| Component | Path | Maturity |
|-----------|------|----------|
| Unified CLI | `src/med_research/cli.py` | STABLE |
| Disease registry | `src/med_research/diseases/` | BETA |
| Pipeline engine | `src/med_research/pipeline/` | BETA |
| Evidence Workspace | `src/med_research/pipeline/evidence_workspace/` | BETA |
| Universal biomed | `src/med_research/biomed/` | BETA |
| Web API + dashboard | `src/med_research/web/` | BETA |
| Async tasks | `src/med_research/web/tasks/` | BETA |

## Data flow (typical analysis)

1. User selects `disease_id` via CLI or dashboard.
2. `Disease` loads JSON KG + config; `coverage` checks curated inputs.
3. Pipeline module executes with disease context; optional live API fetches.
4. `build_provenance()` attaches fingerprint + source metadata.
5. Results returned as JSON/HTML or stored in workspace SQLite history.

## Tier model (public honesty)

See [data-model.md](data-model.md). **Registry count ≠ curation depth.**

## Deployment topology

- **Minimal:** Python venv + CLI (no Redis)
- **Dashboard:** FastAPI + Redis + Celery worker
- **Docker:** `docker-compose.yml` (API, worker, Redis)

## Related documents

- [data-model.md](data-model.md)
- [evidence-model.md](evidence-model.md)
- [provenance.md](provenance.md)
- [ontology-policy.md](ontology-policy.md)
- [commercialization-boundaries.md](commercialization-boundaries.md)

## Branding compatibility

| Surface | Name |
|---------|------|
| Public product | **NosoGraph** |
| Python package | `med_research` (KEEP_FOR_COMPATIBILITY) |
| CLI command | `med-research` (KEEP_FOR_COMPATIBILITY) |

Future major version may introduce `nosograph` package alias.
