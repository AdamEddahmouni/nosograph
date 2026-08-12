# Universal Biomedical Legacy Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Project the seven curated disease modules into the canonical biomedical store as explicit claims and entities while preserving all existing disease loaders, graph builders, APIs, and coverage contracts.

**Architecture:** Add a `med_research.biomed.legacy` package with a reviewed disease-to-Mondo manifest, deterministic file checksums, a migration adapter that emits `ImportBundle` records, and parity reports. Compatibility projections may read the canonical store when a `legacy-curated` snapshot is active, but JSON loaders under `src/med_research/diseases/` remain the compatibility source of truth in v1.

**Tech Stack:** Python 3.11+, Pydantic 2, SQLite 3 (via Stage 1 repository), pytest, Ruff, mypy.

**Depends on:** [Canonical Core](2026-08-11-universal-biomedical-canonical-core.md) and [Ontology Ingestion](2026-08-11-universal-biomedical-ontology-ingestion.md) — Mondo snapshot import must be available so legacy condition nodes resolve to imported Mondo entities.

## Global Constraints

- Preserve all seven disease modules and every current `/api/*` contract.
- Do not remove or rewrite existing JSON data files during migration.
- Use explicit reviewed Mondo mappings; never infer mappings from labels or synonyms.
- Convert relationships into claims with provenance no stronger than the source file supports.
- Non-SLE diseases must not inherit SLE identifiers, scores, or therapy rubrics.
- Migration writes are atomic, idempotent, and recorded under resource name `legacy-curated`.
- Preserve unrelated working-tree changes; stage only files named by the active task.

## Reviewed Legacy Disease → Mondo Mapping

These mappings are fixed for v1 and must be validated in tests:

| Legacy ID | Display name | Mondo CURIE |
|---|---|---|
| `sle` | Systemic Lupus Erythematosus | `MONDO:0007915` |
| `ra` | Rheumatoid Arthritis | `MONDO:0008390` |
| `ms` | Multiple Sclerosis | `MONDO:0005217` |
| `ss` | Sjögren's Syndrome | `MONDO:0011604` |
| `ssc` | Systemic Sclerosis (Scleroderma) | `MONDO:0005101` |
| `t1d` | Type 1 Diabetes | `MONDO:0005147` |
| `ibd` | Inflammatory Bowel Disease | `MONDO:0005265` |

---

### Task 1: Migration Manifest and Checksums

**Files:**
- Create: `src/med_research/biomed/legacy/__init__.py`
- Create: `src/med_research/biomed/legacy/manifest.py`
- Create: `src/med_research/biomed/legacy/checksums.py`
- Test: `tests/biomed/legacy/test_manifest.py`

**Interfaces:**
- Consumes: `Disease.list_all()`, disease data files under `src/med_research/diseases/{id}/data/`.
- Produces: `LEGACY_DISEASE_MONDO_MAP`, `legacy_resource_version()`, `legacy_file_checksums(disease_id)`.

- [ ] **Step 1: Write failing manifest tests**

```python
import pytest

DISEASES = ["sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"]


@pytest.mark.parametrize("disease_id", DISEASES)
def test_every_legacy_disease_has_reviewed_mondo_mapping(disease_id: str) -> None:
    from med_research.biomed.legacy.manifest import LEGACY_DISEASE_MONDO_MAP

    assert disease_id in LEGACY_DISEASE_MONDO_MAP
    assert LEGACY_DISEASE_MONDO_MAP[disease_id].startswith("MONDO:")


def test_legacy_checksums_cover_required_data_files() -> None:
    from med_research.biomed.legacy.checksums import legacy_file_checksums

    checksums = legacy_file_checksums("sle")
    assert set(checksums) >= {"profile.json", "genes.json", "drugs.json", "pathways.json", "relationships.json"}
```

- [ ] **Step 2: Run tests and verify package is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/legacy/test_manifest.py -q`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement manifest and checksum helpers**

Record the current Git commit short hash and a deterministic SHA-256 per required data file. Expose `legacy_resource_version()` as `legacy-curated@{commit}` for snapshot versioning. Reject unknown disease IDs during migration.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/legacy/test_manifest.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/legacy tests/biomed/legacy/test_manifest.py
git commit -m "feat: add legacy disease migration manifest"
```

### Task 2: Legacy Entity and Claim Projection

**Files:**
- Create: `src/med_research/biomed/legacy/projector.py`
- Test: `tests/biomed/legacy/test_projector.py`

