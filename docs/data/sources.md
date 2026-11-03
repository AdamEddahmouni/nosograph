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
| MONDO | Disease ontology | IDs, hierarchy, registered sync source | `STABLE` import · sync `EXPERIMENTAL` | CC-BY-4.0 |
| HPO | Phenotypes | Comparison, annotations | `STABLE` import | HPO-custom |
| HPOA | Phenotype associations | Symptom harvest, registered sync source | `STABLE` import · sync `EXPERIMENTAL` | HPO-custom |
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

Open Targets synchronization is an experimental vertical slice with a dry-run path. HPOA is registered in the same sync lifecycle for operator-supplied annotation files: there is no download automation, the artifact must be placed at `data/bulk/hpoa/*.tsv` (or passed explicitly), and version provenance comes from an explicit `VERSION` pin or a local artifact-mtime token rather than an invented upstream release. Source synchronization belongs in advanced workflows; it is not required for the first-time tutorial. MONDO is registered in the same lifecycle for operator-supplied OBO-JSON artifacts; see [MONDO synchronization](#mondo-synchronization) below.

## MONDO synchronization

`MondoSyncSource` runs the same DISCOVER → FETCH → VERIFY → NORMALIZE → DIFF → PROVENANCE lifecycle as the other sources against a local Mondo OBO-JSON artifact. There is no download automation: place the artifact at `data/bulk/mondo/*.json`, or pass `artifact_path=...`. With neither present the source falls back to the checked-in minimal fixture, so the offline test tier never touches the network.

```python
from pathlib import Path

from med_research.biomed.repository import BiomedicalRepository
from med_research.biomed.sync import SyncService

service = SyncService(
    BiomedicalRepository(Path("data/biomedical.sqlite3")),
    staging_root=Path("data/bulk/sync"),
)
report = service.run("mondo", dry_run=True, publish=False)  # dry run first
```

Version provenance:

- `meta.version` inside the artifact wins, because it is the only value that names a real MONDO release.
- When the artifact declares no `meta.version`, an explicit `VERSION` pin next to the artifact (or in `data/bulk/mondo/`) is used.
- When neither exists, discovery raises instead of inventing an upstream release number.

Verification reports a `sha256:` checksum for the artifact and for the version pin when one is staged. Pin enforcement is opt-in: construct the source with `expected_checksums=[...]` to reject an artifact whose checksum matches no pin. The canonical pin file for reproducible imports remains `data/biomed/pinned-artifacts.json`, used by `scripts/setup_biomed_imports.py`; this sync source does not silently relax that gate.

Provenance fields recorded per run: `source_id`, `resource_name`, `upstream_version`, `checksum`, `snapshot_id`, `manifest_fingerprint`, `retrieved_at`, `importer_name`, `importer_version`, and `stages_completed`.

Normalization stays single-sourced in `MondoAdapter`. The sync source adds an inspection summary to the bundle metadata — active and obsolete concept counts, obsolete concepts with no published replacement, published replacement targets that are absent from the artifact, and cross-reference counts by prefix. That summary is derived from the parsed records; it never adds an assertion.

### Limitations

- Cross-reference mappings are exactly the ones the artifact publishes. No mapping is inferred from label string similarity, and no obsolete concept is collapsed onto an unrelated active concept.
- Obsolete concepts remain in the bundle with `EntityRevision.obsolete=True` plus their published `replaced_by`/`consider` values. Consumers that resolve active concepts must filter on `obsolete` rather than assuming every entity is current.
- An obsolete concept whose published replacement target is missing from the artifact is reported, not repaired.
- MONDO sync is `EXPERIMENTAL`: there is no scheduling, retry, or incremental-diff publication, and `diff` reports record-count changes plus a checksum comparison rather than a term-level changelog.
- Discovery reads the artifact once per `(mtime, size)` pair; a very large full-size Mondo artifact is read at least once per process for version discovery plus once for parsing.

## Terms and provenance

Apache-2.0 applies to NosoGraph source code. Each upstream resource retains its own license and terms; read the [data licensing guide](../legal/data-licenses.md) before redistributing imported data. Provenance may include source identity, snapshot/version, import stages, and fingerprints where the current adapter supports them. See [data provenance](provenance.md).

## Continue

- [Evidence Explorer](../using/evidence-explorer.md) — inspect source-linked evidence.
- [Provenance](../concepts/provenance.md) — interpret snapshot and fingerprint context.
- [Source sync lifecycle](../architecture/source-sync-lifecycle.md) — advanced experimental sync details.
