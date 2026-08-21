# Biomedical Source Matrix

Machine-readable registry: `data/sources/registry.yaml`. Sync lifecycle: `docs/architecture/source-sync-lifecycle.md`.

| Source | Domain | Adapter | Access | Version | License | Cache | Transforms | Provenance | Tests |
|--------|--------|---------|--------|---------|---------|-------|------------|------------|-------|
| mondo | disease ontology | `MondoAdapter` | local OBO-JSON | meta.version | CC-BY-4.0 | snapshot checksum | entities, IS_A, xrefs | ResourceSnapshot | `test_mondo_adapter.py` |
| hp / hpo | phenotype ontology | `HpoOntologyAdapter` | local OBO-JSON | meta.version | HPO-custom | snapshot checksum | phenotype hierarchy | ResourceSnapshot | `test_hpo_adapter.py` |
| hpoa | disease-phenotype | `HpoAnnotationAdapter` | local TSV | operator pin | HPO-custom | snapshot checksum | HAS_PHENOTYPE + evidence | ClaimEvidence | `test_hpoa_adapter.py` |
| go | gene function | `GOImportAdapter` | local JSON | meta.version | CC-BY-4.0 | snapshot checksum | GO terms | ResourceSnapshot | `test_go_adapter.py` |
| reactome | pathways | `ReactomeImportAdapter` | local JSON | release tag | CC-BY-4.0 | snapshot checksum | INVOLVES_PATHWAY | ClaimEvidence | `test_reactome_adapter.py` |
| uberon | anatomy | `UberonImportAdapter` | local OBO-JSON | meta.version | CC-BY-4.0 | snapshot checksum | anatomy entities | ResourceSnapshot | `test_uberon_adapter.py` |
| clinvar | variants | `ClinVarImportAdapter` | local JSON | release date | NCBI-ClinVar | snapshot checksum | gene associations | ClaimEvidence | `test_clinvar_openfda_cli.py` |
| openfda | drug labels | `OpenFDAImportAdapter` | local JSON | operator pin | US-public-domain | snapshot checksum | TREATED_BY | ClaimEvidence | `test_clinvar_openfda_cli.py` |
| **open_targets** | target-disease | `OpenTargetsSyncSource` + `OpenTargetsImportAdapter` | FTP parquet / fixtures | bulk manifest.version | Open-Targets-data | parquet checksums | gene/phenotype/drug claims | SyncProvenance | `test_opentargets_sync.py` |
| pubmed | literature | evidence_workspace sources | Entrez API | live timestamp | NCBI-terms | pipeline cache | EvidenceRecord | build_provenance() | `test_evidence_gatherer.py` |
| clinicaltrials_gov | trials | external API | CT.gov v2 | live | CT.gov-terms | pipeline cache | trial records | build_provenance() | `test_pipeline_contracts.py` |
| chembl / pubchem | compounds | import/live adapters | JSON or API | release | EBI/NCBI | snapshot/live | interventions | ResourceSnapshot | `test_live_api_adapters.py` |
| legacy modules | disease KG | `LegacyMigrationAdapter` | repo JSON | git commit | Apache-2.0 | legacy snapshot | relationship claims | parity report | `test_adapter.py` |

**Vertical slice:** Open Targets (`biomed sync open_targets`) — end-to-end versioning, checksum verification, diff, provenance fingerprint, deterministic normalize.
