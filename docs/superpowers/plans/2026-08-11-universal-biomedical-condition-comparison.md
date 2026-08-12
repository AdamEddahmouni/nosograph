# Universal Biomedical Condition Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compare two conditions using transparent HPO-aware phenotype similarity, biological overlap scores, coverage reporting, and immutable `ResearchRun` persistence exposed through API, CLI, and dashboard views.

**Architecture:** Add `med_research.biomed.comparison` with fingerprint construction, information-content computation over the active HPO annotation snapshot, a versioned similarity algorithm, and `ConditionComparisonService` that writes terminal comparison runs through the Stage 1 repository. Results remain research hypotheses, not diagnoses.

**Tech Stack:** Python 3.11+, Pydantic 2, NetworkX 3 (bounded in-memory HPO ancestor graphs only), FastAPI, pytest, Ruff, mypy.

**Depends on:** Stages 1–4 complete, especially imported HPO ontology, HPO annotations, and `/api/v1` condition routes.

## Global Constraints

- Preserve all seven disease modules and existing `/api/*` contracts.
- Use research language only; never emit diagnosis or treatment recommendations.
- Missing dimensions renormalize weights; they do not count as zero biological similarity.
- Negative phenotypes are compared separately from positive phenotypes.
- Biomarkers are visible in fingerprints and explanations but excluded from default v1 overall weighting.
- Comparisons with inadequate comparable data return structured `insufficient_data` without a numeric overall score.
- Algorithm ID, version, parameters, snapshots, and claim-set fingerprint are stored in every comparison `ResearchRun`.
- Preserve unrelated working-tree changes; stage only files named by the active task.

## Algorithm v1 Defaults

| Dimension | Default weight | Method |
|---|---|---|
| Phenotype | 0.55 | HPO ancestor best-match average with information content |
| Gene | 0.20 | Jaccard overlap on canonical gene CURIEs/IDs |
| Pathway | 0.15 | Jaccard overlap |
| Intervention | 0.10 | Jaccard overlap |
| Biomarker | 0.00 | Reported only in v1 |

`SimilarityConfig` must validate custom weights sum to `1.0` before missing-dimension renormalization.

---

### Task 1: Fingerprint Builder

**Files:**
- Create: `src/med_research/biomed/comparison/__init__.py`
- Create: `src/med_research/biomed/comparison/fingerprint.py`
- Create: `src/med_research/biomed/comparison/models.py`
- Test: `tests/biomed/comparison/test_fingerprint.py`

**Interfaces:**
- Consumes: `BiomedicalRepository`, active snapshot IDs, condition CURIE.
- Produces: `ConditionFingerprint` with positive/negative phenotypes, genes, pathways, interventions, biomarkers, coverage map, and claim-set fingerprint.

- [ ] **Step 1: Write failing fingerprint tests**

```python
def test_fingerprint_separates_positive_and_negative_phenotypes(biomed_repository) -> None:
    fp = build_fingerprint(biomed_repository, "MONDO:0007915")
    assert fp.positive_phenotypes
    assert isinstance(fp.negative_phenotypes, list)
    assert fp.claim_set_fingerprint


def test_fingerprint_records_coverage_per_dimension(biomed_repository) -> None:
    fp = build_fingerprint(biomed_repository, "MONDO:0008390")
    assert "phenotype" in fp.coverage
    assert "gene" in fp.coverage
```

- [ ] **Step 2: Run tests and verify package is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/comparison/test_fingerprint.py -q`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement fingerprint builder**

Select claims from active snapshots only. Group `HAS_PHENOTYPE` by qualifier `negated`. Collect genes, pathways, interventions, and biomarkers from approved predicates. Record snapshot IDs used per dimension and a deterministic `claim_set_fingerprint`.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/comparison/test_fingerprint.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/comparison tests/biomed/comparison/test_fingerprint.py
git commit -m "feat: add condition fingerprint builder"
```

### Task 2: HPO Information Content and Ancestor Graph

**Files:**
- Create: `src/med_research/biomed/comparison/hpo.py`
- Test: `tests/biomed/comparison/test_hpo_ic.py`

**Interfaces:**
- Consumes: active HPO ontology and annotation snapshots.
- Produces: `build_hpo_ancestor_graph(repository) -> nx.DiGraph`, `information_content(term) -> float`.

- [ ] **Step 1: Write failing IC tests**

```python
def test_information_content_decreases_toward_root(biomed_repository) -> None:
    graph = build_hpo_ancestor_graph(biomed_repository)
    root_ic = information_content(graph, "HP:0000118")  # Phenotypic abnormality
    leaf_ic = information_content(graph, "HP:0001945")  # Fever
    assert leaf_ic > root_ic


def test_ancestor_relationship_is_reflexive_only_at_same_node(biomed_repository) -> None:
    graph = build_hpo_ancestor_graph(biomed_repository)
    assert "HP:0001945" in nx.ancestors(graph, "HP:0001945") or graph.has_node("HP:0001945")
```

