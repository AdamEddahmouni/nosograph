---
description: Why NosoGraph builds on standard biomedical ontologies — MONDO, HPO, GO, Reactome, Uberon — and how ontology snapshots are pinned for reproducibility.
---

# Ontology Policy

## Principles

1. **Prefer standard ontologies** over ad-hoc identifiers (MONDO for diseases, HPO for phenotypes, GO/Reactome for biology, Uberon for anatomy).
2. **Never merge ontologies silently** — imports create versioned snapshots in the biomed store.
3. **Preserve source CURIEs** in disease profiles and claims.
4. **Document upstream licenses** in `docs/legal/data-licenses.md`.

## Supported ontologies (import adapters)

| Ontology | Use | Import module |
|----------|-----|---------------|
| MONDO | Disease identifiers | `biomed/imports/mondo` |
| HPO | Phenotypes | `biomed/imports/hpo` |
| HPOA | Phenotype associations | `biomed/imports/hpoa` |
| GO | Biological processes | `biomed/imports/go` |
| Reactome | Pathways | `biomed/imports/reactome` |
| Uberon | Anatomy | `biomed/imports/uberon` |
| ClinVar | Variants | `biomed/imports/clinvar` |
| openFDA | Drug labels | `biomed/imports/openfda` |

## Disease module identifiers

- Scaffold modules map to MONDO/EFO via Open Targets bulk harvest
- Curated modules include `kg_node_id` and EFO/MONDO references in `profile.json`
- Slug (`disease_id`) is the stable internal key — not always equal to MONDO label

## Interoperability status

| Standard | Status |
|----------|--------|
| MONDO CURIEs | STABLE |
| HPO term IDs | STABLE |
| FHIR Condition export | NOT_IMPLEMENTED |
| OMOP concept mapping | NOT_IMPLEMENTED |
| Phenopackets | NOT_IMPLEMENTED |

## Curation rules

- Do not invent ontology IDs; use resolver scripts or Open Targets EFO mappings
- When ontology term is unavailable, document limitation in `SCREENING_PROFILE.limitations`
- Cross-disease comparison uses HPO-aware logic in `biomed/comparison/`

## Update policy

Ontology snapshots are refreshed via `scripts/setup_biomed_imports.py`. Pin snapshot dates in import reports for reproducibility.
