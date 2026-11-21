# ADR-R5-01 — Canonical scientific semantics and object lifecycle (PROPOSED)

**Problem:** Legacy disease JSON, universal biomedical claims, Evidence Workspace `Claim` objects, pipeline output and hypothesis-agent results encode overlapping concepts. Without an explicit adapter boundary, inconsistent evidence direction or identity can make conflicting sources appear equivalent. **Decision proposal:** one typed scientific kernel with compatibility adapters and immutable historical records; do not bulk-migrate existing source files as a first action.

## Core objects

| Object | Immutable/Mutable | Essential fields | Invariant |
|---|---|---|---|
| ScientificEntity | Revisioned | stable ID, type, ontology CURIE, aliases, map source | `EXACT` != `CLOSE` mappings |
| Observation | Immutable | observed quantity, units, specimen, collection context, method, source | a measured null is not missing data |
| ScientificAssertion | Revisioned | subject, relation, object, evidence type, population/tissue/time qualifiers, provenance | association cannot become causal automatically |
| SourceRecord | Immutable | URI, checksum, source publication, license, snapshot, retrieval method | no citation without verifiable source identity |
| EvidenceLink | Append-only | assertion, source, evidence direction, study design, dependence group, directness | contradictory evidence is not discarded |
| Hypothesis | Revisioned | explicit competing predictions, falsification, source graph, reviewer status | `PROPOSED` is not `VALIDATED` |
| ExperimentProtocol | Immutable after freeze | outcomes, baseline, controls, units, split, analysis plan, stopping rules | no overwritten prespecified methods |
| ModelSpecification | Revisioned | equations/formats, solver requirement, bounds, parameters, units, validation domain | numerical reproduction != biological validation |
| RunManifest | Append-only events | exact code/data/environment hash, seed, version and lineage | result provenance must be auditable |
| ReviewDecision | Immutable | decision, role, timestamp, evidence, scope, conflicts | author cannot unilaterally certify research claim |
| PublicationRecord | Revisioned | reviewers, correction chain, data access context and DOI if assigned | retractions propagate without erasing history |

## Evidence-direction taxonomy

- `SUPPORTING`: evidence supports the *specific contextual assertion*.
- `REFUTING`: evidence directly conflicts in sufficiently comparable conditions.
- `NULL`: a measured effect consistent with no effect under a defined precision context.
- `MIXED`: evidence contains multiple meaningful directions or heterogeneity.
- `INDIRECT`: relevant only through stated assumptions or bridge variables.
- `UNASSESSED`: evidence exists but direction cannot be established.
- `WITHDRAWN`: source corrected/retracted or output withdrawn; preserve historical fact that it was once asserted.

None of the states is a scalar "confidence". Statistical significance, effect magnitude, risk of bias, sample size, directness, consistency, precision, independence and generalizability should be independently represented and reviewed.

## Contextual contradiction test

A pair of study claims is a candidate contradiction only after comparing: population, age and sampling; species/organ/tissue/cell; intervention/contrast, dose, timing; outcome or estimand; assay and unit; design/adjustment; source dependence; status/version; and measurement quality. Unknown fields generate a "context insufficient" report, **not** a forced contradiction. Differences can be biologically informative and need not indicate study failure.

## Provenance and identifier policy

Primary key for internal objects: UUID or content hash as appropriate; qualified identifiers for ontology refs; stable version records for source terms; external IDs never overwrite internal identity. Preserve original CURIE and normalized mapping with map relation type, source/version and reviewer. A current release may change mapping labels without retroactively rewriting old research runs.

Use W3C PROV-O concepts of `Entity`, `Activity` and `Agent` for source and transformation provenance (https://www.w3.org/TR/prov-o/). Use RO-Crate 1.2 for export bundles (https://www.researchobject.org/ro-crate/specification/1.2/index.html). Ensure public exports never include restricted raw data without rights review.

## Persistence and migration

1. Map legacy `biomed.Claim` and Workspace `Claim` into an adapter-level canonical view; do not drop fields or alter old identifiers.
2. Define field-by-field lossy/lossless mapping and roundtrip tests for 20 representative fixtures.
3. Keep unknown values explicit; never invent study design, date, unit, or population.
4. Use versioned database migrations with backups and compatibility tests, not destructive schema reset.
5. Support immutable read snapshots while concurrent research jobs run.
6. Keep API `v1` functional under a compatibility layer; introduce new namespaced endpoints only after reviewed contracts.

## Synthetic acceptance fixtures

- `p = 0.0001` and small sample: statistical quality must not automatically become HIGH.
- Review paper and primary paper from same cohort: two publications, at most one independent study family.
- Human and mouse effect directions differ: classify context difference, not direct contradiction.
- Not-recorded phenotype and experimentally measured absent phenotype remain distinct.
- Estimand compares absolute vs relative risk: never silently average.
- Units of ng/mL vs µg/L may be equivalent numerically; assay method may still be non-comparable.
- Correction supersedes evidence: old version remains accessible and flagged.
- Agent-generated interpretation is `COMPUTATIONAL_INFERENCE`, never independent evidence from a primary study.