**Interfaces:**
- Consumes: `Disease`, `LEGACY_DISEASE_MONDO_MAP`, Stage 1 models.
- Produces: `project_disease(disease_id) -> ImportBundle` fragment with entities, revisions, mappings, and claims.

- [ ] **Step 1: Write failing projection tests**

```python
def test_sle_projection_emits_genes_drugs_and_target_claims() -> None:
    bundle = project_disease("sle")
    types = {rev.entity_type for rev in bundle.revisions}
    assert EntityType.GENE in types
    assert EntityType.INTERVENTION in types
    predicates = {claim.predicate for claim in bundle.claims}
    assert Predicate.TREATED_BY in predicates or Predicate.HAS_BIOMARKER in predicates


def test_ra_projection_does_not_emit_sle_identifiers() -> None:
    bundle = project_disease("ra")
    serialized = bundle.model_dump_json()
    assert "MONDO:0007915" not in serialized or "ra" in serialized
    assert "Lupus (SLE)" not in serialized
```

Map relationship `type` values from `relationships.json` to controlled predicates:

- `TARGETS` → `Predicate.ASSOCIATED_WITH_GENE` or a dedicated targets predicate approved in Stage 1.
- `TREATS` / `TREATED_BY` → `Predicate.TREATED_BY`.
- `PARTICIPATES_IN` / pathway edges → `Predicate.INVOLVES_PATHWAY`.
- `HAS_BIOMARKER` → `Predicate.HAS_BIOMARKER`.

Preserve legacy node IDs as `EntityMapping` rows with relation `exact` only when the legacy ID is a stable curated identifier, otherwise `close` with notes.

- [ ] **Step 2: Run tests and verify projector is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/legacy/test_projector.py -q`

Expected: import failure.

- [ ] **Step 3: Implement projector**

Load validated JSON through existing `Disease` helpers. Create one condition entity per reviewed Mondo mapping. Project genes, drugs, pathways, and biomarkers as typed entities. Convert relationships into claims with source record IDs pointing to the originating JSON row. Attach lightweight `ClaimEvidence` rows referencing the `legacy-curated` snapshot and source file offsets.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/legacy/test_projector.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/legacy/projector.py tests/biomed/legacy/test_projector.py
git commit -m "feat: project legacy disease graphs into canonical claims"
```

### Task 3: Migration Adapter and Import Bundle Assembly

**Files:**
- Create: `src/med_research/biomed/legacy/adapter.py`
- Test: `tests/biomed/legacy/test_adapter.py`

**Interfaces:**
- Consumes: `project_disease`, `ImportBundle`, `ResourcePolicy`.
- Produces: `LegacyMigrationAdapter.build_bundle(disease_ids: Sequence[str] | None = None) -> ImportBundle`.

- [ ] **Step 1: Write failing adapter tests**

```python
def test_build_bundle_covers_all_seven_diseases() -> None:
    bundle = LegacyMigrationAdapter().build_bundle()
    mapped = {entry.legacy_id for entry in bundle.metadata["diseases"]}
    assert mapped == set(DISEASES)


def test_bundle_snapshot_uses_legacy_curated_resource_name() -> None:
    bundle = LegacyMigrationAdapter().build_bundle(["sle"])
    assert bundle.snapshot.resource_name == "legacy-curated"
    assert bundle.snapshot.checksum
```

- [ ] **Step 2: Run tests and verify adapter is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/legacy/test_adapter.py -q`

Expected: import failure.

- [ ] **Step 3: Implement adapter**

Merge per-disease fragments into one bundle. Include manifest metadata: Git commit, per-disease file checksums, and reviewed Mondo CURIEs. Use `ResourcePolicy` with redistribution `redistributable` for curated repository content.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/legacy/test_adapter.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/legacy/adapter.py tests/biomed/legacy/test_adapter.py
git commit -m "feat: assemble legacy migration import bundles"
```

### Task 4: Parity Reports and Exception Tracking

**Files:**
- Create: `src/med_research/biomed/legacy/report.py`
- Test: `tests/biomed/legacy/test_report.py`

**Interfaces:**
- Consumes: legacy JSON counts and imported canonical counts.
- Produces: `ParityReport` with per-disease entity/claim counts, unmatched relationships, and exception list.

- [ ] **Step 1: Write failing parity tests**

