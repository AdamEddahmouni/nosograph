# Data Model

## Disease module schema

Each disease lives at `src/med_research/diseases/{disease_id}/`:

```text
{disease_id}/
├── config.py              # Pipeline parameters (Python)
└── data/
    ├── profile.json       # Disease metadata
    ├── genes.json         # Gene catalog
    ├── drugs.json         # Drug catalog
    ├── pathways.json      # Pathway associations
    └── relationships.json # Knowledge graph edges
```

Optional: `adverse_events.json`, `scores.py`, expression overlays in config.

## Validation contract

`Disease.validate()` returns per-field status (`ok`, `missing`, `invalid`). Strict mode (`disease validate --strict`) gates L2 readiness.

Required config fields for L2:

- `SYMPTOMS`, `PUBMED_QUERIES`, `TRIAL_QUERY`, `GWAS_SEARCH_TERMS`
- `CAR_T_SCORES`, `DRUG_SAFETY_RISK` (when drugs exist)
- `SCREENING_PROFILE` (via populate script)

## Readiness tiers

| Tier | Criteria |
|------|----------|
| L0 | Missing core KG JSON files |
| L1 | Partial KG or config gaps |
| L2 | Strict validation pass |
| L3 | L2 + entry in `CURATED_CONSENSUS_DISEASES` (hand-curated GEO expression) |

Implementation: `diseases/tier_model.py`, `pipeline/gene_expression/geo.py`.

## Universal Biomedical Store

SQLite database (default `data/biomedical.sqlite3`):

| Entity | Description |
|--------|-------------|
| `entities` | Ontology terms (MONDO, HP, GO, …) |
| `claims` | Typed assertions (e.g., HAS_PHENOTYPE) |
| `evidence` | Supporting evidence records |
| `resource_snapshots` | Import provenance |

Import adapters: `biomed/imports/`.

## Evidence Workspace store

SQLite (default `data/evidence_workspace.sqlite3`):

- Saved dossiers, comparison history, alerts
- Session-scoped researcher auth

## Runtime vs versioned data

| Data | Location | Versioned |
|------|----------|-----------|
| Disease KG JSON | `src/med_research/diseases/` | Yes |
| Biomed DB | `data/biomedical.sqlite3` | No (local build) |
| Workspace DB | `data/evidence_workspace.sqlite3` | No |
| Batch reports | `data/reports/` | Partial |

## Corpus statistics (2026-08-20)

- **10,407** registry modules
- **8** CI-validated curated (original set)
- **~45** promoted L2 modules (test gate)
- **23** L3 expression-curated modules
