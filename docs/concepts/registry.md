---
description: What the NosoGraph disease registry contains — including auto-generated scaffolds — and why listing is not validation.
---

# Disease registry

The registry is **three surfaces**, not one number:

| Surface | What it is |
|---------|------------|
| Discoverable modules | `Disease.list_all()` — runnable on-disk packages |
| On-disk directories | Same tree including blocked GO-like slugs |
| Harvest catalog | `disease_registry.json` — Open Targets harvest/scaffold catalog |

**Listing is not validation.** Registry breadth is not curation depth. Use `nosograph disease corpus-status`, [coverage](../data/coverage.md), and [public-status.yaml](../generated/public-status.yaml).

## Why CI-validated modules used to be missing from harvest JSON

Harvest merge and `batch_scaffold` skip directories that already exist. The eight CI-validated packages (`sle`, `ra`, `ms`, `ss`, `ssc`, `t1d`, `ibd`, `ad`) and several reference/playbook short slugs were created as first-class modules **before** the OT harvest, so they never entered the JSON catalog. Identifier Mondo/EFO indexes are built from that JSON.

The process fix is `python scripts/reconcile_harvest_registry.py`, gated by `python scripts/check_registry_harvest.py`. Do not hand-append rows.

## Intentional exclusions

Blocked slugs (`positive_regulation_of_ovulation`, `sensory_perception_of_sound`, `zz_scaffold_test`) and GO-like / `response_to_*` / `trait_in_response_to_*` directories that remain on disk are **not** harvest diseases. Discovery already excludes the blocklist; the GO-like dirs can still appear in `list_all()` until separately purged.