```python
def test_parity_report_matches_legacy_relationship_count_for_sle() -> None:
    report = build_parity_report("sle")
    assert report.relationships.source_count > 0
    assert report.relationships.imported_count == report.relationships.source_count
    assert report.exceptions == []
```

- [ ] **Step 2: Run tests and verify report module is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/legacy/test_report.py -q`

Expected: import failure.

- [ ] **Step 3: Implement parity reporting**

Count genes, drugs, pathways, relationships, and profile fields from source JSON. Compare against bundle contents after projection. Record skipped rows with reason codes (`unsupported_predicate`, `duplicate_entity`, `invalid_reference`).

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/legacy/test_report.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/legacy/report.py tests/biomed/legacy/test_report.py
git commit -m "feat: add legacy migration parity reports"
```

### Task 5: Compatibility Suite and Optional Projection Reads

**Files:**
- Create: `src/med_research/biomed/legacy/compat.py`
- Modify: `tests/test_multidisease_coverage.py` (only if a shared helper is needed)
- Test: `tests/biomed/legacy/test_compat.py`

**Interfaces:**
- Consumes: active `legacy-curated` snapshot, existing `Disease` loaders.
- Produces: `legacy_projection_enabled(repository) -> bool` and read-only helpers for canonical claim counts per legacy disease.

- [ ] **Step 1: Write failing compatibility tests**

```python
@pytest.mark.parametrize("disease_id", DISEASES)
def test_existing_graph_builder_still_works_after_migration_import(disease_id: str) -> None:
    from med_research.pipeline.knowledge_graph.builder import build_graph

    graph = build_graph(disease_id)
    assert graph.number_of_nodes() > 0


def test_canonical_projection_is_optional_when_snapshot_inactive(repository) -> None:
    assert legacy_projection_enabled(repository) is False
```

Use the project's actual knowledge-graph entrypoint if the import path differs; adjust the test import to match repository reality before implementation.

- [ ] **Step 2: Run tests and verify helpers are missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/legacy/test_compat.py -q`

Expected: failures for missing helper or assertion mismatch.

- [ ] **Step 3: Implement compatibility boundary**

Do not change default graph construction. When `legacy-curated` is active, expose canonical claim counts and Mondo resolution for diagnostics only. Feature remains off unless `BIOMED_LEGACY_PROJECTION=1` is set.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/legacy/test_compat.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/legacy/compat.py tests/biomed/legacy/test_compat.py
git commit -m "feat: keep legacy loaders primary with optional projection reads"
```

### Task 6: CLI, Documentation, and Stage 3 Gate

**Files:**
- Modify: `src/med_research/cli.py`
- Modify: `Makefile`
- Modify: `docs/api-reference.md`
- Test: `tests/biomed/legacy/test_cli.py`

**Interfaces:**
- Consumes: `ImportService`, `LegacyMigrationAdapter`, `build_parity_report`.
- Produces: `biomed migrate legacy [--db PATH] [--disease ID] [--report PATH]` and Make target `biomed-migrate-legacy`.

- [ ] **Step 1: Write failing CLI tests**

```python
def test_biomed_migrate_legacy_imports_and_writes_report(tmp_path: Path) -> None:
    db = tmp_path / "biomedical.sqlite3"
    report = tmp_path / "parity.json"
    init_cli_db(db)
    import_mondo_fixture(db)
    result = run_cli("biomed", "migrate", "legacy", "--db", str(db), "--report", str(report))
    assert result.exit_code == 0
    assert report.exists()
```

- [ ] **Step 2: Run test and verify command is unknown**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/legacy/test_cli.py -q`

Expected: parser rejects `biomed migrate`.

- [ ] **Step 3: Wire CLI and docs**

Document that migration requires an imported Mondo snapshot. Emit parity summary to stdout and optional JSON report path. Clarify that legacy JSON loaders remain authoritative for existing modules.

- [ ] **Step 4: Run the Stage 3 gate**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed -q`

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_multidisease_coverage.py tests/test_pipeline_contracts.py -q`

Run: `.\.venv\Scripts\python.exe -m med_research.cli disease validate --all --strict`

Run: `.\.venv\Scripts\python.exe -m ruff check src/med_research/biomed tests/biomed`

Run: `.\.venv\Scripts\python.exe -m mypy src/med_research/biomed`

Run: `git diff --check`

Expected: every command exits `0`; all seven modules validate.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/cli.py Makefile docs/api-reference.md tests/biomed/legacy/test_cli.py
git commit -m "feat: expose legacy biomedical migration cli"
```
