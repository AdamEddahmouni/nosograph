# Universal Biomedical Schema v1 Design

**Date:** 2026-08-11

**Status:** Approved design

## Purpose

Transform `med-research` from seven disease-specific knowledge graphs into the first version of a universal, computable biomedical knowledge platform. The existing seven disease modules remain a curated regression corpus and compatibility surface while a new claim-centric store becomes the canonical representation for conditions, phenotypes, biological entities, interventions, evidence, and reproducible analyses.

The milestone is **7-Disease Prototype to Universal Biomedical Schema v1**. It establishes the foundation for later clinical-case interoperability, additional biological sources, unresolved-case clustering, and collaborative research without attempting those independent subsystems in this release.

## Goals

1. Define stable, versioned models for biomedical resources, entities, mappings, claims, claim evidence, and research runs.
2. Ingest Mondo conditions, the HPO ontology, and HPO disease-phenotype annotations through reproducible, license-aware adapters.
3. Migrate the seven existing disease datasets into the universal representation without breaking current disease APIs or analysis modules.
4. Render and query any imported condition through generic APIs and the dashboard without requiring a hand-authored disease module.
5. Compare conditions using transparent, coverage-aware phenotype and biological fingerprints.
6. Make every import and comparison reproducible from immutable resource snapshots and research-run manifests.
7. Keep all output explicitly research-oriented and avoid diagnosis or patient-specific recommendations.

## Non-Goals

Universal Biomedical Schema v1 does not include:

- Patient records, protected health information, or case submission.
- An unresolved phenotype registry or candidate-condition clustering.
- Diagnostic recommendations or clinical decision support.
- FHIR, OMOP, or Phenopacket import/export.
- ClinVar, ClinGen, SNOMED CT, UMLS, or ICD ingestion.
- A hosted graph database, distributed ingestion service, or multi-node storage system.
- Automatic biomedical conclusions inferred from labels or language models.
- Equal analysis-module readiness for every imported Mondo condition.

The schema will leave explicit extension points for these capabilities, but no partial implementation will be presented as functional.

## Approaches Considered

### Compatibility-first canonical core

Add a universal schema and canonical store beside the existing disease modules. Migrate current data through adapters and gradually redirect consumers to the new repositories. This approach preserves the extensive existing API, CLI, dashboard, and pipeline behavior while creating a clean foundation.

This is the selected approach.

### Immediate graph-database rewrite

Replace disease modules and NetworkX construction with Neo4j or another hosted property-graph database. This would offer graph-native traversal and future horizontal scaling but would add deployment and migration complexity before the data contract and workflows are stable. It would also place the existing local and offline workflows at risk.

### RDF and triplestore-first platform

Represent the platform directly as RDF/OWL and use a SPARQL endpoint. This aligns strongly with ontology standards but makes qualifier modeling, evidence workflows, local deployment, and existing Python integration more complex. RDF export can be added later from the canonical claim model without requiring RDF to be the first operational store.

## Architectural Principles

### Claims are fundamental

A condition page is a projection. The durable scientific unit is a claim connecting a subject to an object through a controlled predicate. Descriptions, pages, graphs, fingerprints, and comparisons are derived views.

### Scientific state is immutable and versioned

Imported resource snapshots, normalized claims, evidence assertions, and research runs are immutable. A new upstream release creates a new snapshot. Corrections or changed evidence create new records or explicit supersession links rather than silently rewriting history.

### Identifiers take precedence over labels

Entity resolution uses CURIEs and explicit published mappings. Labels and synonyms support search only. They must never create exact biomedical mappings or claims automatically.

### Coverage remains visible

The platform distinguishes ontology presence, available claims, curated support, and executable analysis-module coverage. An imported condition is not automatically research-pipeline ready.

### The open core stays license-aware

Software, schemas, unrestricted adapters, and redistributable data remain separate from terminology sources that require individual licenses. Every resource snapshot records its license and redistribution policy.

### Research use only

Condition similarity and candidate relationships are research hypotheses, not diagnoses, treatment recommendations, or evidence of efficacy. User-facing text, APIs, and exported manifests preserve this boundary.

## System Architecture

The new biomedical core is divided into focused units:

1. **Domain models** validate resources, entities, mappings, claims, evidence links, fingerprints, and runs.
2. **Repository interfaces** define storage-neutral reads and writes.
3. **SQLite repositories** provide the initial canonical implementation.
4. **Source adapters** fetch or read artifacts and normalize source records.
5. **Import orchestration** stages, validates, and atomically records a resource snapshot.
6. **Legacy migration** converts the seven disease datasets into universal records.
7. **Projection services** build condition views and bounded NetworkX graphs.
8. **Fingerprint and comparison services** calculate transparent similarity results.
9. **Research-run services** store immutable inputs, versions, parameters, outputs, and warnings.
10. **API, CLI, and dashboard adapters** expose the new capabilities while preserving existing routes.

