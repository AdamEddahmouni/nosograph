# Universal Biomedical Ontology Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import pinned Mondo, HPO ontology, and HPO disease-phenotype annotation releases into the canonical biomedical store with reproducible reports, license enforcement, and atomic rollback on failure.

**Architecture:** Add a focused `med_research.biomed.imports` package with adapter contracts, fixture-backed parsers, and an `ImportService` that stages writes inside a single repository transaction. Network download remains an operator action; tests never require live ontology fetches.

**Tech Stack:** Python 3.11+, Pydantic 2, SQLite 3 (via Stage 1 `BiomedicalRepository`), pytest, Ruff, mypy.

**Depends on:** [Canonical Core](2026-08-11-universal-biomedical-canonical-core.md) — `BiomedicalRepository`, `ResourcePolicy`, `ResourceSnapshot`, entity/claim models, and deterministic identifiers must be stable before starting this stage.

## Global Constraints

- Preserve all seven disease modules and current `/api/*` contracts.
- Store public biomedical knowledge only; do not accept patient, case, or PHI data.
- Parsing and import tests use pinned local fixtures under `tests/fixtures/biomed/`; no live network in the default suite.
- Import writes are atomic, idempotent, checksum-verified, and license-policy-aware.
- A failed import leaves the previous active snapshot unchanged.
- Only `exact` mappings may drive automatic joins during annotation import.
- Preserve unrelated working-tree changes; stage only files named by the active task.

---

### Task 1: Import Contracts and Staging Models

**Files:**
- Create: `src/med_research/biomed/imports/__init__.py`
- Create: `src/med_research/biomed/imports/contracts.py`
- Create: `src/med_research/biomed/imports/models.py`
- Test: `tests/biomed/imports/test_contracts.py`

**Interfaces:**
- Consumes: Stage 1 `ResourcePolicy`, `ResourceSnapshot`, `Entity`, `EntityRevision`, `EntityMapping`, `Claim`, `ClaimEvidence`.
- Produces: `ImportAdapter` protocol, `ImportBundle`, `ImportRecordCounts`, `ImportWarning`, `ImportReport`, and `RedistributionPolicy`.

- [ ] **Step 1: Write failing contract tests**

```python
from pathlib import Path

from med_research.biomed.imports.contracts import ImportBundle, ImportReport
from med_research.biomed.models import ResourcePolicy


def test_import_bundle_requires_snapshot_and_checksum() -> None:
    policy = ResourcePolicy(
        resource_name="mondo",
        license_id="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        redistribution_policy="redistributable",
    )
    bundle = ImportBundle.from_artifact(
        policy=policy,
        artifact_path=Path("tests/fixtures/biomed/mondo/minimal.json"),
        upstream_version="2024-01-01",
    )
  assert bundle.snapshot.checksum
  assert bundle.snapshot.resource_name == "mondo"
  assert bundle.counts.entity_revisions >= 1


def test_import_report_records_warnings_and_fingerprint() -> None:
  report = ImportReport.empty("mondo")
  report.add_warning("unresolved_mapping", "OMIM:12345 has no exact Mondo join")
  dumped = report.to_dict()
  assert dumped["warnings"]
  assert dumped["fingerprint"]
```

- [ ] **Step 2: Run tests and verify the package is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/imports/test_contracts.py -q`

Expected: `ModuleNotFoundError: No module named 'med_research.biomed.imports'`.

- [ ] **Step 3: Implement contracts and staging models**

Define `RedistributionPolicy = Literal["redistributable", "user_supplied", "restricted"]`. Define frozen Pydantic models:

- `ImportRecordCounts` — entity, revision, mapping, claim, and evidence counts.
- `ImportWarning` — code, message, optional source record ID.
- `ImportBundle` — snapshot, entities, revisions, mappings, claims, evidence, counts, warnings; `from_artifact()` computes SHA-256 before parsing.
- `ImportReport` — snapshot ID, counts, warnings, rejected records, fingerprint, duration; `to_dict()` is JSON-safe.
- `ImportAdapter` protocol with `resource_name`, `supported_formats`, `parse(path, policy) -> ImportBundle`.

Reject `restricted` policies unless the adapter is explicitly configured for operator-supplied local artifacts.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/imports/test_contracts.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/imports tests/biomed/imports/test_contracts.py
git commit -m "feat: add biomedical import contracts"
```

