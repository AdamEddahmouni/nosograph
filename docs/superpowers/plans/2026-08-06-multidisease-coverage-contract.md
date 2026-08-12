# Strict Multi-Disease Coverage Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make every supported disease/module execution explicitly report full, partial, or unsupported coverage and prevent non-SLE analyses from silently using SLE data or defaults.

**Architecture:** Add a small reusable coverage boundary under `med_research.diseases`, then progressively wire the graph, literature, GWAS, enrichment, screening, safety, and CAR-T boundaries to it. Preserve existing public function names and return shapes where possible by adding a `coverage` object, while returning structured blocked results for expected incomplete coverage. Expose the same metadata through CLI/API/dashboard and verify all seven diseases with deterministic fixtures.

**Tech Stack:** Python 3.10+, dataclasses, existing Pydantic v2 models, NetworkX, pytest, FastAPI, vanilla JavaScript dashboard.

## Global Constraints

- Strict policy: missing required curated inputs produce `unsupported`/`blocked`, not zero-filled or successful-looking output.
- Known diseases never inherit SLE terms, signatures, safety profiles, novelty assumptions, or therapy rubrics.
- Do not invent biomedical curation values or copy SLE data into other diseases.
- Preserve existing exported function names/signatures where practical; optional metadata is additive.
- Tests are deterministic and must not require Redis, Celery, LLM credentials, or live APIs.
- Keep research-use-only disclaimers and distinguish computational prioritization from efficacy evidence.
- Do not refactor all pipeline modules into a common class hierarchy.

---

### Task 1: Add the reusable disease/module coverage boundary

**Files:**
- Create: `src/med_research/diseases/coverage.py`
- Modify: `src/med_research/diseases/base.py`
- Test: `tests/test_multidisease_coverage.py`

**Interfaces:**
- Produces `CoverageLevel`, `CoverageStatus`, `ModuleCoverage`, `coverage_for_disease()`, and `module_coverage()`.
- `ModuleCoverage.to_dict() -> dict` is the stable JSON boundary.
- `module_coverage(disease_id: str, module: str, required_inputs: tuple[str, ...], optional_inputs: tuple[str, ...] = ()) -> ModuleCoverage`.

- [x] **Step 1: Write the failing tests**

```python
import pytest

DISEASES = ["sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"]


@pytest.mark.parametrize("disease_id", DISEASES)
def test_core_coverage_reports_all_five_data_files(disease_id):
    from med_research.diseases.coverage import coverage_for_disease

    coverage = coverage_for_disease(disease_id)
    assert coverage.level == "full"
    assert coverage.status == "ready"
    assert set(coverage.curated_inputs) >= {
        "profile",
        "genes",
        "drugs",
        "pathways",
        "relationships",
    }
    assert coverage.missing_inputs == []


def test_missing_required_config_is_blocked(monkeypatch):
    from med_research.diseases.base import Disease
    from med_research.diseases.coverage import module_coverage

    monkeypatch.setattr(Disease, "config", property(lambda self: {}))
    result = module_coverage("ra", "car_t", ("genes", "car_t_scores"))
    assert result.level == "unsupported"
    assert result.status == "blocked"
    assert "car_t_scores" in result.missing_inputs
    assert result.to_dict()["module"] == "car_t"


def test_coverage_does_not_treat_zero_values_as_curated(monkeypatch):
    from med_research.diseases.base import Disease
    from med_research.diseases.coverage import module_coverage

    monkeypatch.setattr(Disease, "get_car_t_scores", lambda self: {})
    result = module_coverage("ibd", "car_t", ("car_t_scores",))
    assert result.status == "blocked"
    assert result.inferred_inputs == []
```

- [x] **Step 2: Run the focused tests and verify they fail**

Run: `python -m pytest tests/test_multidisease_coverage.py -q`
Expected: FAIL because the coverage module and richer result types do not yet exist.

- [x] **Step 3: Implement the coverage model**

Use a dataclass with literal string values so the result is JSON-safe:

```python
from dataclasses import asdict, dataclass, field
from typing import Literal

CoverageLevel = Literal["full", "partial", "unsupported"]
CoverageStatus = Literal["ready", "limited_coverage", "blocked"]


@dataclass(frozen=True)
class ModuleCoverage:
    disease_id: str
    module: str
    level: CoverageLevel
    status: CoverageStatus
    curated_inputs: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)
    inferred_inputs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_runnable(self) -> bool:
        return self.status != "blocked"


def coverage_for_disease(disease_id: str) -> ModuleCoverage:
    disease = Disease(disease_id)
    required_files = ("profile", "genes", "drugs", "pathways", "relationships")
    missing = [name for name in required_files if not (disease.data_dir / f"{name}.json").is_file()]
    if missing:
        return ModuleCoverage(
            disease_id=disease_id,
            module="core",
            level="unsupported",
            status="blocked",
            missing_inputs=missing,
            limitations=[
                "Core disease data is incomplete; run disease scaffolding or refresh before analysis."
            ],
        )
    return ModuleCoverage(
        disease_id=disease_id,
        module="core",
        level="full",
        status="ready",
        curated_inputs=list(required_files),
    )


def module_coverage(disease_id, module, required_inputs, optional_inputs=()):
    disease = Disease(disease_id)
    core = coverage_for_disease(disease_id)
    if not core.is_runnable:
        return ModuleCoverage(**{**core.to_dict(), "module": module})
    missing = []
    curated = []
    for name in required_inputs:
        value = _input_value(disease, name)
        if _is_empty(value):
            missing.append(name)
        else:
            curated.append(name)
    optional_missing = [name for name in optional_inputs if _is_empty(_input_value(disease, name))]
    if missing:
        return ModuleCoverage(
            disease_id=disease_id,
            module=module,
            level="unsupported",
            status="blocked",
            curated_inputs=curated,
            missing_inputs=missing,
            limitations=[f"Required curated inputs are missing: {', '.join(missing)}."],
        )
    if optional_missing:
        return ModuleCoverage(
            disease_id=disease_id,
            module=module,
            level="partial",
            status="limited_coverage",
            curated_inputs=curated,
            missing_inputs=optional_missing,
            warnings=[f"Optional curated inputs are unavailable: {', '.join(optional_missing)}."],
        )
    return ModuleCoverage(
        disease_id=disease_id, module=module, level="full", status="ready", curated_inputs=curated
    )
```

Implement `_input_value()` against the existing `Disease` accessors (`get_symptoms`, `get_car_t_scores`, `get_adverse_event_profile`, config keys, and data loaders), and `_is_empty()` so empty dicts/lists/strings are unavailable while numeric zero remains valid.

- [x] **Step 4: Add `Disease.coverage()` convenience API and keep `validate()` compatible**

Add:

```python
def coverage(self, module="core", required_inputs=(), optional_inputs=()):
    from med_research.diseases.coverage import module_coverage

    return module_coverage(self.disease_id, module, required_inputs, optional_inputs)
```

Do not change existing `validate()` keys in this task.

- [x] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_multidisease_coverage.py -q`
Expected: PASS.

---

### Task 2: Verify and expose the core data/graph contract, including IBD

**Files:**
- Modify: `src/med_research/pipeline/knowledge_graph/builder.py` only if needed to add coverage metadata without breaking the graph return type.
- Modify: `src/med_research/web/models/__init__.py` and `src/med_research/web/routers/system.py`.
- Test: `tests/test_multidisease_coverage.py`

**Interfaces:**
- `GET /api/system/diseases` adds optional `coverage` data to each disease entry.
- Existing `build_graph(disease_id) -> nx.MultiDiGraph` remains unchanged.

- [x] **Step 1: Add graph/data smoke tests**

```python
import json
from pathlib import Path
import pytest


@pytest.mark.parametrize("disease_id", DISEASES)
def test_all_disease_graphs_build_and_relationships_reference_nodes(disease_id):
    from med_research.diseases.base import Disease
    from med_research.pipeline.knowledge_graph.builder import build_graph

    disease = Disease(disease_id)
    genes = {x["id"] for x in disease.load_genes()["genes"]}
    drugs = {x["id"] for x in disease.load_drugs()["drugs"]}
    pathways = {x["id"] for x in disease.load_pathways()["pathways"]}
    graph = build_graph(disease_id)
    assert graph.number_of_nodes() > 0
    assert disease.load_relationships()["relationships"]
    valid = genes | drugs | pathways | {disease.profile.kg_node_id, disease.profile.name}
    assert all(
        r["source"] in valid and r["target"] in valid
        for r in disease.load_relationships()["relationships"]
    )