- [ ] **Step 2: Run tests and verify module is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/comparison/test_hpo_ic.py -q`

Expected: import failure.

- [ ] **Step 3: Implement HPO helpers**

Build a bounded DAG from `IS_A` claims in the active HPO snapshot. Compute IC as `-ln(annotated_conditions_at_or_below / all_annotated_conditions)` using the active HPOA snapshot corpus. Cache per repository connection; do not persist IC tables in v1.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/comparison/test_hpo_ic.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/comparison/hpo.py tests/biomed/comparison/test_hpo_ic.py
git commit -m "feat: add hpo information content helpers"
```

### Task 3: Similarity Algorithm v1

**Files:**
- Create: `src/med_research/biomed/comparison/algorithm.py`
- Test: `tests/biomed/comparison/test_algorithm.py`

**Interfaces:**
- Consumes: two `ConditionFingerprint` values, `SimilarityConfig`, HPO graph/IC helpers.
- Produces: `ComparisonComponents`, `ComparisonCoverage`, `ComparisonResult` with `status: comparable | insufficient_data`.

- [ ] **Step 1: Write failing similarity invariant tests**

```python
def test_identical_fingerprints_score_maximally() -> None:
    fp = sample_fingerprint()
    result = compare_fingerprints(fp, fp, SimilarityConfig.v1_default(), hpo_context())
    assert result.status == "comparable"
    assert result.overall_score == pytest.approx(1.0)


def test_disjoint_phenotypes_do_not_false_overlap() -> None:
    left = fingerprint_with_phenotypes(["HP:0001945"])
    right = fingerprint_with_phenotypes(["HP:0001250"])
    result = compare_fingerprints(left, right, SimilarityConfig.v1_default(), hpo_context())
    assert result.components.phenotype < 0.2


def test_missing_dimension_renormalizes_weights() -> None:
    left = fingerprint_with_genes_only(["HGNC:1100"])
    right = fingerprint_with_genes_only(["HGNC:1100"])
    result = compare_fingerprints(left, right, SimilarityConfig.v1_default(), hpo_context())
    assert result.effective_weights["gene"] == pytest.approx(1.0)


def test_inadequate_data_returns_insufficient_data() -> None:
    left = empty_fingerprint()
    right = empty_fingerprint()
    result = compare_fingerprints(left, right, SimilarityConfig.v1_default(), hpo_context())
    assert result.status == "insufficient_data"
    assert result.overall_score is None
```

- [ ] **Step 2: Run tests and verify algorithm is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/comparison/test_algorithm.py -q`

Expected: import failure.

- [ ] **Step 3: Implement algorithm**

Phenotype similarity: best-match average over positive phenotypes using ancestor Jaccard/IC blend defined in the design. Compare negative sets separately and include distinguishing entities in the explanation payload. Gene/pathway/intervention dimensions use Jaccard overlap on canonical IDs. Renormalize weights across dimensions present on both sides. Populate shared and distinguishing entity lists.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/comparison/test_algorithm.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/comparison/algorithm.py tests/biomed/comparison/test_algorithm.py
git commit -m "feat: add condition similarity algorithm v1"
```

### Task 4: Comparison Service and ResearchRun Persistence

**Files:**
- Create: `src/med_research/biomed/comparison/service.py`
- Test: `tests/biomed/comparison/test_service.py`

**Interfaces:**
- Consumes: `BiomedicalRepository`, `SimilarityConfig`.
- Produces: `ConditionComparisonService.compare(left_curie, right_curie, config) -> ComparisonResult` with persisted `ResearchRun`.

- [ ] **Step 1: Write failing service tests**

```python
def test_compare_persists_research_run(biomed_repository) -> None:
    service = ConditionComparisonService(biomed_repository)
    result = service.compare("MONDO:0007915", "MONDO:0008390", SimilarityConfig.v1_default())
    run = biomed_repository.get_research_run(result.run_id)
    assert run.status == RunStatus.COMPLETED
    assert run.result["overall_score"] == result.overall_score
    assert run.fingerprint


def test_replay_with_same_inputs_returns_same_run_id(biomed_repository) -> None:
    service = ConditionComparisonService(biomed_repository)
    config = SimilarityConfig.v1_default()
    first = service.compare("MONDO:0007915", "MONDO:0008390", config)
    second = service.compare("MONDO:0007915", "MONDO:0008390", config)
    assert first.run_id == second.run_id
```

- [ ] **Step 2: Run tests and verify service is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/comparison/test_service.py -q`

Expected: import failure.

- [ ] **Step 3: Implement service**

Create a `ResearchRunCreate` with run type `condition_comparison`, algorithm ID `condition-similarity`, version `1.0.0`, active snapshot IDs, sorted claim-set fingerprint, and normalized parameters. Transition `pending -> running -> completed|failed`. Store component scores, effective weights, shared/distinguishing entities, coverage, and disclaimer text in `result`.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/comparison/test_service.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/biomed/comparison/service.py tests/biomed/comparison/test_service.py
git commit -m "feat: persist condition comparison research runs"
```

