# Data sources

Machine-readable registry: [`data/sources/registry.yaml`](https://github.com/AdamEddahmouni/nosograph/blob/master/data/sources/registry.yaml) (updated 2026-08-20).

| Source | Domain | Used for | Integration state | License/terms |
|--------|--------|----------|-------------------|---------------|
| MONDO | Disease ontology | IDs, hierarchy | STABLE import | CC-BY-4.0 |
| HPO | Phenotypes | Comparison, annotations | STABLE import | HPO-custom |
| HPOA | Phenotype associations | Symptom harvest | STABLE import | HPO-custom |
| GO | Function/process | Pathways | STABLE import | CC-BY-4.0 |
| Reactome | Pathways | Pathways | STABLE import | CC-BY-4.0 |
| Uberon | Anatomy | Anatomy | STABLE import | CC-BY-4.0 |
| Open Targets | Target-disease | KG scaffold, live connector, sync slice | BETA / EXPERIMENTAL sync | Open Targets data license |
| PubMed | Literature | Evidence workspace | STABLE adapter | NCBI terms |
| ClinicalTrials.gov | Trials | Trials, workspace | STABLE adapter | CT.gov terms |
| GWAS Catalog | Genetics | Workspace | BETA | EBI terms |
| openFDA | Labels | Workspace | BETA | US public domain / FDA |
| ClinVar | Variants | Biomed import | BETA | NCBI ClinVar |
| ChEMBL | Bioactivity | Live connector | BETA | EBI ChEMBL |
| PubChem | Compounds | Live connector | BETA | NCBI PubChem |
| GTEx | Expression | Expression / live | BETA | GTEx policy |
| UniProt | Proteins | Live connector | BETA | UniProt terms |
| bioRxiv/medRxiv | Preprints | Workspace | EXPERIMENTAL | Per-preprint |

LIVE vs fixture-backed vs experimental depends on the code path (CI often fixture-backed). Do not assume every source is a continuously updated live feed.

Licenses: [data-licenses.md](../legal/data-licenses.md).
