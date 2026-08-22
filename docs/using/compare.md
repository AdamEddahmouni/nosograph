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
`PRESENT` and the response includes a `CONFLICTING_ASSERTIONS` warning.

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

The response also includes canonical condition and dimension lists, all active snapshot IDs, a
claim-set fingerprint, algorithm ID/version, a research-use disclaimer, and the persisted
`nosograph_compare_v2` `run_id`. Repeating a completed request with the same canonical inputs and
underlying active data replays the same payload and run ID, including when input order differs.

## Compatibility and current product scope

`POST /api/v1/nosograph/compare` is deprecated but retained for the dashboard and existing
clients. It projects a two-condition V2 result into the legacy left/right schema and maps
`mechanism` to the canonical `pathway` dimension. The separate scored
`POST /api/v1/comparisons` API is unchanged.

Sprint 1 provides the canonical engine, persistence, API, compatibility adapter, and golden JSON
contract. The standalone Compare V2 dashboard, exports, CLI support, and Explorer drill-down are
not implemented yet; the existing dashboard continues to use the deprecated pairwise endpoint.