### Task 5: API and CLI Endpoints

**Files:**
- Modify: `src/med_research/web/routers/universal.py`
- Modify: `src/med_research/web/models/universal.py`
- Modify: `src/med_research/cli.py`
- Test: `tests/web/test_universal_comparison_api.py`
- Test: `tests/biomed/comparison/test_cli.py`

**Interfaces:**
- Produces:
  - `POST /api/v1/comparisons` — compare two condition CURIEs.
  - `GET /api/v1/comparisons/{run_id}` — fetch persisted run.
  - `biomed compare --left CURIE --right CURIE [--weights ...] [--db PATH]`

- [ ] **Step 1: Write failing API and CLI tests**

```python
def test_compare_endpoint_returns_components_and_disclaimer(client, seeded_biomed_db) -> None:
    response = client.post(
        "/api/v1/comparisons",
        json={"left_curie": "MONDO:0007915", "right_curie": "MONDO:0008390"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["disclaimer"]["text"]
    assert "components" in body


def test_biomed_compare_cli_writes_run_id(tmp_path: Path) -> None:
    db = tmp_path / "biomedical.sqlite3"
    seed_biomed_db(db)
    result = run_cli(
        "biomed", "compare",
        "--left", "MONDO:0007915",
        "--right", "MONDO:0008390",
        "--db", str(db),
    )
    assert result.exit_code == 0
    assert "run_id" in result.output.lower()
```

- [ ] **Step 2: Run tests and verify endpoints are missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/web/test_universal_comparison_api.py tests/biomed/comparison/test_cli.py -q`

Expected: 404 or parser failure.

- [ ] **Step 3: Implement API and CLI**

Validate CURIEs, optional custom weights, and database path. Return `insufficient_data` with HTTP 200 and explicit missing dimensions rather than fabricating a score. Document endpoints in `docs/api-reference.md`.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/web/test_universal_comparison_api.py tests/biomed/comparison/test_cli.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/web/routers/universal.py src/med_research/web/models/universal.py src/med_research/cli.py tests/web/test_universal_comparison_api.py tests/biomed/comparison/test_cli.py docs/api-reference.md
git commit -m "feat: expose condition comparison api and cli"
```

### Task 6: Dashboard Comparison UI and Stage 5 Gate

**Files:**
- Modify: `src/med_research/web/static/index.html`
- Modify: `src/med_research/web/static/js/dashboard.js`
- Modify: `src/med_research/web/static/css/dashboard.css`
- Test: `tests/web/test_universal_comparison_dashboard.py`

**Interfaces:**
- Produces: side-by-side condition picker, comparison result panel, component score bars, shared/distinguishing entity lists, coverage badges, and run replay link.

- [ ] **Step 1: Write failing dashboard contract tests**

Assert presence of `compareConditions`, `renderComparisonResult`, and visible research-only disclaimer in the comparison panel.

- [ ] **Step 2: Run tests and verify failures**

Run: `.\.venv\Scripts\python.exe -m pytest tests/web/test_universal_comparison_dashboard.py -q`

Expected: missing functions or markup.

- [ ] **Step 3: Implement dashboard comparison UI**

Wire two CURIE inputs to `POST /api/v1/comparisons`. Render `insufficient_data` as an informational state without numeric score. Show effective weights and snapshot IDs used. Provide keyboard-accessible controls and loading state.

- [ ] **Step 4: Run the Stage 5 / program gate**

Run: `.\.venv\Scripts\python.exe -m pytest tests/biomed/comparison tests/web/test_universal_comparison_api.py tests/web/test_universal_comparison_dashboard.py -q`

Run: `.\.venv\Scripts\python.exe -m pytest tests -m "not slow and not network" -q --tb=short`

Run: `.\.venv\Scripts\python.exe -m ruff check src tests`

Run: `.\.venv\Scripts\python.exe -m mypy src/med_research/biomed src/med_research/web/models/universal.py src/med_research/web/routers/universal.py src/med_research/web/services/universal_service.py`

Run: `.\.venv\Scripts\python.exe scripts/check_imports.py`

Run: `.\.venv\Scripts\python.exe -m compileall -q src/med_research`

Run: `.\.venv\Scripts\python.exe -m med_research.cli disease validate --all --strict`

Run: `git diff --check`

Expected: every command exits `0`; strict disease validator reports all seven modules valid.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/web/static/index.html src/med_research/web/static/js/dashboard.js src/med_research/web/static/css/dashboard.css tests/web/test_universal_comparison_dashboard.py
git commit -m "feat: add dashboard condition comparison views"
```