The canonical SQLite store is separate from the Evidence Workspace database. The two stores have different lifecycles: the biomedical store contains versioned shared knowledge, while the Workspace store contains user-owned dossiers, reviews, alerts, and delivery state.

## Canonical Data Model

### ResourceSnapshot

Represents one immutable imported release.

- `snapshot_id`: deterministic UUID derived from resource ID, upstream version, and artifact checksum.
- `resource_id`: stable source name such as `mondo`, `hp`, `hpoa`, or `legacy-curated`.
- `name`, `namespace_prefix`, `source_url`, and `artifact_format`.
- `upstream_version` and optional `version_iri`.
- `sha256` and artifact byte size.
- `license_id`, `license_url`, attribution text, and `redistribution_policy`.
- `retrieved_at`, `imported_at`, importer name, and importer version.
- Counts, warnings, and an import manifest fingerprint.

`redistribution_policy` is one of `redistributable`, `user_supplied`, or `restricted`. Importers reject restricted content unless it was explicitly mounted by the operator and the adapter is configured for local use.

### Entity

Represents the stable identity of a biomedical concept.

- `entity_id`: UUIDv5 derived from entity type and stable primary CURIE.
- `primary_curie`: canonical external identifier when available.
- `entity_type`: controlled value including `condition`, `phenotype`, `gene`, `variant`, `protein`, `pathway`, `drug`, `procedure`, `device`, `measurement`, `anatomy`, `exposure`, `organism`, or `other`.
- `created_in_snapshot_id`, recording the first imported appearance.

An entity's identity does not change when an upstream resource changes its preferred label, definition, synonyms, or obsolescence metadata.

### EntityRevision

Represents an entity as published in one immutable resource snapshot.

- `entity_revision_id`: deterministic identifier derived from entity and snapshot.
- `entity_id` and `snapshot_id`.
- `label`, `definition`, synonyms, and alternative labels.
- `obsolete`, `replaced_by`, and `consider` identifiers.
- Source-native record identifier and retained audit properties.

Condition pages resolve revisions through the selected active snapshot set. Historical runs resolve the exact revisions from their recorded snapshot IDs.

### EntityMapping

Connects one entity to another identifier.

- `mapping_id`.
- `entity_id`.
- `mapped_curie`.
- `relation`: `exact`, `close`, `broad`, or `narrow`.
- `snapshot_id` and source-native record identifier.
- Optional evidence and mapping notes.

Only exact mappings participate automatically in cross-source joins. Close, broad, and narrow mappings remain inspectable but do not collapse entities.

### Claim

Represents a normalized biomedical statement.

- `claim_id`: deterministic UUIDv5 over normalized subject, predicate, object, and identity-bearing qualifiers.
- `subject_entity_id`.
- `predicate`: controlled predicate identifier.
- `object_entity_id` or a typed literal, never both.
- Structured qualifiers for frequency, onset, age range, sex or context, disease stage, severity, anatomical location, temporal relationship, population, and negation.
- Optional `supersedes_claim_id`.

Claims are never updated in place. A correction creates a new claim with `supersedes_claim_id`; whether a claim is current is derived from the selected snapshots and the supersession chain.

Initial controlled predicates include `IS_A`, `HAS_PHENOTYPE`, `ASSOCIATED_WITH`, `TARGETS`, `PARTICIPATES_IN`, `MODULATES`, `DRIVES`, `TREATS`, `HAS_BIOMARKER`, and `DIFFERENTIAL_OF`. Predicate definitions are centralized and validated; adapters cannot introduce arbitrary predicates silently.

### ClaimEvidence

Represents a source-specific assertion about a claim.

- `claim_evidence_id`: deterministic identifier derived from claim, snapshot, and source-native record.
- `claim_id` and `snapshot_id`.
- `direction`: `supports` or `contradicts`.
- Source-native identifier, citation identifiers, URL, and publication date.
- Evidence or study type, population, sample size when supplied, and source evidence code.
- Strength label, normalized confidence, and rationale.
- Curator, extraction method, importer version, and extraction time.
- Limitations and unparsed source fields retained for audit.

Confidence values are transparent source or heuristic metadata, not probabilities of clinical truth.

### ResearchRun

Represents one computational analysis that becomes immutable when it reaches a terminal state.

