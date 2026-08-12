# Universal Biomedical Schema v1 Implementation Plan

> **Status: Implementation complete (2026-08-12).** All five stage plans are implemented and verified against the release acceptance checklist below.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the seven-disease data silo as the platform's canonical model with a versioned, claim-centric biomedical store while preserving all existing disease workflows.

**Architecture:** Implement the approved design as five sequential, independently releasable stages. A dedicated SQLite canonical store owns snapshots, versioned entities, claims, evidence, and research runs; existing JSON loaders remain compatibility consumers while bounded NetworkX projections support analysis.

**Tech Stack:** Python 3.11+, Pydantic 2, SQLite 3, FastAPI, NetworkX 3, pytest, Ruff, mypy, vanilla HTML/CSS/JavaScript.

## Global Constraints

- Preserve the existing seven disease modules and all current `/api/*` contracts during v1.
- Store public biomedical knowledge only; do not accept patient, case, or PHI data.
- Use `condition similarity`, `candidate relationship`, `research hypothesis`, `supporting evidence`, and `contradictory evidence` in user-facing copy.
- Do not generate diagnosis, treatment recommendations, or probability-of-disease claims.
- Every imported fact must retain source snapshot, source record, and evidence provenance.
- Only `exact` mappings may drive automatic joins; `close`, `broad`, and `narrow` mappings remain visible but non-joining.
- Import parsing is offline and fixture-backed in tests; network retrieval is a separate operator action.
- Import writes are atomic, idempotent, checksum-verified, and license-policy-aware.
- NetworkX graphs are bounded projections and never the canonical persistence layer.
- Python remains `>=3.11`; no graph database, RDF store, FHIR, OMOP, Phenopacket, SNOMED, UMLS, ClinVar, or ClinGen dependency is added in v1.
- Preserve unrelated working-tree changes; stage and commit only files named by the active task.

---

## Delivery Sequence

| Stage | Plan | Working deliverable | Entry gate | Exit gate |
|---|---|---|---|---|
| 1 | [Canonical Core](2026-08-11-universal-biomedical-canonical-core.md) | Versioned SQLite store, deterministic identifiers, repositories, graph projection, ResearchRun lifecycle | Approved design | Focused persistence tests and existing offline unit suite pass |
| 2 | [Ontology Ingestion](2026-08-11-universal-biomedical-ontology-ingestion.md) | Reproducible Mondo, HPO, and HPO annotation imports with reports | Stage 1 interfaces stable | Adapter, rollback, idempotency, license, and CLI tests pass |
| 3 | [Legacy Migration](2026-08-11-universal-biomedical-legacy-migration.md) | All seven modules represented as curated canonical claims with parity reports | Mondo snapshot imported | Seven mappings resolve and compatibility suite remains green |
| 4 | [Universal Query and Explorer](2026-08-11-universal-biomedical-query-explorer.md) | `/api/v1` condition APIs and generic condition explorer | Stages 1–3 complete | API, UI contract, accessibility, and research-language tests pass |
| 5 | [Condition Comparison](2026-08-11-universal-biomedical-condition-comparison.md) | HPO-aware fingerprints, transparent scores, immutable comparison runs | HPO hierarchy and annotations imported | Similarity invariants, run replay, API/CLI/UI, and full verification pass |

### Stage plan index

| Document | Tasks | Primary packages |
|---|---|---|
| [Canonical Core](2026-08-11-universal-biomedical-canonical-core.md) | 6 | `med_research.biomed` |
| [Ontology Ingestion](2026-08-11-universal-biomedical-ontology-ingestion.md) | 6 | `med_research.biomed.imports` |
| [Legacy Migration](2026-08-11-universal-biomedical-legacy-migration.md) | 6 | `med_research.biomed.legacy` |
| [Universal Query and Explorer](2026-08-11-universal-biomedical-query-explorer.md) | 5 | `med_research.web.models.universal`, `med_research.web.routers.universal` |
| [Condition Comparison](2026-08-11-universal-biomedical-condition-comparison.md) | 6 | `med_research.biomed.comparison` |

