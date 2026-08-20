# Disease Content Audit

**Date:** 2026-08-20  
**Registry size:** 10,407 disease module directories

## Summary

The disease registry is **large in count but shallow in curation depth**. Public messaging must distinguish:

1. **Registry modules** — MONDO-aligned slugs, mostly Open Targets bulk scaffolds  
2. **Pipeline-ready (L2)** — ~45 promoted + 18 legacy hand-curated modules  
3. **Expression-curated (L3)** — 23 modules with disease-specific GEO consensus (no SLE signature reuse)

## Original curated eight (CI gate)

These pass `disease validate --strict` in GitHub Actions:

| ID | Name (approx.) | Tier |
|----|----------------|------|
| `sle` | Systemic lupus erythematosus | L3 |
| `ra` | Rheumatoid arthritis | L3 |
| `ibd` | Inflammatory bowel disease | L3 |
| `ms` | Multiple sclerosis | L3 |
| `ss` | Sjögren syndrome | L3 |
| `ssc` | Systemic sclerosis | L3 |
| `t1d` | Type 1 diabetes | L3 |
| `ad` | Alzheimer's disease | L3 |

## Extended hand-curated set (docs/disease-curation.md)

Additional legacy curated IDs: `als`, `as`, `asthma`, `atopic_dermatitis`, `copd`, `gout`, `pd`, `psa`, `pso`, `t2d` (overlap with promoted corpus).

## Promoted L2+ modules (test gate)

`tests/test_disease_catalog_tier_promotion.py` validates ~45 indications including oncology (`nsclc`, `melanoma`, `colorectal_cancer`, …), rare metabolic (`gaucher_disease`, `fabry_disease`, …), psychiatric (`major_depressive_disorder`, `schizophrenia`, …), and cardiometabolic (`heart_failure`, `copd`, `t2d`, …).

## Scaffold corpus (~10,350 modules)

- Generated via `disease add`, `bulk-harvest`, Open Targets parquet pipeline
- Typically have KG JSON from Open Targets but **empty or placeholder** symptoms, safety, CAR-T until curated
- `disease validate --all --strict` **expected to fail** — not a merge gate
- HPO symptom harvest populated SYMPTOMS for ~3,824 scaffolds (partial automation, not L2)

## Content quality controls

| Control | Status |
|---------|--------|
| JSON schema validation | STABLE |
| Relationship integrity checks | STABLE |
| Neutral terminology tests (non-SLE) | STABLE |
| Expression consensus isolation | STABLE (L3 set) |
| Open Targets provenance in KG edges | BETA |

## Risk: misleading public claims

**Pre-audit README** implied 10,403+ modules are fully curated with CAR-T tiers and GTEx profiles. **Reality:** those features exist only for L2/L3 subsets.

## Remediation

- README and architecture docs use tier table above.
- ROADMAP clarifies curation expansion is contributor-driven, not pre-complete.
- Disease curation playbook (`docs/disease-curation.md`) remains authoritative for contributors.

## Maturity classification

| Content type | Classification |
|--------------|----------------|
| Original eight + L3 consensus | **BETA** (research hypotheses) |
| Promoted L2 corpus | **BETA** |
| HPO-harvest scaffolds | **EXPERIMENTAL** |
| Raw Open Targets scaffolds | **PROTOTYPE** |