- `run_id` and optional `parent_run_id` for forks.
- Run type, status, and timestamps.
- Input entity IDs or query.
- Exact resource snapshot IDs and claim-set fingerprint.
- Algorithm ID, algorithm version, software version, and parameters.
- Results, confidence metadata, citations, limitations, and warnings.
- Stable reproducibility fingerprint excluding run ID and timestamps.

A run may transition from `pending` to `running` and then exactly once to `completed` or `failed`. Inputs, snapshot selections, algorithm identity, and parameters are fixed before execution. Terminal runs cannot be edited; a changed analysis is a new run with an optional parent link.

Comparison v1 is the first producer of universal ResearchRun records. The existing Evidence Workspace dossier remains supported and can later be adapted to this shared run envelope without changing its current persisted schema in this milestone.

## Storage Design

SQLite is the initial canonical store because it preserves local deployment, requires no additional service, supports indexed ontology-scale queries, and is already an accepted project dependency through the Python standard library.

The database contains normalized tables for snapshots, active snapshot selections, entities, entity revisions, names, mappings, claims, claim evidence, research runs, and run-snapshot links. JSON columns are limited to structured qualifiers, source-specific audit payloads, and immutable run results. Fields required for joins, filtering, provenance, or integrity constraints remain relational columns.

Requirements:

- Foreign keys are enabled on every connection.
- Write transactions are atomic.
- Schema migrations are ordered and versioned.
- Import uniqueness constraints make repeated imports idempotent.
- Activating a successfully imported snapshot updates a small selection table; it never mutates or deletes older snapshots.
- Reader connections use a bounded timeout and WAL mode where supported.
- Query methods paginate large result sets.
- NetworkX receives bounded projections rather than loading the universal graph by default.
- Database paths are configurable and default under the project `data` directory.

Repository protocols prevent callers from depending directly on SQLite details and leave room for later PostgreSQL or graph-store implementations.

## Source Adapters and Import Flow

### Adapter contract

Every source adapter provides:

- A resource descriptor and license policy.
- Supported artifact formats.
- Artifact discovery or validation for a supplied local path.
- Streaming or bounded parsing into normalized records.
- Source-version extraction.
- Validation and import statistics.

Network fetching and artifact parsing are separate operations. Tests use pinned local fixtures and never require live ontology downloads.

### Import sequence

1. Resolve the requested release URL or operator-supplied artifact.
2. Download to a temporary artifact or open the local artifact.
3. Compute SHA-256 before parsing.
4. Read and validate source version and licensing metadata.
5. Parse into a staging transaction.
6. Normalize CURIEs and source records.
7. Validate references, predicate shapes, mappings, required metadata, and counts.
8. Record unresolved mappings and rejected records explicitly.
9. Commit the snapshot atomically when validation succeeds.
10. Emit an import report and stable fingerprint.

A failed import leaves the previous active snapshot unchanged. Operators can inspect the failure report without receiving a partially updated graph.

### Mondo adapter

The Mondo JSON release is the initial condition source. The adapter imports condition entities, hierarchy, definitions, synonyms, obsolescence, replacement metadata, and published mappings. Mondo is distributed in JSON as well as OWL and OBO and is licensed CC BY 4.0.

Mondo becomes the primary condition namespace when a Mondo identifier exists. Published Mondo mappings are preserved with their declared mapping relationship. The adapter does not import restricted terminology content beyond what Mondo itself redistributes in its release.

### HPO ontology adapter

The HPO JSON release provides phenotype entities, hierarchy, definitions, synonyms, and obsolescence metadata. The exact upstream release identifier and checksum are stored rather than assuming a timeless HPO vocabulary.

### HPO annotation adapter

The HPO disease annotation release produces `HAS_PHENOTYPE` claims. Disease identifiers are joined to Mondo through exact published mappings. Qualifiers retain frequency, onset, modifiers, sex, evidence code, biocuration metadata, and negation when present.

An annotation whose disease identifier lacks an exact Mondo mapping is retained in the import report and may be represented by its source condition identifier. It must not be attached to a condition through label matching.

## Legacy Seven-Disease Migration

The seven disease modules remain frozen as the curated test corpus while their current files are projected into the universal schema.

The migration adapter:

- Uses an explicit reviewed mapping from each legacy disease ID to a Mondo CURIE.
- Records the current Git commit, every source file checksum, and a `legacy-curated` resource version.
- Converts profiles, genes, drugs, pathways, and relationship files into entities and claims.
- Links current references and evidence text as provenance without claiming a stronger evidence tier than the source supports.
- Preserves legacy identifiers as mappings or aliases.
- Produces parity counts and an exception report.

