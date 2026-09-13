---
title: Disease coverage
description: Read NosoGraph registry breadth, validation subsets, and curation-depth limits.
---

# Disease coverage

This page describes repository coverage metadata, not clinical coverage or scientific completeness. The current public snapshot is v0.2.1, released 2026-08-22; authoritative numbers live in [public-status.yaml](../generated/public-status.yaml).

**These counts measure different things. Do not substitute one for another.**

| Metric | Value | Definition | Source | Regeneration | Kind |
|---|---:|---|---|---|---|
| Discoverable modules (`registry_modules`) | 10,404 | `Disease.list_all()` — on-disk packages with `__init__.py`, excluding blocked slugs | Runtime discovery | `python scripts/refresh_public_status.py` | full-corpus |
| On-disk module directories | 10,406 | Directories with `__init__.py` and `config.py`, **including** two blocked GO-like slugs | Filesystem | same script | full-corpus |
| Harvest catalog entries | 10,391 | Unique `id` values in `disease_registry.json` | `src/med_research/diseases/disease_registry.json` | `python scripts/reconcile_harvest_registry.py` then refresh | full-corpus |
| Strict L2-validated | 88 | Strict-validation pass in an **n=500 alphabetical** `list_all()` sample | v0.2.1 sampled status report | `nosograph disease corpus-status --limit 500` (sample) or full-corpus `--tier L2 --strict` (expensive, not the public figure) | sample |
| L3 expression-curated (public) | 2 | Consensus members that fall inside that same n=500 window (`ad`, `acute_myeloid_leukemia`) | same sample | same | sample |
| L3 consensus membership | 23 | `CURATED_CONSENSUS_DISEASES`; `compute_tier()` assigns L3 to every member | `pipeline/gene_expression/geo.py` | refresh script (set size) | full-corpus |
| Reference | 6 | `REFERENCE_DISEASES` | `diseases/identifiers.py` | code constant | full-corpus |
| CI-validated | 8 | `CI_VALIDATED_DISEASES`; hosted CI runs `disease validate --strict` on each | `identifiers.py` + `.github/workflows/test.yml` | code constant | full-corpus |
| Registered pipeline adapters | 25 | `pipeline.registry.list_modules()` | adapter catalog | refresh script | full-corpus |

The historical public figure **10,407** was discoverable (10,404) plus the three-id blocklist (`positive_regulation_of_ovulation`, `sensory_perception_of_sound`, and the `zz_scaffold_test` fixture that is not a committed directory). It is not a live counter.

## Harvest catalog vs discovery

`disease_registry.json` is the Open Targets **harvest catalog** used for scaffolding and Mondo/EFO indexes. It is not `Disease.list_all()`. Curated short-slug packages (`sle`, `ra`, …) existed on disk before harvest and were skipped by `batch_scaffold` (already-exists). Reconcile them with:

```bash
python scripts/reconcile_harvest_registry.py          # admit missing disease-like modules
python scripts/reconcile_harvest_registry.py --check   # CI drift gate
```

**Intentional harvest exclusions:** blocked slugs and GO-like / `response_to_*` / `trait_in_response_to_*` directories that remain on disk historically. They must not be hand-appended to the catalog. CI-validated and reference slugs **must** be present. The 13 discoverable GO/response dirs are classified A–E in `harvest_registry.ON_DISK_GO_RESPONSE_EXCLUSIONS` (none are category C; none were deleted). New GO-like scaffolds are refused. See [registry](../concepts/registry.md).

## L2 / L3 (do not collapse)

- **L2=88** is an n=500 sample. It is not “88 of 88 of the whole registry.”
- **L3=2** is that sample intersecting consensus membership. The consensus set is **23**. `compute_tier()` short-circuits consensus members to L3; it does **not** require L2 ∩ consensus.
- Full-corpus L2-strict is **not** the public metric. Regenerating it is expensive (`nosograph disease validate-batch --tier L2 --strict`).

## Pipelines

**25 registered adapters** (`list_modules()`). Additional packages exist under `pipeline/` that are not in that catalog (`lead_opt`, `matching_engine`, `pharmacogenomics`, `bioinformatics` engine package, and others). The retired slogan “40+ pipelines” mixed those packages with adapters.

## Commands

```bash
python scripts/refresh_public_status.py
python scripts/check_public_metadata.py
python scripts/check_registry_harvest.py
nosograph disease corpus-status
nosograph disease validate-batch --tier ci_validated --strict
```

Do not use `disease validate --all --strict` as a green merge gate: the 10k scaffolds are expected to fail. Hosted CI validates the eight CI-validated ids plus the reference batch.

Do not interpret an unrecorded module field as a biological negative finding. Use [curation tiers](../concepts/curation-tiers.md) for the readiness model and [Sources](sources.md) for upstream integration context.