### Task 2: Mondo Adapter and Minimal Fixture

**Files:**
- Create: `src/med_research/biomed/imports/mondo.py`
- Create: `tests/fixtures/biomed/mondo/minimal.json`
- Test: `tests/biomed/imports/test_mondo_adapter.py`

**Interfaces:**
- Consumes: `ImportAdapter`, `ImportBundle`.
- Produces: `MondoAdapter.parse(path, policy) -> ImportBundle` with condition entities, hierarchy `IS_A` claims, synonyms, obsolescence metadata, and published mappings.

- [ ] **Step 1: Write failing adapter tests**

```python
from pathlib import Path

from med_research.biomed.imports.mondo import MondoAdapter
from med_research.biomed.models import EntityType, MappingKind, Predicate


def test_mondo_fixture_imports_condition_and_hierarchy() -> None:
    bundle = MondoAdapter().parse(
        Path("tests/fixtures/biomed/mondo/minimal.json"),
        policy=mondo_policy(),
    )
    curies = {rev.primary_curie for rev in bundle.revisions}
    assert "MONDO:0007915" in curies
    predicates = {claim.predicate for claim in bundle.claims}
    assert Predicate.IS_A in predicates
    assert all(m.relation != MappingKind.EXACT or m.can_auto_join for m in bundle.mappings)
```

Build `mondo_policy()` in the test module using CC BY 4.0 metadata from the design.

- [ ] **Step 2: Run tests and verify adapter is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/imports/test_mondo_adapter.py -q`

Expected: import or parse failure.

- [ ] **Step 3: Implement Mondo adapter**

Create a minimal fixture containing at least:

- `MONDO:0007915` (systemic lupus erythematosus) with label, definition, and one child term.
- One `exact` cross-reference mapping to a second identifier.
- One obsolete term with `replaced_by`.

Parse Mondo JSON graph nodes into `EntityRevision` rows typed `EntityType.CONDITION`. Emit `IS_A` claims for `subClassOf` edges. Preserve mapping relation strings (`EXACT`, `CLOSE`, etc.) as `MappingKind` values. Never promote non-exact mappings to joinable status.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/imports/test_mondo_adapter.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/imports/mondo.py tests/fixtures/biomed/mondo tests/biomed/imports/test_mondo_adapter.py
git commit -m "feat: add mondo ontology import adapter"
```

### Task 3: HPO Ontology Adapter

**Files:**
- Create: `src/med_research/biomed/imports/hpo.py`
- Create: `tests/fixtures/biomed/hpo/minimal.json`
- Test: `tests/biomed/imports/test_hpo_adapter.py`

**Interfaces:**
- Consumes: `ImportAdapter`.
- Produces: `HpoOntologyAdapter.parse(path, policy) -> ImportBundle` with phenotype entities and `IS_A` hierarchy claims.

- [ ] **Step 1: Write failing adapter tests**

```python
def test_hpo_fixture_imports_phenotype_hierarchy() -> None:
    bundle = HpoOntologyAdapter().parse(
        Path("tests/fixtures/biomed/hpo/minimal.json"),
        policy=hpo_policy(),
    )
    assert any(rev.entity_type == EntityType.PHENOTYPE for rev in bundle.revisions)
    child = next(c for c in bundle.claims if c.predicate == Predicate.IS_A)
    assert child.subject_curie != child.object_curie
```

- [ ] **Step 2: Run tests and verify adapter is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/imports/test_hpo_adapter.py -q`

Expected: import failure.

- [ ] **Step 3: Implement HPO ontology adapter**

Fixture must include at least three terms with `is_a` links, synonyms, and one obsolete term. Map HP identifiers to `EntityType.PHENOTYPE`. Store the upstream release version from fixture metadata, not a hard-coded vocabulary date.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/imports/test_hpo_adapter.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/imports/hpo.py tests/fixtures/biomed/hpo tests/biomed/imports/test_hpo_adapter.py
git commit -m "feat: add hpo ontology import adapter"
```

