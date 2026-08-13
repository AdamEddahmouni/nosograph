# Disease Curation Playbook

This guide documents the repeatable workflow for keeping disease modules research-ready before adding new diseases or shipping major pipeline changes.

The registry contains **10,405 disease modules**: 18 hand-curated modules and 10,387 auto-generated OpenTargets knowledge-graph scaffolds. This playbook applies to the curated set; scaffolds must be curated (below) before they are treated as research-ready.

## Validate → coverage → refresh cycle

Run these commands for each curated disease (`sle`, `ra`, `ms`, `ss`, `ssc`, `t1d`, `ibd`):

```bash
# Preview external merges before applying
python -m med_research.cli disease refresh <id> --dry-run
python -m med_research.cli disease prune <id> --dry-run

# Config population audit (CAR-T tiers, safety tiers, screening profile)
python scripts/populate_disease_configs.py <id> --check --strict

# Schema and relationship integrity
python -m med_research.cli disease validate <id> --strict

# Module readiness (expression, screening, KG, etc.)
python -m med_research.cli disease coverage <id>
```

For all curated diseases at once:

```bash
python scripts/populate_disease_configs.py --all --check --strict
python -m med_research.cli disease validate sle --strict
```

Use `scaffold.py` audit/backups (or the web admin prune/restore endpoints) before destructive refreshes.

## Scaffolding and bulk harvest

New diseases are added as scaffolds, either individually from public knowledge bases or in bulk from the local Open Targets bulk parquet download:

```bash
# Single disease from public knowledge bases
python -m med_research.cli disease add <id> --name "<Name>" --efo EFO:xxxxxxx --dry-run

# Batch add from the curated candidate registry
python -m med_research.cli disease batch-add --category <category> --limit N --dry-run

# Bulk harvest from Open Targets bulk parquet files
python scripts/setup_opentargets_bulk.py --version 25.03
python -m med_research.cli disease bulk-harvest --all --workers 8 --dry-run
```

Scaffolds carry OpenTargets-derived genes/drugs/pathways/relationships plus generated config (PubMed queries, trial query, GWAS terms, placeholder CAR-T/safety/screening blocks). They are **starting points, not research-ready modules**: `disease validate <id> --strict` typically reports empty `SYMPTOMS` and `DRUG_SAFETY_RISK` until curated. The batch pipeline (`scripts/disease_batch_pipeline.py`) orchestrates setup → resolve → harvest → repair → symptoms → populate → validate and writes `data/reports/disease_batch_status.json` with per-module tiering.

## `populate_disease_configs.py` rubric

The populate script enforces curated metadata that cannot be inferred from raw KG JSON alone:

| Field | Requirement |
|-------|-------------|
| CAR-T tiers | Every disease drug with CAR-T relevance must have a tier (`tier1`–`tier4`) and rationale |
| Safety tiers | Adverse-event profiles must map to `tier1`–`tier4` safety bands |
| `SCREENING_PROFILE` | Must declare `strategy_id`, keywords, reference drugs, weights summing to 1.0, `curated_inputs`, `inferred_inputs`, and `limitations` |

Run with `--check --strict` in CI and before merging curation PRs. Fix failures in the disease `config.py` or data JSON, not by weakening the checker.

## Expression consensus curation (`geo.py`)

Each disease module needs its own consensus gene lists — never reuse SLE signatures for other diseases.

1. Add `*_CONSENSUS_GENES` dicts with `upregulated` / `downregulated` entries (`fold_change` + `confidence`).
2. Register the disease in `CURATED_CONSENSUS_DISEASES` and `DISEASE_CONSENSUS_GENES`.
3. Add optional tissue filters in `DISEASE_TISSUE_SPECIFIC_GENES` (e.g. MS `lesion`, SS `salivary`, T1D `islet`).
4. Add GEO search terms in `DISEASE_SEARCH_TERMS` for each tissue category.
5. Verify: `build_consensus_signature([{"accession": "TEST"}], disease="<id>")` returns `coverage: curated` with non-empty gene lists.
6. Regenerate expression outputs:

```bash
python -m med_research.cli expression --disease <id>
```

7. Run `python -m pytest tests/test_gene_expression.py tests/test_report_neutral_terminology.py -q`.

Ground gene selection in published transcriptomic studies and the disease KG (`genes.json` evidence fields like `ms_evidence`, `ssc_evidence`).

## `SCREENING_PROFILE` template

Each `src/med_research/diseases/<id>/config.py` must define:

```python
SCREENING_PROFILE = {
    "strategy_id": "<id>-screening-v1",
    "pathway_keywords": [...],  # pathway terms from KG
    "mechanism_keywords": [...],  # MOA terms for complementarity scoring
    "reference_drug_ids": [...],  # must exist in drugs.json
    "weights": {
        "binding_estimate": 0.25,
        "druglikeness": 0.15,
        "target_complementarity": 0.35,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },  # must sum to 1.0
    "source": "curated_<id>_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals and do not establish <disease> efficacy.",
    ],
}
```

**AutoDock Vina scope:** PDB target structures in `virtual_screening/targets/` are SLE-only in this release. Non-SLE diseases use property-based binding estimates. Reports note this distinction automatically.

## Research-ready checklist

Before marking a disease module research-ready:

- [ ] `disease validate <id> --strict` passes
- [ ] `disease coverage <id>` shows expression module **full/ready** (not `not_curated`)
- [ ] `populate_disease_configs.py <id> --check --strict` passes
- [ ] Expression consensus genes are disease-specific (no SLE gene reuse)
- [ ] `expression_correlations_<id>.json` regenerated after signature changes
- [ ] `SCREENING_PROFILE` reference drugs align with current `drugs.json`
- [ ] Gene `category` and disease-specific evidence fields are populated
- [ ] Relationship integrity: all `source`/`target` IDs exist in genes/drugs/pathways
- [ ] Neutral-terminology tests pass: `pytest tests/test_report_neutral_terminology.py -q`
- [ ] `make test-offline` remains green

## Deferred / larger scope

- **Live GEO matrix download:** `fetch_expression_data()` returns `not_implemented`; only pre-cached matrices and hand-curated consensus lists are supported today.
- **Multi-disease Vina targets:** Adding PDB structures for MS, RA, etc. is optional stretch work beyond property-based screening.
