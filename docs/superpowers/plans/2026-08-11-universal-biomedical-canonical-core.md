# Universal Biomedical Canonical Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, versioned SQLite canonical store for biomedical entities, claims, evidence, resource snapshots, and research runs.

**Architecture:** Create a new `med_research.biomed` package isolated from the evidence-workspace database. Pydantic models enforce domain rules, repositories own SQL and transactions, and NetworkX receives bounded projections only.

**Tech Stack:** Python 3.11+, Pydantic 2, SQLite 3, NetworkX 3, pytest, Ruff, mypy.

## Global Constraints

- Preserve all seven disease modules and current `/api/*` contracts.
- Store public biomedical knowledge only; do not accept patient, case, or PHI data.
- Identifiers and fingerprints are deterministic for identical normalized input.
- Claims and evidence are append-only; corrections use `supersedes_claim_id`.
- ResearchRun transitions only `pending -> running -> completed|failed`; terminal rows are immutable.
- Only exact mappings participate in joins; SQLite foreign keys are enabled on every connection.
- Preserve unrelated working-tree changes; stage only files named by the active task.

---

### Task 1: Domain Types and Deterministic Identifiers

**Files:**
- Create: `src/med_research/biomed/__init__.py`
- Create: `src/med_research/biomed/models.py`
- Create: `src/med_research/biomed/identifiers.py`
- Create: `src/med_research/biomed/errors.py`
- Test: `tests/biomed/test_models.py`
- Test: `tests/biomed/test_identifiers.py`

**Interfaces:**
- Consumes: CURIE strings and JSON-compatible qualifiers.
- Produces: `normalize_curie`, `entity_uuid`, `snapshot_uuid`, `claim_uuid`, `fingerprint_json`, and the immutable domain models used by every stage.

- [ ] **Step 1: Write failing tests**

```python
from med_research.biomed.identifiers import claim_uuid, entity_uuid, normalize_curie
from med_research.biomed.models import EntityType, MappingKind, Predicate


def test_normalization_and_ids_are_stable() -> None:
    assert normalize_curie(" mondo:0007915 ") == "MONDO:0007915"
    assert entity_uuid(EntityType.CONDITION, "mondo:0007915") == entity_uuid(
        EntityType.CONDITION, "MONDO:0007915"
    )
    left = claim_uuid("MONDO:0007915", Predicate.HAS_PHENOTYPE, "HP:0001945", {"negated": False})
    right = claim_uuid("mondo:0007915", Predicate.HAS_PHENOTYPE, "hp:0001945", {"negated": False})
    assert left == right


def test_only_exact_mapping_can_auto_join() -> None:
    assert MappingKind.EXACT.can_auto_join is True
    assert MappingKind.CLOSE.can_auto_join is False
```

- [ ] **Step 2: Run tests and verify the package is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/test_identifiers.py tests/biomed/test_models.py -q`

Expected: `ModuleNotFoundError: No module named 'med_research.biomed'`.

- [ ] **Step 3: Implement models and identifiers**

Define string enums: `EntityType(condition, phenotype, gene, pathway, intervention, biomarker, measurement, exposure, outcome)`, `MappingKind(exact, close, broad, narrow)`, `Predicate(IS_A, HAS_PHENOTYPE, ASSOCIATED_WITH_GENE, INVOLVES_PATHWAY, TREATED_BY, HAS_BIOMARKER, HAS_MEASUREMENT, ASSOCIATED_WITH_EXPOSURE, HAS_OUTCOME)`, `EvidenceDirection(supporting, contradictory)`, and `RunStatus(pending, running, completed, failed)`. Define frozen Pydantic models `ResourcePolicy`, `ResourceSnapshot`, `Entity`, `EntityRevision`, `EntityMapping`, `Claim`, `ClaimEvidence`, `ResearchRunCreate`, and `ResearchRun` with the fields approved in the design.

```python
BIOMED_NAMESPACE = UUID("b38db2a8-67eb-5f5f-9f6d-742947426959")
_CURIE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*:[^\s:][^\s]*$")