### Task 4: HPO Annotation Adapter

**Files:**
- Create: `src/med_research/biomed/imports/hpoa.py`
- Create: `tests/fixtures/biomed/hpoa/minimal.tsv`
- Test: `tests/biomed/imports/test_hpoa_adapter.py`

**Interfaces:**
- Consumes: Mondo exact mappings from a previously imported or co-imported bundle.
- Produces: `HpoAnnotationAdapter.parse(path, policy, *, mondo_mappings) -> ImportBundle` with `HAS_PHENOTYPE` claims, evidence rows, and qualifier preservation.

- [ ] **Step 1: Write failing annotation tests**

```python
def test_hpoa_preserves_frequency_and_negation() -> None:
    bundle = HpoAnnotationAdapter().parse(
        Path("tests/fixtures/biomed/hpoa/minimal.tsv"),
        policy=hpoa_policy(),
        mondo_mappings={"OMIM:152700": "MONDO:0007915"},
    )
    claim = next(c for c in bundle.claims if c.predicate == Predicate.HAS_PHENOTYPE)
    assert claim.qualifiers.get("frequency") == "Very frequent"
    assert claim.qualifiers.get("negated") is False
    evidence = bundle.evidence[0]
    assert evidence.direction in {EvidenceDirection.SUPPORTING, EvidenceDirection.CONTRADICTORY}


def test_hpoa_unresolved_disease_is_reported_not_joined() -> None:
    bundle = HpoAnnotationAdapter().parse(
        Path("tests/fixtures/biomed/hpoa/minimal.tsv"),
        policy=hpoa_policy(),
        mondo_mappings={},
    )
    codes = {warning.code for warning in bundle.warnings}
    assert "unresolved_disease_mapping" in codes
```

- [ ] **Step 2: Run tests and verify adapter is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/imports/test_hpoa_adapter.py -q`

Expected: import failure.

- [ ] **Step 3: Implement HPO annotation adapter**

Parse the HPO annotation TSV header used by the pinned fixture. Join disease identifiers to Mondo only through the supplied exact mapping table. Retain frequency, onset, sex, evidence code, biocuration, and negation qualifiers. Emit unresolved-disease warnings instead of label matching.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/imports/test_hpoa_adapter.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/imports/hpoa.py tests/fixtures/biomed/hpoa tests/biomed/imports/test_hpoa_adapter.py
git commit -m "feat: add hpo annotation import adapter"
```

### Task 5: Import Service, Rollback, and Activation

**Files:**
- Create: `src/med_research/biomed/imports/service.py`
- Modify: `tests/biomed/conftest.py`
- Test: `tests/biomed/imports/test_import_service.py`

**Interfaces:**
- Consumes: `BiomedicalRepository`, `ImportBundle`.
- Produces: `ImportService.import_bundle(bundle) -> ImportReport` with atomic commit, idempotent re-import, checksum conflict detection, and post-import snapshot activation.

- [ ] **Step 1: Write failing service tests**

```python
def test_import_is_idempotent_and_activates_snapshot(repository, mondo_bundle) -> None:
    service = ImportService(repository)
    first = service.import_bundle(mondo_bundle)
    second = service.import_bundle(mondo_bundle)
    assert first.snapshot_id == second.snapshot_id
    assert repository.get_active_snapshot("mondo") is not None


def test_checksum_conflict_rolls_back(repository, mondo_bundle, tmp_path) -> None:
    service = ImportService(repository)
    service.import_bundle(mondo_bundle)
    tampered = mondo_bundle.model_copy(
        update={"snapshot": mondo_bundle.snapshot.model_copy(update={"checksum": "deadbeef"})}
    )
    with pytest.raises(SnapshotConflictError):
        service.import_bundle(tampered)
    assert repository.get_active_snapshot("mondo").checksum == mondo_bundle.snapshot.checksum


def test_failed_validation_leaves_previous_active_snapshot(repository, mondo_bundle, monkeypatch) -> None:
    service = ImportService(repository)
    service.import_bundle(mondo_bundle)
    monkeypatch.setattr(service, "_validate_bundle", lambda _b: (_ for _ in ()).throw(BiomedicalValidationError("bad")))
    with pytest.raises(BiomedicalValidationError):
        service.import_bundle(mondo_bundle)
    assert repository.get_active_snapshot("mondo") is not None
```