```

- [x] **Step 2: Run the new graph tests and fix only actual data/path defects**

Run: `python -m pytest tests/test_multidisease_coverage.py -k graph -q`
Expected: PASS for all seven diseases, including IBD. If a relationship points to a valid graph alias not represented in the raw entity IDs, update the validation set to use the builder’s disease-node convention rather than weakening the check.

- [x] **Step 3: Add coverage fields to disease API models and registry output**

Extend `DiseaseInfo` with:

```python
coverage: dict[str, object] = Field(default_factory=dict)
```

In `disease_registry()`, compute `coverage_for_disease(disease_id).to_dict()` and add module readiness summaries for `kg`, `literature`, `gwas`, `enrichment`, `screening`, `safety`, and `car_t`.

- [x] **Step 4: Run API-focused tests**

Run: `python -m pytest tests/test_multidisease_reliability.py tests/test_web_api.py -q`
Expected: PASS.

---

### Task 3: Remove SLE fallback behavior from literature, GWAS, and enrichment

**Files:**
- Modify: `src/med_research/pipeline/literature_mining/miner.py`
- Modify: `src/med_research/pipeline/bioinformatics/gwas.py`
- Modify: `src/med_research/pipeline/bioinformatics/enrichment.py`
- Modify: `src/med_research/pipeline/literature_mining/crossref.py` only if candidate loading must be disease-scoped.
- Test: `tests/test_multidisease_coverage.py`
- Test: existing `tests/test_literature_mining.py`, `tests/test_bioinformatics_gwas.py`, and enrichment tests as needed.

**Interfaces:**
- Existing helper functions remain callable.
- `mine_literature(..., disease_id=...)`, `disease_search_terms()`, and disease gene list helpers return a structured blocked result only at top-level execution boundaries; lower-level query helpers may continue returning lists for compatibility.

- [x] **Step 1: Add tests that assert active disease terms and strict blocking**

```python
def test_literature_queries_are_not_sle_for_ra(monkeypatch):
    from med_research.pipeline.literature_mining import miner

    queries = miner._disease_queries("ra")
    assert queries
    assert all("lupus" not in q.lower() and "sle" not in q.lower() for q in queries)
    assert any("rheumatoid" in q.lower() or "ra[" in q.lower() for q in queries)


def test_gwas_terms_are_not_sle_for_ibd():
    from med_research.pipeline.bioinformatics.gwas import disease_search_terms

    terms = disease_search_terms("ibd")
    assert terms
    assert any("bowel" in term.lower() or "crohn" in term.lower() for term in terms)
    assert all(term.lower() not in {"sle", "lupus"} for term in terms)


def test_missing_literature_config_is_blocked(monkeypatch):
    from med_research.diseases.base import Disease
    from med_research.pipeline.literature_mining.miner import _disease_queries

    monkeypatch.setattr(Disease, "config", property(lambda self: {}))
    assert _disease_queries("ra") == []