def normalize_curie(value: str) -> str:
    normalized = value.strip()
    if not _CURIE.fullmatch(normalized):
        raise ValueError(f"Invalid CURIE: {value!r}")
    prefix, local = normalized.split(":", 1)
    return f"{prefix.upper()}:{local}"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def entity_uuid(entity_type: EntityType, curie: str) -> UUID:
    return uuid5(BIOMED_NAMESPACE, f"entity|{entity_type.value}|{normalize_curie(curie)}")


def claim_uuid(subject: str, predicate: Predicate, object_: str, qualifiers: Mapping[str, Any]) -> UUID:
    value = {"subject": normalize_curie(subject), "predicate": predicate.value,
             "object": normalize_curie(object_), "qualifiers": dict(qualifiers)}
    return uuid5(BIOMED_NAMESPACE, f"claim|{canonical_json(value)}")
```

Add typed errors `BiomedicalError`, `BiomedicalValidationError`, `SnapshotConflictError`, and `RunTransitionError` in `errors.py`.

- [ ] **Step 4: Run tests and static checks**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/test_identifiers.py tests/biomed/test_models.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed tests/biomed/test_models.py tests/biomed/test_identifiers.py
git commit -m "feat: add canonical biomedical domain types"
```

### Task 2: SQLite Schema and Migration Runner

**Files:**
- Create: `src/med_research/biomed/schema.py`
- Create: `src/med_research/biomed/database.py`
- Test: `tests/biomed/test_database.py`

**Interfaces:**
- Consumes: a database `Path`.
- Produces: `BiomedicalDatabase.connect()`, `initialize()`, `transaction()`, and `SCHEMA_VERSION = 1`.

- [ ] **Step 1: Write failing schema tests**

```python
def test_initialize_is_idempotent_and_enables_foreign_keys(tmp_path: Path) -> None:
    db = BiomedicalDatabase(tmp_path / "biomedical.sqlite3")
    db.initialize()
    db.initialize()
    with db.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        names = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert {"resource_snapshots", "entities", "claims", "claim_evidence", "research_runs"} <= names
```

- [ ] **Step 2: Run the test and verify `BiomedicalDatabase` is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/test_database.py -q`

Expected: import failure for `med_research.biomed.database`.

- [ ] **Step 3: Implement schema version 1**

Create tables `resource_snapshots`, `active_snapshots`, `entities`, `entity_revisions`, `entity_names`, `entity_mappings`, `claims`, `claim_evidence`, `research_runs`, and `research_run_snapshots`. Use the exact column contract from the design: UUIDs as text primary keys; JSON as canonical text; booleans with `CHECK IN (0,1)`; mapping and direction check constraints; foreign keys for every reference; unique keys for snapshot `(resource_name, version, checksum)`, entity `primary_curie`, evidence `(claim_id, snapshot_id, direction, source_record_id)`, and run `fingerprint`.

```python
class BiomedicalDatabase:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as connection:
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
```

Add indexes for revision/name search, subject/object predicate lookup, and evidence direction. Set `PRAGMA user_version = 1` only after all DDL succeeds.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/test_database.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/schema.py src/med_research/biomed/database.py tests/biomed/test_database.py
git commit -m "feat: add biomedical sqlite schema"
```

### Task 3: Snapshot, Entity, and Mapping Repository

**Files:**
- Create: `src/med_research/biomed/repository.py`
- Create: `tests/biomed/conftest.py`
- Test: `tests/biomed/test_repository_entities.py`

**Interfaces:**
- Consumes: Task 1 models and Task 2 database.
- Produces: `BiomedicalRepository.initialize`, `transaction`, `upsert_snapshot`, `activate_snapshot`, `get_active_snapshot`, `upsert_entity`, `add_entity_revision`, `add_entity_mapping`, `resolve_exact_curie`, `get_entity`, and `search_entities`.

- [ ] **Step 1: Write failing idempotency and mapping tests**

```python
def test_entity_writes_are_idempotent(repository, mondo_snapshot, sle_entity) -> None:
    repository.upsert_snapshot(mondo_snapshot)
    repository.upsert_snapshot(mondo_snapshot)
    repository.upsert_entity(sle_entity)
    repository.upsert_entity(sle_entity)
    repository.activate_snapshot("mondo", mondo_snapshot.id)
    assert repository.get_active_snapshot("mondo") == mondo_snapshot
    assert repository.get_entity("MONDO:0007915").entity == sle_entity


def test_non_exact_mapping_never_resolves(repository, exact_mapping, close_mapping) -> None:
    repository.add_entity_mapping(exact_mapping)
    repository.add_entity_mapping(close_mapping)
    assert repository.resolve_exact_curie(exact_mapping.object_curie) == exact_mapping.subject_curie
    assert repository.resolve_exact_curie(close_mapping.object_curie) is None
```

