# Data Licenses

Third-party biomedical data integrated by NosoGraph. **Comply with each provider before redistributing derived datasets.**

| Source | Use in NosoGraph | License / terms | Attribution |
|--------|------------------|-----------------|-------------|
| [MONDO](https://mondo.monarchinitiative.org/) | Disease IDs, hierarchy, biomed store | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Cite MONDO release |
| [HPO](https://hpo.jax.org/) | Phenotypes, comparison | [HPO license](https://hpo.jax.org/app/license) | Required |
| [HPOA](https://hpo.jax.org/) | Phenotype-disease associations | HPO terms | Required |
| [Gene Ontology](https://geneontology.org/) | Process/function imports | [CC BY 4.0](https://geneontology.org/docs/go-citation-policy/) | GO citation policy |
| [Reactome](https://reactome.org/) | Pathways | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Reactome citation |
| [Uberon](https://uberon.github.io/) | Anatomy | CC BY 3.0 / 4.0 | Uberon citation |
| [Open Targets](https://platform.opentargets.org/) | KG scaffolds, associations | [OT data license](https://platform-docs.opentargets.org/licence) | Required |
| [GWAS Catalog](https://www.ebi.ac.uk/gwas/) | Genetic evidence | [EBI terms](https://www.ebi.ac.uk/data-protection/privacy-notice/embl-ebi-public-website) | EBI policy |
| [PubMed / NCBI](https://pubmed.ncbi.nlm.nih.gov/) | Literature | [NCBI policies](https://www.ncbi.nlm.nih.gov/home/about/policies/) | Set `ENTREZ_EMAIL` |
| [ClinicalTrials.gov](https://clinicaltrials.gov/) | Trials | [CT.gov terms](https://clinicaltrials.gov/ct2/about-site/terms-conditions) | Required |
| [openFDA / DailyMed](https://open.fda.gov/) | Drug labels | Public domain / US gov works | FDA attribution |
| [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) | Variants | [ClinVar usage](https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/) | NCBI policy |
| [ChEMBL](https://www.ebi.ac.uk/chembl/) | Bioactivity | [EBI ChEMBL terms](https://www.ebi.ac.uk/chembl/) | Required |
| [PubChem](https://pubchem.ncbi.nlm.nih.gov/) | Compounds | [PubChem access policy](https://pubchem.ncbi.nlm.nih.gov/docs/programmatic-access) | NCBI policy |
| [GTEx](https://gtexportal.org/) | Expression | [GTEx policy](https://gtexportal.org/home/downloads) | GTEx citation |
| [UniProt](https://www.uniprot.org/) | Proteins | [UniProt license](https://www.uniprot.org/help/license) | Required |
| [bioRxiv/medRxiv](https://www.biorxiv.org/) | Preprints | Per-article licenses | Metadata aggregation only |

## Disease JSON in repository

Files under `src/med_research/diseases/*/data/` are compilations. You may use them under Apache-2.0 for the compilation structure; verify upstream rights before republishing raw extractions.

## No PHI

NosoGraph does not distribute protected health information. Do not commit patient data.

## Registry

Machine-readable source list: [data/sources/registry.yaml](../../data/sources/registry.yaml).