Existing `Disease`, coverage, knowledge-graph, pipeline, CLI, and API behavior remains available. Compatibility projections can read the new store when a migrated snapshot is active, but the old data loaders are not removed in v1. Tests prove that the seven current graphs and module-coverage contracts remain intact.

## Condition Query and Rendering

The universal API adds versioned endpoints for:

- Searching and listing conditions.
- Reading a condition summary and mappings.
- Traversing parents and children with explicit depth and result limits.
- Listing claims with filters for predicate, object type, evidence direction, source snapshot, and minimum confidence metadata.
- Reading claim provenance and contradictory evidence.
- Listing resource snapshots and import reports.
- Creating, reading, and comparing condition-comparison research runs.

The dashboard adds a generic condition explorer. Every imported condition can render:

- Preferred name, definition, synonyms, hierarchy, and mappings.
- Available phenotypes, genes, pathways, interventions, biomarkers, and evidence.
- Supporting and contradictory evidence with source versions.
- Data completeness and curated-module readiness.
- Links to comparison runs.

The renderer must not show absent sections as negative scientific evidence. It displays `No data imported for this section` and identifies the active resource snapshots.

Legacy API routes remain supported. New universal routes use an explicit `/api/v1` namespace so their contracts can evolve through normal versioning rather than hidden compatibility behavior.

## Condition Fingerprints and Similarity

### Fingerprint

A condition fingerprint is generated from active, query-selected claims and records:

- Positive and negative HPO phenotypes plus available frequency and timing qualifiers.
- Genes.
- Pathways.
- Drugs and other interventions.
- Biomarkers when present.
- Snapshot IDs, claim-set fingerprint, and coverage for every dimension.

The fingerprint is a versioned computational artifact, not a new biological assertion.

### Comparison algorithm v1

Phenotype similarity uses HPO ancestor structure and information-content-aware best-match average comparison. Information content for a phenotype is `-ln(annotated_conditions_at_or_below_term / all_annotated_conditions)` using the active HPO annotation snapshot. Positive and explicitly negative phenotypes are compared separately; negative findings can distinguish conditions but are never treated as positive matches.

Gene, pathway, and intervention dimensions use Jaccard overlap over canonical identifiers. The default v1 overall weights are phenotype `0.55`, gene `0.20`, pathway `0.15`, and intervention `0.10`. Biomarkers remain visible in the fingerprint and result explanation but do not receive a default v1 weight until a normalized biomarker vocabulary is part of the canonical imports.

Rules:

- Missing dimensions do not count as zero biological similarity.
- Weights are renormalized across dimensions available for both conditions.
- Results always report component scores, effective weights, shared entities, distinguishing entities, and coverage.
- A comparison with insufficient comparable information returns a structured `insufficient_data` result instead of a misleading numeric score.
- Algorithm ID, version, parameters, snapshots, and claim-set fingerprint are stored in a ResearchRun.

Weights and the information-content corpus identifier are part of the named, versioned algorithm configuration and its tests, not hidden constants in a route or renderer. Callers may request alternative valid weights, which are stored in the ResearchRun parameters and must sum to `1.0` before missing-dimension renormalization.

## Error Handling

Errors are typed and actionable:

- Artifact access errors identify the resource and path or URL.
- Checksum or version mismatches stop the import.
- Unsupported formats or schema versions are rejected before writes.
- License-policy failures explain whether an operator-supplied artifact is required.
- Invalid CURIEs, dangling references, and malformed claims identify the source record.
- Unresolved mappings produce warnings and counts unless they violate a required join.
- Import failures roll back completely.
- Unknown entities return stable API not-found responses.
- Excessive traversal or page sizes are rejected with documented limits.
- Comparisons with inadequate coverage return `insufficient_data` plus missing dimensions.

No adapter silently invents identifiers, mappings, relationships, evidence strength, or clinical conclusions.

## Licensing and Distribution

The repository includes software, schemas, fixtures, and adapters. Full ontology artifacts and generated databases are downloaded or built separately unless their license and repository policy explicitly permit bundling.

Every adapter declares:

- License identifier and URL.
- Required attribution.
- Whether redistribution is allowed.
- Whether the artifact must be supplied by the operator.
- Any territory or account constraint the software must surface.

Restricted adapters must never fall back to an unrestricted source and present it as the requested terminology. Export and API layers retain source identifiers so downstream users can enforce their own licensing obligations.

## Research and Safety Boundary

The milestone processes public biomedical knowledge only. It does not accept case data or infer a person's condition.

