---
title: Data sources
description: NosoGraph's source matrix, integration maturity, provenance expectations, and source-specific terms.
---

# Data sources

NosoGraph connects local records with upstream biomedical resources. This page is the authoritative source matrix: it describes each integration's role and current implementation state, not the scientific quality or clinical validity of the upstream resource.

Machine-readable registry: [`data/sources/registry.yaml`](https://github.com/AdamEddahmouni/nosograph/blob/master/data/sources/registry.yaml), updated 2026-08-20.

## Integration matrix

| Source | Domain | Used for | Integration state | License/terms |
|--------|--------|----------|-------------------|---------------|
| MONDO | Disease ontology | IDs, hierarchy | `STABLE` import | CC-BY-4.0 |
| HPO | Phenotypes | Comparison, annotations | `STABLE` import | HPO-custom |
| HPOA | Phenotype associations | Symptom harvest | `STABLE` import | HPO-custom |
| GO | Function/process | Pathways | `STABLE` import | CC-BY-4.0 |
| Reactome | Pathways | Pathways | `STABLE` import | CC-BY-4.0 |
| Uberon | Anatomy | Anatomy | `STABLE` import | CC-BY-4.0 |
| Open Targets | Target-disease | Knowledge-graph scaffold, connector, sync slice | `BETA` / sync `EXPERIMENTAL` | Open Targets data license |
| PubMed | Literature | Evidence Workspace | `STABLE` adapter | NCBI terms |
| ClinicalTrials.gov | Trials | Trials, Evidence Workspace | `STABLE` adapter | ClinicalTrials.gov terms |
| GWAS Catalog | Genetics | Evidence Workspace | `BETA` | EBI terms |
| openFDA | Labels | Evidence Workspace | `BETA` | US public domain / FDA |
| ClinVar | Variants | Biomedical import | `BETA` | NCBI ClinVar |
| ChEMBL | Bioactivity | Live connector | `BETA` | EBI ChEMBL |
| PubChem | Compounds | Live connector | `BETA` | NCBI PubChem |
| GTEx | Expression | Expression / live connector | `BETA` | GTEx policy |
| UniProt | Proteins | Live connector | `BETA` | UniProt terms |
| bioRxiv/medRxiv | Preprints | Evidence Workspace | `EXPERIMENTAL` | Per-preprint |

## How to interpret maturity

`STABLE`, `BETA`, and `EXPERIMENTAL` describe NosoGraph's integration maturity. They do not rank upstream scientific quality, source prestige, reproducibility, or clinical validity. Live, fixture-backed, and experimental behavior depends on the code path; CI is often fixture-backed, and connectors are not continuously updated feeds by default.

Open Targets synchronization is an experimental vertical slice with a dry-run path. Source synchronization belongs in advanced workflows; it is not required for the first-time tutorial.

## Terms and provenance

Apache-2.0 applies to NosoGraph source code. Each upstream resource retains its own license and terms; read the [data licensing guide](../legal/data-licenses.md) before redistributing imported data. Provenance may include source identity, snapshot/version, import stages, and fingerprints where the current adapter supports them. See [data provenance](provenance.md).

## Continue

- [Evidence Explorer](../using/evidence-explorer.md) — inspect source-linked evidence.
- [Provenance](../concepts/provenance.md) — interpret snapshot and fingerprint context.
- [Source sync lifecycle](../architecture/source-sync-lifecycle.md) — advanced experimental sync details.
