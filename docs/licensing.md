# Licensing

## Project software

The `med-research` source code is released under the [MIT License](../LICENSE).

## Third-party data and APIs

The platform integrates public biomedical data and APIs. When using, redistributing, or citing derived work, comply with each provider's terms and attribution requirements.

| Source | Use in platform | License / terms |
|--------|-----------------|-----------------|
| [Mondo Disease Ontology](https://mondo.monarchinitiative.org/) | Disease identifiers, hierarchy, universal biomedical store | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| [Human Phenotype Ontology (HPO)](https://hpo.jax.org/) | Phenotype similarity, condition comparison | [Custom HPO license](https://hpo.jax.org/app/license) — attribution required |
| [Open Targets Platform](https://platform.opentargets.org/) | Disease–gene and disease–drug associations for KG curation and bulk scaffolding | [Open Targets data license](https://platform-docs.opentargets.org/licence) |
| [GWAS Catalog](https://www.ebi.ac.uk/gwas/) | Genetic association evidence | [EBI terms of use](https://www.ebi.ac.uk/data-protection/privacy-notice/embl-ebi-public-website) |
| [Reactome](https://reactome.org/) | Pathway annotations | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| [PubMed / NCBI Entrez](https://pubmed.ncbi.nlm.nih.gov/) | Literature mining, evidence gathering | [NCBI disclaimer and copyright](https://www.ncbi.nlm.nih.gov/home/about/policies/) — include `ENTREZ_EMAIL` |
| [ClinicalTrials.gov](https://clinicaltrials.gov/) | Trial tracking and workspace adapters | [CT.gov terms](https://clinicaltrials.gov/ct2/about-site/terms-conditions) |
| [DailyMed / openFDA](https://dailymed.nlm.nih.gov/) | Drug label evidence | Public domain / U.S. government works where applicable |
| [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) | Clinical variant-condition claims (live adapter) | [NCBI ClinVar data usage](https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/) — U.S. government works where applicable |
| [ChEMBL](https://www.ebi.ac.uk/chembl/) | Drug-target bioactivity (live connector) | [EMBL-EBI ChEMBL terms](https://www.ebi.ac.uk/chembl/) |
| [PubChem](https://pubchem.ncbi.nlm.nih.gov/) | Compound–gene bioactivity (experimental import adapter) | [NCBI PubChem policies](https://pubchem.ncbi.nlm.nih.gov/docs/programmatic-access) |
| [GTEx](https://gtexportal.org/) | Tissue expression (live connector) | [GTEx data release policy](https://gtexportal.org/home/downloads) |
| [UniProt](https://www.uniprot.org/) | Protein annotation (live connector) | [UniProt terms of use](https://www.uniprot.org/help/license) |
| [bioRxiv / medRxiv](https://www.biorxiv.org/) | Preprint evidence | Preprint licenses vary by article; metadata use only in aggregations |

## Curated disease JSON

Disease-specific knowledge graph files under `src/med_research/diseases/*/data/` are project contributions compiled from the sources above and manual curation. They inherit the project's MIT license for the **compilation and schema**, but underlying facts remain subject to source-provider terms.

## No clinical or patient data

This repository does not distribute protected health information (PHI). Do not commit patient records, clinical notes, or identifiable case data. See [SECURITY.md](../SECURITY.md).

## Questions

For licensing questions about the software, open a GitHub issue. For data-provider terms, consult the linked source documentation.
