---
title: Compare conditions
description: Compare two to five conditions with deterministic outputs, explicit missingness, evidence drill-down, and reproducible exports.
---

# NosoGraph Compare

Compare V2 is a Beta, deterministic research workflow for comparing **two through five unique conditions** across evidence-aware dimensions. It represents recorded differences and missing data; it does not diagnose, rank clinical likelihood, recommend treatment, or produce a universal disease-similarity score.

> **Interpretation boundary.** A difference in recorded evidence is not by itself evidence that one condition is more likely, more severe, or clinically preferable. Compare is for computational research review, not medical advice or clinical decision support.

## Request a comparison

The canonical endpoint is `POST /api/v1/nosograph/comparisons`:

```json
{
  "condition_curies": ["MONDO:0007915", "MONDO:0008390"],
  "dimensions": ["phenotype", "gene", "pathway", "treatment", "evidence_coverage"]
}
```

`dimensions` is optional. When omitted, the engine selects `phenotype`, `gene`, `pathway`, `treatment`, and `evidence_coverage` in canonical order. Conditions are normalized, deduplicated, and sorted. The request must resolve to two through five unique entities of type `CONDITION`; invalid cardinality or unresolved conditions return HTTP 422.

## Interpret the state matrix

Each entity-dimension cell has one of these states:

| State | Meaning |
|---|---|
| `PRESENT` | At least one current positive assertion exists. |
| `KNOWN_ABSENT` | A current assertion explicitly has `qualifiers.negated=true`, and no positive assertion exists. |
| `NOT_RECORDED` | Neither a current positive nor a current negated assertion exists. |

`KNOWN_ABSENT` and `NOT_RECORDED` are not interchangeable. Empty data never implies `KNOWN_ABSENT`. If positive and negated assertions coexist, `PRESENT` takes precedence and the response includes a `CONFLICTING_ASSERTIONS` warning while preserving both claim directions for inspection.

The response also includes shared-by-all, shared-by-subset, unique-by-condition, coverage, source-resource and active-snapshot counts, warnings, a claim-set fingerprint, and the persisted `nosograph_compare_v2` run ID. A sparse but valid result can return `status: insufficient_data` with HTTP 200; this is an explicit result, not a failure or a diagnosis.

## Use the dashboard workflow

1. Open the local dashboard and select **Compare**.
2. Search for and select two through five imported conditions.
3. Keep at least one dimension selected.
4. Select **Compare selected conditions**.
5. Inspect **Shared**, **Distinct**, and **Missing data** panels.
6. Follow a claim link to inspect the assertion in Evidence Explorer.

`KNOWN_ABSENT` cells can link to the negated claim that produced the state. `NOT_RECORDED` cells are deliberately non-clickable because there is no assertion to inspect.

## Replay or export a run

Use the returned `run_id` with:

```text
GET /api/v1/nosograph/comparisons/{run_id}
GET /api/v1/nosograph/comparisons/{run_id}/exports/json
GET /api/v1/nosograph/comparisons/{run_id}/exports/markdown
```

The JSON and Markdown exports are deterministic for the same canonical inputs and active data. They include reproducibility metadata and the research-use disclaimer.

## Compatibility and limits

`POST /api/v1/nosograph/compare` is deprecated but retained for existing clients as a two-condition projection of Compare V2. The separate scored `POST /api/v1/comparisons` API remains distinct. Compare history UI, Workspace save, and CLI export are outside the current Compare workflow.

Compare can show differences in what is recorded, validated, or imported. It cannot determine diagnosis, severity, treatment choice, or causal mechanism from a comparison result.

## Continue

- [Evidence Explorer](evidence-explorer.md) — inspect an exact claim behind a result.
- [Evidence semantics](../concepts/evidence.md) — interpret direction labels.
- [Provenance](../concepts/provenance.md) — follow source and snapshot context.
- [API reference](../api-reference.md) — see the full endpoint and export catalog.
