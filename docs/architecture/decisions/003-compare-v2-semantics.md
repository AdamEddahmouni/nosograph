# ADR-003: Compare V2 semantics

- Status: Accepted
- Date: 2026-08-22
- Decision owners: NosoGraph maintainers

## Context

The original NosoGraph Compare endpoint compared a left and right condition independently by
dimension. It could not represent membership shared by only part of a larger cohort, and empty
curation could be confused with explicit negative assertions. Reproducible multi-condition
research also requires canonical inputs and a persisted result contract.

## Decision

Compare V2 is the canonical deterministic engine for cohorts of two through five unique,
resolved condition CURIEs. Condition CURIEs are normalized, deduplicated, and sorted
lexicographically. Selected dimensions are deduplicated and emitted in this fixed order:

1. `phenotype`
2. `gene`
3. `pathway`
4. `treatment`
5. `evidence_coverage`

The four entity dimensions use the following cell states:

- `PRESENT`: a current positive assertion backed by an active snapshot exists.
- `KNOWN_ABSENT`: one or more current assertions have `qualifiers.negated=true`, and no
  positive assertion exists.
- `NOT_RECORDED`: no current positive or negated assertion exists.

Empty data never implies absence. If positive and negated assertions coexist, `PRESENT` takes
precedence and a structured `CONFLICTING_ASSERTIONS` warning is returned.

Positive memberships are partitioned into entities shared by all conditions, entities shared
by a proper subset, and entities unique to one condition. The response also includes the full
condition-by-entity state matrix and per-condition dimension coverage. All collections and map
insertion order are canonical.

`evidence_coverage` reports current claim count, active evidence count, distinct source-resource
count, distinct active snapshot count, source names, and snapshot IDs per condition. It does not
compare claim identifiers.

A requested comparison is `comparable` when at least one requested dimension has recorded data
for at least two conditions. Otherwise a valid sparse comparison is `insufficient_data` and
still returns HTTP 200.

Warnings have stable `code`, `dimension`, affected `condition_curies`, per-condition `counts`,
and `message` fields. `MISSING_CURATION` is emitted for zero versus nonzero positive-claim
counts. `ASYMMETRIC_CURATION` is emitted when nonzero counts differ by at least 2x and by an
absolute delta of at least three. Conflict warnings additionally identify `entity_curie`.

Each comparison persists one deterministic `nosograph_compare_v2` research run using algorithm
version `2.0.0`. Its fingerprint includes canonical conditions, canonical dimensions, condition
fingerprints, active snapshots, claims, and algorithm version. Permutations of identical inputs
replay the same completed run and run ID.

The canonical API is `POST /api/v1/nosograph/comparisons`. Invalid CURIE syntax, unresolved
conditions, invalid cohort cardinality, empty dimension selections, and unknown dimensions
return HTTP 422. `POST /api/v1/nosograph/compare` is deprecated and remains a two-condition
projection of V2; its legacy `mechanism` dimension maps to `pathway`. The separate scored
`POST /api/v1/comparisons` API is unchanged.

## Rejected alternatives

- A universal similarity score: it hides dimension-specific evidence and curation limitations.
- Composing N-way results from pairwise comparisons: it loses proper-subset membership and can
  duplicate fingerprint work.
- Claim-ID overlap as evidence coverage: claim identifiers are assertion records, not comparable
  evidence sources.
- Inferring `KNOWN_ABSENT` from empty data: lack of curation is not evidence of absence.

## Consequences

Clients receive a larger but explicit response contract and must handle structured warnings and
three-state entity matrices. Results are reproducible across request permutations. The legacy
pairwise endpoint remains available during migration without maintaining a second comparison
semantics implementation.