```

- [x] **Step 2: Run focused tests and verify the new strict test fails**

Run: `python -m pytest tests/test_multidisease_coverage.py -k 'literature or gwas or enrichment' -q`
Expected: the missing-config test fails until fallbacks are removed.

- [x] **Step 3: Make known-disease query selection strict**

In `_disease_queries()` and `disease_search_terms()`:

- Instantiate `Disease(disease_id)` first.
- For known diseases, use only config/profile terms.
- If no usable terms exist, return `[]` (or a top-level blocked result) rather than `DEFAULT_QUERIES`/`SLE_SEARCH_TERMS`.
- Keep legacy constants only for explicit unknown-ID compatibility paths, and do not use them for the seven discovered diseases.
- Build targeted candidate queries from `Disease(disease_id).profile.name` when the configured query does not contain a usable disease clause.

- [x] **Step 4: Add disease/module coverage to top-level result dictionaries**

At the top-level literature/GWAS/enrichment orchestration boundaries, return:

```python
{
    "coverage": module_coverage(...).to_dict(),
    "status": "blocked",
    "warnings": ["No disease-specific ... configuration is available."],
    "results": [],
}
```

Do not return a normal empty analysis with a success message when blocked. Preserve lower-level return values used by existing unit tests.

- [x] **Step 5: Make enrichment wording disease-neutral and use active pathway keywords**

Rename local variables/docstrings from `lupus_genes` to `disease_genes`, retain `get_lupus_gene_list` as a compatibility wrapper, and ensure `cross_reference_with_kg_pathways()` exclusively uses `Disease(disease_id).get_pathway_keywords()` for fallback keyword matching.

- [x] **Step 6: Run focused existing and new tests**

Run: `python -m pytest tests/test_multidisease_coverage.py tests/test_literature_mining.py tests/test_bioinformatics_gwas.py tests/test_bioinformatics_enrichment.py -q`
Expected: PASS.

---

### Task 4: Make screening, safety, and CAR-T strict and disease-neutral

**Files:**
- Modify: `src/med_research/pipeline/virtual_screening/screening.py`
- Modify: `src/med_research/pipeline/adverse_events/profiler.py`
- Modify: `src/med_research/pipeline/car_t_predictor/predictor.py`
- Modify: disease config accessors in `src/med_research/diseases/base.py`.
- Test: `tests/test_multidisease_coverage.py`
- Test: existing screening, safety, and CAR-T tests.

**Interfaces:**
- Existing scoring functions retain their signatures.
- Top-level `screen_compounds()`, `score_all_drugs()`, and `compute_all_scores()` add `coverage` and `status` fields to result containers where their existing return shape is a dict/list wrapper; blocked execution returns an empty result plus explicit metadata.
- `Disease.get_disease_risk_config()` is the new neutral accessor; `get_drug_induced_lupus_risk()` remains as a compatibility alias.

- [x] **Step 1: Add strict tests**

```python
def test_carscores_block_when_missing(monkeypatch):
    from med_research.diseases.base import Disease
    from med_research.pipeline.car_t_predictor import predictor

    monkeypatch.setattr(Disease, "get_car_t_scores", lambda self: {})
    result = predictor.compute_all_scores(disease_id="ra")
    assert result == []
    assert predictor.last_coverage.to_dict()["status"] == "blocked"


def test_screening_novelty_is_disease_scoped():
    from med_research.pipeline.virtual_screening.screening import compute_novelty_score

    compound = {"category": "Approved for rheumatoid arthritis"}
    assert compute_novelty_score(compound, {"id": "TNF"}) > 2.0


def test_safety_uses_neutral_disease_risk_accessor(monkeypatch):
    from med_research.diseases.base import Disease

    assert hasattr(Disease, "get_disease_risk_config")
    monkeypatch.setattr(Disease, "get_disease_risk_config", lambda self: {"high_risk": ["fixture"]})
```

- [x] **Step 2: Run focused tests and inspect failures**

Run: `python -m pytest tests/test_multidisease_coverage.py -k 'carscores or screening or safety' -q`
Expected: new strict tests fail before implementation.

- [x] **Step 3: Add neutral disease-risk accessor**

In `Disease`:

```python
def get_disease_risk_config(self) -> dict:
    return self.config.get("DISEASE_SPECIFIC_RISK") or self.config.get(
        "DRUG_INDUCED_LUPUS_RISK", {}
    )


def get_drug_induced_lupus_risk(self) -> dict:
    return self.get_disease_risk_config()