- [ ] **Step 2: Run tests and verify repository methods are missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/test_repository_entities.py -q`

Expected: import or attribute failures for `BiomedicalRepository`.

- [ ] **Step 3: Implement repository operations**

```python
@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class BiomedicalRepository:
    def __init__(self, path: Path):
        self.database = BiomedicalDatabase(path)

    def initialize(self) -> None:
        self.database.initialize()

    def transaction(self) -> AbstractContextManager[sqlite3.Connection]:
        return self.database.transaction()
```

Use named SQL parameters and `canonical_json`. Reject a resource/version with a different checksum using `SnapshotConflictError`. Reject a primary CURIE assigned to a different entity type. Search labels and synonyms case-insensitively with `limit` in `1..200` and `offset >= 0`. Return the active revision plus all mappings; never promote close/broad/narrow mappings.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/test_repository_entities.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/repository.py tests/biomed/conftest.py tests/biomed/test_repository_entities.py
git commit -m "feat: persist biomedical snapshots and entities"
```

### Task 4: Claims, Evidence, and Bounded Graph Projection

**Files:**
- Modify: `src/med_research/biomed/repository.py`
- Create: `src/med_research/biomed/graph.py`
- Test: `tests/biomed/test_repository_claims.py`
- Test: `tests/biomed/test_graph_projection.py`

**Interfaces:**
- Consumes: stored entities and snapshots.
- Produces: `add_claim`, `add_claim_evidence`, `list_claims`, `claim_is_current`, and `project_claim_graph(repository, root_curie, max_hops=2, max_nodes=500)`.

- [ ] **Step 1: Write failing claim tests**

```python
def test_support_and_contradiction_remain_separate(repository, claim, support, contradiction) -> None:
    repository.add_claim(claim)
    repository.add_claim_evidence(support)
    repository.add_claim_evidence(contradiction)
    view = repository.list_claims("MONDO:0007915")[0]
    assert {item.direction for item in view.evidence} == {
        EvidenceDirection.SUPPORTING, EvidenceDirection.CONTRADICTORY
    }


def test_projection_rejects_unbounded_request(repository) -> None:
    with pytest.raises(ValueError, match="max_hops"):
        project_claim_graph(repository, "MONDO:0007915", max_hops=4)
```

- [ ] **Step 2: Run tests and verify methods are missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/test_repository_claims.py tests/biomed/test_graph_projection.py -q`

Expected: failures for missing claim and projection functions.

- [ ] **Step 3: Implement append-only persistence and projection**

Repeated identical writes return stored records; changed payloads for an existing ID raise `BiomedicalValidationError`. `claim_is_current` is false when superseded or when no evidence snapshot is active. `list_claims` never merges confidence across evidence directions.

```python
def project_claim_graph(repository, root_curie: str, max_hops: int = 2,
                        max_nodes: int = 500) -> nx.MultiDiGraph:
    if not 0 <= max_hops <= 3:
        raise ValueError("max_hops must be between 0 and 3")
    if not 1 <= max_nodes <= 2000:
        raise ValueError("max_nodes must be between 1 and 2000")
    graph = nx.MultiDiGraph()
    frontier = {normalize_curie(root_curie)}
    visited: set[str] = set()
    for _depth in range(max_hops + 1):
        next_frontier: set[str] = set()
        for curie in sorted(frontier):
            if curie in visited or graph.number_of_nodes() >= max_nodes:
                continue
            visited.add(curie)
            for claim in repository.list_claims(curie):
                if claim.object_curie not in graph and graph.number_of_nodes() >= max_nodes:
                    continue
                graph.add_edge(curie, claim.object_curie, key=str(claim.claim.id),
                               type=claim.claim.predicate.value)
                next_frontier.add(claim.object_curie)
        frontier = next_frontier
    return graph