- [ ] **Step 2: Run tests and verify service is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/imports/test_import_service.py -q`

Expected: import or attribute failure.

- [ ] **Step 3: Implement ImportService**

Wrap all writes in `repository.transaction()`. Validate foreign references, predicate shapes, and required metadata before insert. Upsert snapshot, entities, revisions, mappings, claims, and evidence through repository methods from Stage 1. Activate the snapshot only after a successful commit. Return an `ImportReport` with deterministic fingerprint over counts, warnings, and snapshot ID.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/imports/test_import_service.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/imports/service.py tests/biomed/conftest.py tests/biomed/imports/test_import_service.py
git commit -m "feat: add atomic biomedical import service"
```

### Task 6: CLI, Makefile, Documentation, and Stage 2 Gate

**Files:**
- Modify: `src/med_research/cli.py`
- Modify: `Makefile`
- Modify: `docs/api-reference.md`
- Test: `tests/biomed/imports/test_cli.py`

**Interfaces:**
- Consumes: `ImportService`, adapters, `BIOMEDICAL_DB_PATH`.
- Produces: `biomed import mondo|hp|hpoa --artifact PATH [--db PATH]`, `biomed snapshots list`, and Make target `biomed-import-fixtures`.

- [ ] **Step 1: Write failing CLI tests**

```python
def test_biomed_import_mondo_from_fixture(tmp_path: Path) -> None:
    db = tmp_path / "biomedical.sqlite3"
    artifact = Path("tests/fixtures/biomed/mondo/minimal.json")
    result = run_cli("biomed", "import", "mondo", "--artifact", str(artifact), "--db", str(db))
    assert result.exit_code == 0
    assert "MONDO:0007915" in result.output
```

- [ ] **Step 2: Run test and verify command is unknown**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/imports/test_cli.py -q`

Expected: parser rejects `biomed import`.

- [ ] **Step 3: Wire CLI and documentation**

Add `biomed` subcommands:

- `import mondo|hp|hpoa --artifact PATH [--db PATH] [--activate/--no-activate]`
- `snapshots list [--resource NAME] [--db PATH]`

Default `--db` to `BIOMEDICAL_DB_PATH`. Log snapshot ID, checksum, counts, and warnings. Document license boundaries, operator-supplied artifacts, and separation from the Evidence Workspace database.

Add Make target:

```makefile
biomed-import-fixtures:  ## Import pinned ontology fixtures into the local biomedical store
	python -m med_research.cli biomed import mondo --artifact tests/fixtures/biomed/mondo/minimal.json
	python -m med_research.cli biomed import hp --artifact tests/fixtures/biomed/hpo/minimal.json
	python -m med_research.cli biomed import hpoa --artifact tests/fixtures/biomed/hpoa/minimal.tsv
```

- [ ] **Step 4: Run the Stage 2 gate**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed -q`

Expected: all biomedical tests pass.

Run: `.\.venv\Scripts\python.exe -m pytest tests -m "unit and not network" -q --tb=short`

Expected: existing offline unit suite passes.

Run: `.\.venv\Scripts\python.exe -m ruff check src/med_research/biomed tests/biomed`

Run: `.\.venv\Scripts\python.exe -m mypy src/med_research/biomed`

Run: `git diff --check`

Expected: every command exits `0`.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/cli.py Makefile docs/api-reference.md tests/biomed/imports/test_cli.py
git commit -m "feat: expose biomedical ontology import cli"
```