```

Do not rename all existing config constants in this pass; the accessor removes the semantic dependency while preserving compatibility.

- [x] **Step 4: Block CAR-T when curated scores are empty**

At the start of `compute_all_scores()`, obtain `coverage = module_coverage(disease_id, "car_t", ("genes", "car_t_scores"))`. If blocked, store the coverage on a module-level `last_coverage` object for backward-compatible list callers, log a warning, and return `[]`. For successful output, include `coverage` in the serialized file/report wrapper and keep each row’s `disease_id`.

- [x] **Step 5: Remove SLE-specific scoring literals from screening**

Update similarity/novelty scoring to use active disease context. Pass `disease_id` through the scoring helpers by adding optional parameters only where needed. Use `Disease(disease_id).profile.name`, configured approval/category fields, and active disease evidence. Never test for literal `"sle"`/`"lupus"` to decide whether a compound is already used in the active disease.

- [x] **Step 6: Make safety use active disease data and strict coverage**

Replace `LUPUS_SYMPTOMS` use in the scoring path with `Disease(disease_id).get_symptom_overlap_terms()`. Read disease risk through `get_disease_risk_config()`. Before scoring all drugs, require non-empty active symptoms and risk/profile support; if unavailable, return `[]` with a blocked coverage result rather than default profiles/scores. Preserve the existing SLE data path when SLE is fully configured.

- [x] **Step 7: Run focused existing and new tests**

Run: `python -m pytest tests/test_multidisease_coverage.py tests/test_multidisease_reliability.py tests/test_docking.py tests/test_evidence_quality.py -q`
Expected: PASS.

---

### Task 5: Wire coverage through web services, API models, and dashboard

**Files:**
- Modify: `src/med_research/web/models/shared.py`
- Modify: `src/med_research/web/models/__init__.py` if exports are needed.
- Modify: `src/med_research/web/services/shared_services.py`
- Modify: `src/med_research/web/services/bioinformatics_service.py`
- Modify: `src/med_research/web/services/adverse_events_service.py`
- Modify: `src/med_research/web/static/js/dashboard.js`
- Modify: `src/med_research/web/static/css/dashboard.css`
- Modify: `src/med_research/web/static/index.html`
- Test: `tests/test_multidisease_coverage.py`
- Test: `tests/test_evidence_workspace_dashboard.py` or a new dashboard coverage test.

**Interfaces:**
- Add `coverage: dict[str, Any] = Field(default_factory=dict)` to affected response models.
- Service results must preserve the coverage object returned by pipeline boundaries.
- Dashboard adds a reusable `renderCoverageBadge(coverage)` helper and renders blocked/limited states without interpreting them as success.

- [x] **Step 1: Add API/service coverage tests**

```python
def test_screening_response_model_accepts_coverage():
    from med_research.web.models.shared import ScreeningResponse

    response = ScreeningResponse(
        targets=[],
        compounds_screened=0,
        total_pairings=0,
        tier1_count=0,
        tier2_count=0,
        vina_available=False,
        rdkit_available=False,
        coverage={"level": "unsupported", "status": "blocked"},
    )
    assert response.coverage["status"] == "blocked"


def test_dashboard_has_coverage_rendering():
    from pathlib import Path

    root = Path(__file__).parents[1] / "src/med_research/web/static"
    script = (root / "js/dashboard.js").read_text(encoding="utf-8")
    assert "renderCoverageBadge" in script
    assert "limited_coverage" in script
    assert "Unsupported for this disease" in script
```

- [x] **Step 2: Run the tests and verify the model/UI assertions fail**

Run: `python -m pytest tests/test_multidisease_coverage.py -k 'response or dashboard' -q`
Expected: FAIL until model fields and rendering helper exist.

- [x] **Step 3: Add optional coverage fields to response models**

Add the field to `LiteratureResponse`, `ScreeningResponse`, `TrialsResponse` where appropriate, and create a small shared `CoveragePayload` type only if it does not make existing response validation more complicated. Keep defaults empty for old callers.

- [x] **Step 4: Preserve coverage in service responses**

In each service, if a pipeline result contains `coverage`, copy it into the response. If a strict blocked result is returned, do not convert it to `success`; return its status, warning, and coverage metadata.

- [x] **Step 5: Add dashboard rendering**

Implement:

```javascript
function renderCoverageBadge(coverage) {
    const level = coverage?.level || 'unknown';
    const status = coverage?.status || '';
    const label = level === 'full' ? 'Full coverage'
        : level === 'partial' ? 'Limited coverage'
        : level === 'unsupported' ? 'Unsupported for this disease'
        : 'Coverage unknown';
    const cls = level === 'full' ? 'coverage-full'
        : level === 'partial' ? 'coverage-partial' : 'coverage-unsupported';
    const warnings = [...(coverage?.missing_inputs || []), ...(coverage?.warnings || [])];
    return `<span class="coverage-badge ${cls}" title="${escapeHtml(warnings.join('; '))}">${label}</span>`;
}
```

Use a distinct blocked renderer that displays limitations and remediation, and never shows an empty ranking table with a green success class. Add CSS for full/partial/unsupported badges and blocked result panels.

- [x] **Step 6: Run dashboard/API tests**

Run: `python -m pytest tests/test_multidisease_coverage.py tests/test_evidence_workspace_dashboard.py tests/test_web_api.py -q`
Expected: PASS.

---

### Task 6: Add a reusable coverage/provenance report and CLI command

**Files:**
- Create: `src/med_research/diseases/coverage_report.py`
- Modify: `src/med_research/cli.py`
- Modify: `README.md`
- Modify: `docs/api-reference.md`
- Test: `tests/test_multidisease_coverage.py`

**Interfaces:**
- `build_coverage_report(disease_id: str, modules: tuple[str, ...] = DEFAULT_MODULES) -> dict`.
- CLI command: `python -m med_research.cli disease coverage <id> [--json PATH]`.
- Report includes `disease_id`, `name`, `entity_counts`, `core`, `modules`, `curated_inputs`, `missing_inputs`, `inferred_inputs`, `warnings`, `limitations`, and a stable `fingerprint`.

- [x] **Step 1: Add report tests**

```python
def test_coverage_report_is_stable_and_complete():
    from med_research.diseases.coverage_report import build_coverage_report

    report = build_coverage_report("ibd")
    assert report["disease_id"] == "ibd"
    assert report["entity_counts"]["relationships"] > 0
    assert set(report["modules"]) >= {
        "literature",
        "gwas",
        "enrichment",
        "screening",
        "safety",
        "car_t",
    }
    assert report["fingerprint"] == build_coverage_report("ibd")["fingerprint"]