```

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/test_repository_claims.py tests/biomed/test_graph_projection.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/repository.py src/med_research/biomed/graph.py tests/biomed/test_repository_claims.py tests/biomed/test_graph_projection.py
git commit -m "feat: add immutable claims and graph projection"
```

### Task 5: ResearchRun Lifecycle

**Files:**
- Modify: `src/med_research/biomed/repository.py`
- Test: `tests/biomed/test_research_runs.py`

**Interfaces:**
- Consumes: `ResearchRunCreate`, snapshot IDs, and claim IDs.
- Produces: `create_research_run`, `get_research_run`, `transition_research_run`, `list_research_runs`.

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_terminal_run_is_immutable(repository, run_create) -> None:
    pending = repository.create_research_run(run_create)
    running = repository.transition_research_run(pending.id, RunStatus.RUNNING)
    completed = repository.transition_research_run(
        running.id, RunStatus.COMPLETED, result={"score": 0.75}, warnings=[]
    )
    assert completed.result == {"score": 0.75}
    with pytest.raises(RunTransitionError, match="terminal"):
        repository.transition_research_run(completed.id, RunStatus.FAILED, warnings=["changed"])
```

- [ ] **Step 2: Run tests and verify lifecycle methods are missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/test_research_runs.py -q`

Expected: attribute failures for ResearchRun methods.

- [ ] **Step 3: Implement deterministic creation and guarded transitions**

```python
_TRANSITIONS = {
    RunStatus.PENDING: {RunStatus.RUNNING},
    RunStatus.RUNNING: {RunStatus.COMPLETED, RunStatus.FAILED},
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
}
```

Fingerprint sorted snapshots and claims plus run type, parent, algorithm ID/version, software version, and parameters. Derive the run UUID from the fingerprint. Identical specs return the existing run. Completion requires a result; failure requires warnings. Set `started_at` and `finished_at` only on their corresponding transitions.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/test_research_runs.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/repository.py tests/biomed/test_research_runs.py
git commit -m "feat: persist immutable biomedical research runs"
```

### Task 6: Configuration, CLI, Documentation, and Verification

**Files:**
- Modify: `src/med_research/web/config.py`
- Modify: `src/med_research/cli.py`
- Modify: `Makefile`
- Modify: `docs/api-reference.md`
- Test: `tests/biomed/test_cli.py`

**Interfaces:**
- Consumes: `BiomedicalRepository`.
- Produces: `BIOMEDICAL_DB_PATH`, `biomed init --db PATH`, and Make target `biomed-init`.

- [ ] **Step 1: Write failing CLI test**

```python
def test_biomed_init_creates_store(tmp_path: Path) -> None:
    database = tmp_path / "biomedical.sqlite3"
    result = run_cli("biomed", "init", "--db", str(database))
    assert result.exit_code == 0
    assert database.exists()
    assert "schema version 1" in result.output.lower()
```

- [ ] **Step 2: Run test and verify the command is unknown**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/test_cli.py -q`

Expected: parser rejects `biomed`.

- [ ] **Step 3: Wire configuration and CLI**

```python
BIOMEDICAL_DB_PATH = Path(
    os.environ.get("BIOMEDICAL_DB_PATH", str(PROJECT_ROOT.parent / "data" / "biomedical.sqlite3"))
)
```

Add required `biomed init`, `--db`, and a handler that initializes the repository and logs the absolute path and schema version. Add Make target `biomed-init` executing `python -m med_research.cli biomed init`. Document the separate stores, environment variable, immutability, and research-only boundary.

- [ ] **Step 4: Run the Stage 1 gate**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed -q`

Expected: all Stage 1 tests pass.

Run: `.\.venv\Scripts\python.exe -m pytest tests -m "unit and not network" -q --tb=short`

Expected: existing offline unit suite passes.

Run: `.\.venv\Scripts\python.exe -m ruff check src/med_research/biomed tests/biomed`

Run: `.\.venv\Scripts\python.exe -m mypy src/med_research/biomed`

Run: `git diff --check`

Expected: every command exits `0` and `git diff --check` prints nothing.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/web/config.py src/med_research/cli.py Makefile docs/api-reference.md tests/biomed/test_cli.py
git commit -m "feat: expose biomedical store initialization"
```

