# Biomedical Model Audit

**Project:** NosoGraph (formerly med-research)  
**Date:** 2026-08-20  
**Auditor scope:** Disease modules, universal biomed store, pipeline contracts

## Executive summary

NosoGraph implements a **dual-layer biomedical model**: (1) per-disease JSON knowledge graphs with Python config overlays, and (2) a canonical SQLite universal biomedical store with ontology imports. The model is **sound for research prototyping** but requires honest tier labeling because ~99.8% of registry entries are Open Targets scaffolds, not clinically validated disease models.

## Disease module architecture

**Location:** `src/med_research/diseases/{id}/`

| Component | Maturity | Notes |
|-----------|----------|-------|
| `data/profile.json` | STABLE | Disease metadata, MONDO/EFO linkage where curated |
| `data/genes.json` | STABLE (L2+) | Gene lists with evidence fragments |
| `data/drugs.json` | STABLE (L2+) | Drug catalog, often ChEMBL IDs |
| `data/pathways.json` | STABLE (L2+) | Reactome/GO pathway associations |
| `data/relationships.json` | STABLE (L2+) | KG edges (gene–drug–pathway) |
| `config.py` | STABLE (L2+) | Symptoms, queries, CAR-T, safety, screening |

**Contract enforcement:** `Disease.validate()`, `disease validate --strict`, `populate_disease_configs.py --check --strict`

## Readiness tiers (L0–L3)

Implemented in `diseases/tier_model.py` and `pipeline/gene_expression/geo.py`.

| Tier | Population | Status |
|------|------------|--------|
| L0 | Scaffold missing KG files | PROTOTYPE |
| L1 | Partial KG/config | EXPERIMENTAL |
| L2 | Strict validation pass | BETA (research-ready pipeline inputs) |
| L3 | L2 + curated GEO consensus | BETA (expression module fully curated) |

**L3 curated set (23):** `sle`, `ra`, `ibd`, `ms`, `ss`, `ssc`, `t1d`, `ad`, plus Wave 3/4 oncology/metabolic slice (see `CURATED_CONSENSUS_DISEASES` in `geo.py`).

**Promoted L2 corpus:** ~45 diseases validated in `tests/test_disease_catalog_tier_promotion.py`.

## Coverage vs provenance

- **Coverage** (`diseases/coverage.py`): whether curated inputs exist for a module run — separate from live retrieval success.
- **Provenance** (`pipeline/provenance.py`): reproducibility fingerprints, source lists, schema version 1.0.

This separation is a **strength** for research integrity.

## Universal Biomedical Schema v1

**Location:** `src/med_research/biomed/`

| Feature | Maturity |
|---------|----------|
| SQLite store + migrations | BETA |
| MONDO/HPO/HPOA/GO/Reactome/Uberon imports | BETA |
| ClinVar + openFDA adapters | BETA |
| Legacy disease → canonical claims migration | BETA |
| HPO-aware condition comparison | BETA |
| DuckDB graph analytics | EXPERIMENTAL |
| `/api/v1` read-only endpoints | BETA |

## Pipeline modules

40+ analysis modules under `pipeline/` (repurposing, KG, expression, virtual screening, evidence workspace, etc.).

| Concern | Finding | Severity |
|---------|---------|----------|
| Default disease `sle` in several CLI modules | Legacy bias; coverage system mitigates at API layer | P2 |
| Scaffold modules runnable with warnings | Coverage reports `limited_coverage` | Expected |
| SLE signature reuse | Blocked for non-SLE via tests + geo consensus guards | PASS |

## Recommendations applied

1. Public docs state tier counts honestly (not conflating registry size with curation depth).
2. Architecture docs describe dual-layer model and tier semantics.
3. Source registry documents upstream ontologies and APIs.

## Deferred (P2/P3)

- Expand CI strict validation beyond original eight curated diseases.
- Neutralize remaining SLE-first CLI defaults.
- Phenopacket / FHIR export (PLANNED, not implemented).