```

- [x] **Step 2: Implement deterministic report generation**

Hash only normalized disease ID, entity counts, file presence, module coverage dictionaries, and package version. Exclude timestamps and generated run IDs. Use `hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()`.

- [x] **Step 3: Wire CLI output and JSON export**

Add the subcommand under the existing `disease` parser. Human output must print one row per module with `FULL`, `LIMITED`, or `UNSUPPORTED`, followed by missing inputs and limitations. `--json` writes the complete report.

- [x] **Step 4: Update docs**

Document the command, strict policy, example output, and the distinction between coverage and evidence provenance in `README.md` and `docs/api-reference.md`.

- [x] **Step 5: Run CLI/report tests**

Run: `python -m pytest tests/test_multidisease_coverage.py tests/test_disease_scaffold.py -q`
Run: `python -m med_research.cli disease coverage ibd --json /tmp/ibd-coverage.json`
Expected: command exits 0, report contains IBD relationships and module statuses.

---

### Task 7: Review, regression validation, and documentation consistency

**Files:**
- Modify only files identified by review/test failures.
- Test: all affected test files and full suite.

- [x] **Step 1: Run code review**

Ask the code reviewer to check strictness, accidental SLE fallback paths, compatibility of exported functions, API serialization, and dashboard blocked-state rendering.

- [x] **Step 2: Run targeted checks in parallel**

Run:

```bash
python -m pytest tests/test_multidisease_coverage.py tests/test_multidisease_reliability.py -q --tb=short
python -m pytest tests/test_literature_mining.py tests/test_bioinformatics_gwas.py tests/test_bioinformatics_enrichment.py tests/test_docking.py -q --tb=short
python -m pytest tests/test_evidence_workspace_dashboard.py tests/test_web_api.py -q --tb=short
python scripts/check_imports.py
python -m compileall -q src/med_research
```

Expected: all commands exit 0.

- [x] **Step 3: Fix review findings without broadening scope**

For each finding, preserve the strict contract. Do not restore silent fallback behavior to make tests pass; update fixtures or explicit compatibility paths instead.

- [x] **Step 4: Run the full offline suite**

Run: `make test-offline`
Expected: all non-slow tests pass.

- [x] **Step 5: Run lint and diff checks**

Run: `make lint && git diff --check`
Expected: exit 0.

- [x] **Step 6: Verify all seven coverage reports**

Run:

```bash
for disease in sle ra ms ss ssc t1d ibd; do
  python -m med_research.cli disease coverage "$disease" >/dev/null || exit 1
done
```

Expected: all seven commands exit 0 and print explicit module statuses.

---

## Plan self-review

- **Spec coverage:** Shared contract is Task 1; IBD/graph validation is Task 2; SLE fallback removal is Task 3 and Task 4; visible output is Task 5; coverage/provenance report is Task 6; smoke/regression tests are Tasks 1–7.
- **Placeholder scan:** No TODO/TBD steps are used. Each task includes concrete files, interfaces, test code, commands, and expected outcomes.
- **Type consistency:** `ModuleCoverage.to_dict()` is the stable metadata boundary used by pipeline, API, dashboard, and report tasks. `module_coverage()` returns `ModuleCoverage` in every path. Existing list-returning functions are kept compatible while top-level wrappers expose strict metadata.
- **Scope check:** The plan intentionally avoids the broad common pipeline-interface refactor and new biomedical curation, as required by the approved design.