Required wording uses `condition similarity`, `candidate relationship`, `research hypothesis`, `supporting evidence`, and `contradictory evidence`. It avoids `you have`, `diagnosis`, `recommended treatment`, and probability-of-disease claims in generated results.

API responses and ResearchRun exports carry a research-only disclaimer. Scores are described as computational similarity or prioritization values and never as clinical probabilities.

## Testing Strategy

Implementation follows red-green-refactor cycles. Tests are predominantly fixture-backed and offline.

### Domain and persistence tests

- Stable entity, claim, evidence, snapshot, and run identifiers.
- CURIE normalization and invalid identifier rejection.
- Claim shape and predicate validation.
- Exact versus non-exact mapping behavior.
- Schema migrations from every supported database version.
- Foreign-key and uniqueness constraints.
- Import idempotency and rollback after injected failures.

### Adapter contract tests

- Pinned minimal Mondo, HPO, and HPO annotation fixtures.
- Source version and checksum extraction.
- Hierarchy, synonym, mapping, obsolescence, and qualifier preservation.
- Unresolved mapping reports.
- License policy enforcement.
- Deterministic import reports and fingerprints.

### Migration and compatibility tests

- Explicit Mondo mapping for all seven diseases.
- Entity and relationship parity reports.
- Existing graph construction, coverage, CLI, and API contracts remain passing.
- No non-SLE disease inherits SLE identifiers or content.

### Query and renderer tests

- Pagination, filters, hierarchy bounds, and not-found behavior.
- Generic rendering for imported but uncurated conditions.
- Provenance and contradiction display.
- Clear distinction between ontology presence and module readiness.
- Research-only language and keyboard/accessibility behavior.

### Comparison tests

- Identical fingerprints score maximally for comparable dimensions.
- Disjoint fingerprints do not produce false overlap.
- HPO ancestor relationships affect semantic similarity predictably.
- Missing dimensions cause weight renormalization, not false zeroes.
- Inadequate data returns `insufficient_data`.
- Runs preserve snapshots, algorithm version, parameters, results, warnings, and stable fingerprints.

### Verification gates

- Focused unit and integration tests for each task.
- Full offline suite.
- Relevant browser tests.
- Lint, type checking, import audit, compile check, and `git diff --check`.
- Strict validation and coverage checks for all seven diseases.

## Rollout

### Stage 1: Canonical core

Add models, repositories, SQLite migrations, deterministic identifiers, resource licensing metadata, and ResearchRun storage.

### Stage 2: Ontology ingestion

Add Mondo, HPO, and HPO annotation adapters with local fixtures, staged imports, reports, and CLI administration.

### Stage 3: Legacy migration

Map and import the seven disease modules, generate parity reports, and introduce compatibility projections without removing current loaders.

### Stage 4: Universal query and rendering

Add versioned APIs, the generic condition explorer, provenance views, and explicit coverage/readiness display.

### Stage 5: Fingerprints and comparison

Add hierarchy-aware phenotype similarity, transparent biological overlap, immutable comparison runs, APIs, CLI commands, and dashboard results.

Each stage must leave the repository in a working, independently testable state. Later stages depend only on documented interfaces produced by earlier stages.

## Success Criteria

Universal Biomedical Schema v1 is complete when:

1. A pinned Mondo release and HPO release can be imported reproducibly into a fresh canonical store.
2. Resource versions, checksums, licenses, counts, warnings, and fingerprints are inspectable.
3. Imported condition-phenotype annotations retain qualifiers and provenance.
4. All seven legacy diseases map explicitly to Mondo and appear as deeply curated nodes without breaking existing functionality.
5. Any imported condition can be searched, queried, and rendered generically.
6. Claims expose supporting and contradictory evidence without collapsing provenance.
7. Two sufficiently described conditions can be compared with component scores, coverage, and an immutable ResearchRun.
8. Insufficient data produces an explicit non-scored result.
9. Existing offline tests and the new universal-schema tests pass, and static checks succeed.
10. No v1 workflow accepts patient data or presents diagnosis or treatment recommendations.

## Deferred Roadmap

After this milestone, separate design cycles may add:

1. Phenopacket v2 import/export and de-identified or federated case infrastructure.
2. Measurement, FHIR, and OMOP interoperability.
3. ClinVar and ClinGen genetic evidence adapters.
4. Broader intervention, pathway, exposure, and outcome sources.
5. Collaborative claim curation and dataset or algorithm forks.
6. Unresolved-case similarity and candidate-condition clusters.
7. Optional PostgreSQL, graph-database, RDF, and federated deployments.

Each deferred subsystem requires its own safety, licensing, privacy, and scientific-validation design before implementation.
