---
description: How the SyncService imports, refreshes, and reports on biomedical sources, including dry-run validation before production sync.
---

# Biomedical Source Sync Lifecycle

Production sync is orchestrated by `med_research.biomed.sync.SyncService` and exposed via:

```bash
python -m med_research.cli biomed sync list
python -m med_research.cli biomed sync open_targets --dry-run
python -m med_research.cli biomed sync open_targets
```

## Stages

| Stage | Purpose |
|-------|---------|
| DISCOVER_VERSION | Read upstream release (bulk manifest, artifact meta, or fixture pin) |
| FETCH | Download or stage raw artifacts (skipped network on `--dry-run` when fixtures exist) |
| VERIFY | SHA-256 checksums on manifest and parquet/json artifacts |
| STORE_RAW | Persist raw artifacts under `data/bulk/sync/{source_id}/` |
| NORMALIZE | Transform raw data into `ImportBundle` via source adapter |
| VALIDATE | `ImportService` bundle validation (checksum, snapshot refs) |
| DIFF | Compare checksum/counts against previous active snapshot |
| PUBLISH | Atomic `ImportService.import_bundle(activate=True)` |
| UPDATE_PROVENANCE | Emit `SyncProvenance.manifest_fingerprint` |

## Vertical slice: Open Targets

- **Source:** `OpenTargetsSyncSource` (`src/med_research/biomed/sync/sources/opentargets.py`)
- **Normalize:** `OpenTargetsImportAdapter` maps EFO disease IDs → MONDO via active snapshot xrefs
- **Claims:** `ASSOCIATED_WITH_GENE`, `HAS_PHENOTYPE`, `TREATED_BY` with supporting `ClaimEvidence`
- **Offline tests:** `tests/fixtures/opentargets/25.03/` (build via `tests/fixtures/opentargets/build_fixtures.py`)

## Scheduled workflow (optional dry-run)

`.github/workflows/source-sync-dry-run.yml` runs `biomed sync open_targets --dry-run` on workflow_dispatch without secrets.
