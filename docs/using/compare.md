# NosoGraph Compare

Compare V2 is the canonical deterministic, evidence-aware comparison engine for two through
five conditions. Its semantics are defined by
[ADR-003](../architecture/decisions/003-compare-v2-semantics.md).

## Request a comparison

Use `POST /api/v1/nosograph/comparisons`:

```json
{
  "condition_curies": ["MONDO:0007915", "MONDO:0008390"],
  "dimensions": ["phenotype", "gene", "pathway", "treatment", "evidence_coverage"]
}
```

`dimensions` is optional. When omitted, all dimensions are selected in canonical order:
`phenotype`, `gene`, `pathway`, `treatment`, and `evidence_coverage`. Duplicate condition CURIEs
and dimensions are removed. Conditions are normalized and sorted lexicographically; dimensions
are returned in canonical order regardless of request order. A request must resolve to two
through five unique entities whose type is `CONDITION`.

Only current claims with evidence from active snapshots participate. The four entity dimensions
use these predicates:

| Dimension | Claim predicate |
|---|---|
| `phenotype` | `HAS_PHENOTYPE` |
| `gene` | `ASSOCIATED_WITH_GENE` |
| `pathway` | `INVOLVES_PATHWAY` |
| `treatment` | `TREATED_BY` |

## Interpret the response

Each entity-dimension cell has one of three states:

- `PRESENT`: at least one current positive assertion exists.
- `KNOWN_ABSENT`: at least one current assertion has the literal qualifier
  `qualifiers.negated=true`, and no positive assertion exists.
- `NOT_RECORDED`: neither a current positive nor a current negated assertion exists.

Empty data never implies `KNOWN_ABSENT`. If positive and negated assertions coexist, the cell is
`PRESENT`, its claim links preserve both assertion directions, and the response includes a
`CONFLICTING_ASSERTIONS` warning.

Each item in `dimension_results` contains `shared_by_all`, `shared_by_subset`,
`unique_by_condition`, the complete `entities` state matrix, `coverage_by_condition`, and
dimension-level `warnings`. Coverage contains positive, negated, and total current claim counts;
active evidence count; distinct source-resource and active-snapshot counts; source names; and
snapshot IDs. The `evidence_coverage` dimension reports those counts without comparing claim IDs
and therefore has empty entity-membership collections.

The top-level `curation_warnings` collection aggregates warnings across dimensions:

- `MISSING_CURATION`: at least one condition has zero positive claims while another has one or
  more.
- `ASYMMETRIC_CURATION`: the smallest and largest nonzero positive-claim counts differ by at
  least 2× and by at least three claims.
- `CONFLICTING_ASSERTIONS`: one condition has both positive and negated assertions for an entity.

`status` is `comparable` when at least one requested dimension has recorded claims for two or
more conditions. Otherwise the valid sparse result is `insufficient_data`. Sparse results return
HTTP 200; malformed or unresolved conditions, invalid cohort sizes, empty dimension selections,
and unknown dimensions return HTTP 422.

The response also includes `result_schema_version`, canonical condition and dimension lists, all
active snapshot IDs, a claim-set fingerprint, algorithm ID/version, a research-use disclaimer,
and the persisted `nosograph_compare_v2` `run_id`. Repeating a completed request with the same
canonical inputs, result contract, and underlying active data replays the same payload and run ID,
including when input order differs.

`condition_labels` stores the display label used when the run was created. Each entity state row
also includes `entity_label` and `claim_ids_by_condition`. Claim IDs are sorted and point only to
current claims backed by active snapshots. Older persisted runs remain readable: missing labels
fall back to CURIEs and missing claim-link collections fall back to empty lists.

## Use the dashboard workflow

Open **Compare** in the dashboard, then:

1. Search for and select two through five imported conditions.
2. Keep at least one dimension selected.
3. Select **Compare selected conditions**.
4. Use the dimension tabs to inspect **Shared**, **Distinct**, and **Missing data** panels.
5. Follow a `claim` link to open that exact assertion in Evidence Explorer.

`KNOWN_ABSENT` cells can link to the negated claim that produced the state. `NOT_RECORDED` cells
are deliberately non-clickable because there is no assertion to inspect. Coverage and curation
warnings remain visible for sparse results, including `insufficient_data` reports.

## Replay or export a persisted run

Use the returned `run_id` with these endpoints:

```text
GET /api/v1/nosograph/comparisons/{run_id}
GET /api/v1/nosograph/comparisons/{run_id}/exports/json
GET /api/v1/nosograph/comparisons/{run_id}/exports/markdown
```

The JSON download is the exact V2 API wire payload encoded as canonical UTF-8 JSON with one final
line feed. The Markdown report uses a fixed section order and omits timestamps, so repeated
downloads of the same persisted run are byte-identical. Both formats include reproducibility
metadata and the research-use disclaimer. Missing or non-Compare run IDs return HTTP 404;
incomplete Compare runs return HTTP 409.

## Compatibility and current product scope

`POST /api/v1/nosograph/compare` is deprecated but retained for existing clients. It projects a
two-condition V2 result into the legacy left/right schema and maps
`mechanism` to the canonical `pathway` dimension. The separate scored
`POST /api/v1/comparisons` API is unchanged.

The product workflow includes the canonical engine, persistence, 2–5-condition dashboard,
explicit missingness panels, Evidence Explorer drill-down, deterministic JSON and Markdown
exports, compatibility adapter, and golden/browser coverage. Compare history UI, workspace save,
and CLI export remain out of scope.