Approved design reference: [Universal Biomedical Schema v1 Design](../specs/2026-08-11-universal-biomedical-schema-v1-design.md).

## Stable Cross-Stage Interfaces

The following names are fixed across all stage plans:

```python
from pathlib import Path
from med_research.biomed.repository import BiomedicalRepository

repository = BiomedicalRepository(Path("data/biomedical.sqlite3"))
repository.initialize() -> None
repository.transaction() -> ContextManager[sqlite3.Connection]
repository.get_active_snapshot(resource_name: str) -> ResourceSnapshot | None
repository.get_entity(curie: str) -> EntityView | None
repository.search_entities(query: str, *, entity_type: EntityType | None, limit: int, offset: int) -> Page[EntitySummary]
repository.list_claims(subject_curie: str, *, predicate: Predicate | None) -> list[ClaimView]
repository.create_research_run(spec: ResearchRunCreate) -> ResearchRun
repository.transition_research_run(run_id: UUID, status: RunStatus, *, result: dict | None, warnings: list[str]) -> ResearchRun
```

```python
from med_research.biomed.imports.contracts import ImportAdapter, ImportBundle, ImportReport
from med_research.biomed.imports.service import ImportService

ImportAdapter.parse(path: Path, policy: ResourcePolicy) -> ImportBundle
ImportService(repository).import_bundle(bundle: ImportBundle) -> ImportReport
```

```python
from med_research.biomed.comparison.service import ConditionComparisonService

ConditionComparisonService(repository).compare(
    left_curie: str,
    right_curie: str,
    config: SimilarityConfig,
) -> ComparisonResult
```

## Program Verification

After every stage:

```powershell
.\.venv\Scripts\python.exe -m pytest <stage-focused-tests> -q
.\.venv\Scripts\python.exe -m ruff check <stage-files> <stage-tests>
.\.venv\Scripts\python.exe -m mypy <stage-files>
git diff --check
```

After Stage 5:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -m "not slow and not network" -q --tb=short
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m mypy src/med_research/biomed src/med_research/web/models/universal.py src/med_research/web/routers/universal.py src/med_research/web/services/universal_service.py
.\.venv\Scripts\python.exe scripts/check_imports.py
.\.venv\Scripts\python.exe -m compileall -q src/med_research
.\.venv\Scripts\python.exe -m med_research.cli disease validate --all --strict
git diff --check
```

Expected: every command exits `0`; the full suite has no unexpected skips; the strict disease validator reports all seven modules valid.

## Release Acceptance

- [x] A fresh store imports pinned Mondo and HPO artifacts reproducibly (`make biomed-import-fixtures`, `scripts/setup_biomed_imports.py --from-fixtures`).
- [x] Snapshot versions, checksums, license metadata, counts, warnings, and fingerprints are queryable (`GET /api/v1/snapshots`, dashboard Import Status panel).
- [x] HPO annotation qualifiers and provenance survive round-trip persistence (`tests/biomed/imports/test_hpoa_adapter.py`).
- [x] The seven legacy disease IDs resolve to explicit Mondo CURIEs (`tests/biomed/legacy/test_manifest.py`).
- [x] Every imported condition has a generic API and browser representation (`GET /api/v1/conditions/*`, Condition Explorer).
- [x] Claims show supporting and contradictory evidence independently (`ConditionClaimView` + explorer rendering).
- [x] Comparable conditions return component scores, coverage, shared entities, distinguishing entities, and a persisted ResearchRun (`POST /api/v1/comparisons`).
- [x] Inadequate data returns `insufficient_data` without a numeric overall score (`tests/biomed/comparison/test_service.py`, comparison dashboard).
- [x] Existing disease, pipeline, CLI, report, and API behavior remains passing (offline suite + `disease validate --all --strict` for core seven).
- [x] All API responses and exports carry the research-only disclaimer (`ResearchDisclaimer` on universal models).

