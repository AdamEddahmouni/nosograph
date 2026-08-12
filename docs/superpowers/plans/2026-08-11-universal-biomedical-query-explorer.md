# Universal Biomedical Query and Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose versioned `/api/v1` condition search, detail, hierarchy, claim, and snapshot endpoints plus a generic dashboard condition explorer that renders any imported condition without a hand-authored disease module.

**Architecture:** Add `med_research.web.models.universal`, `med_research.web.services.universal_service`, and `med_research.web.routers.universal` on top of the Stage 1 repository. The dashboard gains a research-language condition explorer panel that consumes the new API. Legacy `/api/*` routes remain unchanged.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, vanilla HTML/CSS/JavaScript, pytest, Ruff, mypy.

**Depends on:** [Canonical Core](2026-08-11-universal-biomedical-canonical-core.md), [Ontology Ingestion](2026-08-11-universal-biomedical-ontology-ingestion.md), and [Legacy Migration](2026-08-11-universal-biomedical-legacy-migration.md).

## Global Constraints

- Preserve all seven disease modules and existing `/api/*` contracts.
- New routes live under `/api/v1` only; do not mutate legacy route shapes.
- Use `condition similarity`, `candidate relationship`, `research hypothesis`, `supporting evidence`, and `contradictory evidence` in user-facing copy.
- Do not generate diagnosis, treatment recommendations, or probability-of-disease claims.
- Every response includes a research-only disclaimer field.
- Pagination and traversal limits are enforced server-side (`limit` 1–200, hierarchy depth 0–3).
- Absent imported data renders as `No data imported for this section`, never as negative evidence.
- Preserve unrelated working-tree changes; stage only files named by the active task.

---

### Task 1: Universal API Models and Disclaimer Contract

**Files:**
- Create: `src/med_research/web/models/universal.py`
- Test: `tests/web/test_universal_models.py`

**Interfaces:**
- Consumes: Stage 1 `EntityType`, `Predicate`, `EvidenceDirection`, `RunStatus`.
- Produces: response models for search, condition summary, hierarchy, claims, snapshots, and shared `ResearchDisclaimer`.

- [ ] **Step 1: Write failing model tests**

```python
from med_research.web.models.universal import (
    ClaimEvidenceView,
    ConditionSummary,
    ResearchDisclaimer,
)


def test_research_disclaimer_is_required_on_condition_summary() -> None:
    payload = ConditionSummary.model_validate(
        {
            "curie": "MONDO:0007915",
            "label": "systemic lupus erythematosus",
            "entity_type": "condition",
            "snapshots": [],
            "disclaimer": ResearchDisclaimer().model_dump(),
        }
    )
    assert "research" in payload.disclaimer.text.lower()


def test_claim_evidence_keeps_directions_separate() -> None:
    evidence = ClaimEvidenceView.model_validate(
        {
            "direction": "supporting",
            "snapshot_id": "00000000-0000-0000-0000-000000000001",
            "source_record_id": "row-1",
        }
    )
    assert evidence.direction == "supporting"
```

- [ ] **Step 2: Run tests and verify models are missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/web/test_universal_models.py -q`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement models**

Define:

- `ResearchDisclaimer` — fixed research-only text plus schema version.
- `EntitySummary`, `ConditionSummary`, `HierarchyNode`, `ClaimView`, `ClaimEvidenceView`.
- `SnapshotSummary`, `ImportReportView`, `PagedResponse[T]`.
- Literal enums mirroring repository enums for stable OpenAPI output.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/web/test_universal_models.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/web/models/universal.py tests/web/test_universal_models.py
git commit -m "feat: add universal biomedical api models"
```

### Task 2: Universal Service Layer

**Files:**
- Create: `src/med_research/web/services/universal_service.py`
- Create: `src/med_research/web/dependencies_biomed.py`
- Test: `tests/web/test_universal_service.py`

**Interfaces:**
- Consumes: `BiomedicalRepository`, `BIOMEDICAL_DB_PATH`.
- Produces: `search_conditions`, `get_condition`, `get_hierarchy`, `list_condition_claims`, `list_snapshots`, `get_import_report`.

- [ ] **Step 1: Write failing service tests**

Use an initialized repository fixture with imported Mondo and legacy snapshots from prior stage tests.

```python
def test_get_condition_returns_mappings_and_active_snapshots(biomed_repository) -> None:
    summary = get_condition(biomed_repository, "MONDO:0007915")
    assert summary.curie == "MONDO:0007915"
    assert summary.disclaimer.text
    assert summary.snapshots


def test_list_claims_supports_predicate_filter(biomed_repository) -> None:
    claims = list_condition_claims(
        biomed_repository, "MONDO:0007915", predicate=Predicate.HAS_PHENOTYPE
    )
    assert all(item.claim.predicate == Predicate.HAS_PHENOTYPE for item in claims)
```

- [ ] **Step 2: Run tests and verify service is missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/web/test_universal_service.py -q`

Expected: import failure.

- [ ] **Step 3: Implement service**

Add a FastAPI dependency that opens `BiomedicalRepository(BIOMEDICAL_DB_PATH)` per request or uses an app-lifespan singleton. Map repository views to API models. Enforce pagination bounds and hierarchy depth. Return `None` for unknown CURIEs so routers can emit HTTP 404.

Distinguish ontology presence from curated-module readiness using snapshot metadata and optional legacy coverage helpers from Stage 3.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/web/test_universal_service.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/web/services/universal_service.py src/med_research/web/dependencies_biomed.py tests/web/test_universal_service.py
git commit -m "feat: add universal biomedical query service"
```

### Task 3: FastAPI `/api/v1` Router

**Files:**
- Create: `src/med_research/web/routers/universal.py`
- Modify: `src/med_research/web/routers/__init__.py`
- Modify: `src/med_research/web/config.py`
- Test: `tests/web/test_universal_api.py`

**Interfaces:**
- Produces versioned routes:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/conditions/search` | Search conditions by label/synonym |
| GET | `/api/v1/conditions/{curie}` | Condition summary |
| GET | `/api/v1/conditions/{curie}/hierarchy` | Parents/children with depth limit |
| GET | `/api/v1/conditions/{curie}/claims` | Claims with predicate and evidence filters |
| GET | `/api/v1/snapshots` | List resource snapshots |
| GET | `/api/v1/snapshots/{snapshot_id}/report` | Import report metadata |

- [ ] **Step 1: Write failing API tests**

```python
def test_search_conditions_returns_disclaimer(client, seeded_biomed_db) -> None:
    response = client.get("/api/v1/conditions/search", params={"q": "lupus", "limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["disclaimer"]["text"]
    assert body["items"]


def test_unknown_condition_returns_404(client, seeded_biomed_db) -> None:
    response = client.get("/api/v1/conditions/MONDO:9999999")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests and verify routes are missing**

Run: `.\.venv\Scripts\python.exe -m pytest tests/web/test_universal_api.py -q`

Expected: `404` for all `/api/v1` paths or collection failure.

- [ ] **Step 3: Implement router**

Register `universal_router` in `routers/__init__.py`. Add OpenAPI tag `Universal Biomedical` in `config.API_TAGS`. Normalize path CURIEs with `normalize_curie`. Reject `limit > 200` and `depth > 3` with HTTP 422.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/web/test_universal_api.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/web/routers/universal.py src/med_research/web/routers/__init__.py src/med_research/web/config.py tests/web/test_universal_api.py
git commit -m "feat: add universal biomedical api routes"
```

### Task 4: Dashboard Condition Explorer UI

**Files:**
- Modify: `src/med_research/web/static/index.html`
- Modify: `src/med_research/web/static/js/dashboard.js`
- Modify: `src/med_research/web/static/css/dashboard.css`
- Test: `tests/web/test_universal_dashboard.py`

**Interfaces:**
- Consumes: `/api/v1/conditions/*` endpoints.
- Produces: search box, condition detail panel, hierarchy list, claims table with supporting/contradictory chips, snapshot provenance panel, and coverage/readiness badges.

- [ ] **Step 1: Write failing dashboard contract tests**

Assert the static bundle contains:

- A `condition-explorer` section anchor in `index.html`.
- Functions `searchConditions`, `renderConditionExplorer`, and `renderClaimEvidence` in `dashboard.js`.
- Research-only disclaimer rendering in the explorer panel.
- Escaped rendering for labels, definitions, and citation URLs.

- [ ] **Step 2: Run tests and verify assertions fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/web/test_universal_dashboard.py -q`

Expected: missing section or function names.

- [ ] **Step 3: Implement explorer UI**

Add a nav link and panel beside existing modules. Fetch search results debounced from input. Render:

- Preferred label, definition, synonyms, and mappings.
- Parent/child hierarchy with depth control.
- Claims grouped by predicate with separate supporting and contradictory evidence chips.
- Active snapshot list and `No data imported for this section` placeholders.
- Keyboard focus order and `aria-busy` during fetch.

Reuse existing `escapeHtml` helpers; do not introduce a frontend framework.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/web/test_universal_dashboard.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/med_research/web/static/index.html src/med_research/web/static/js/dashboard.js src/med_research/web/static/css/dashboard.css tests/web/test_universal_dashboard.py
git commit -m "feat: add universal condition explorer dashboard"
```

### Task 5: API Reference, Accessibility, and Research-Language Tests

**Files:**
- Modify: `docs/api-reference.md`
- Test: `tests/web/test_universal_language.py`

**Interfaces:**
- Produces documented request/response examples for every `/api/v1` route and explicit research-language assertions.

- [ ] **Step 1: Write failing language tests**

```python
FORBIDDEN_PHRASES = ["diagnosis", "recommended treatment", "you have", "probability of disease"]


def test_api_responses_avoid_clinical_diagnostic_language(client, seeded_biomed_db) -> None:
    response = client.get("/api/v1/conditions/MONDO:0007915")
    text = response.text.lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text
```

- [ ] **Step 2: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/web/test_universal_language.py -q`

Expected: pass once routes exist; adjust only if current copy violates the contract.

- [ ] **Step 3: Document API**

Add `/api/v1` section to `docs/api-reference.md` with pagination defaults, traversal limits, disclaimer field, and examples for search, detail, claims, and snapshots.

- [ ] **Step 4: Run the Stage 4 gate**

Run: `.\.venv\Scripts\python.exe -m pytest tests/web/test_universal_models.py tests/web/test_universal_service.py tests/web/test_universal_api.py tests/web/test_universal_dashboard.py tests/web/test_universal_language.py -q`

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_web_api.py -q`

Run: `.\.venv\Scripts\python.exe -m ruff check src/med_research/web/models/universal.py src/med_research/web/services/universal_service.py src/med_research/web/routers/universal.py tests/web/test_universal_*.py`

Run: `.\.venv\Scripts\python.exe -m mypy src/med_research/web/models/universal.py src/med_research/web/services/universal_service.py src/med_research/web/routers/universal.py`

Run: `git diff --check`

Expected: every command exits `0`; existing web API tests remain green.

- [ ] **Step 5: Commit**

```powershell
git add docs/api-reference.md tests/web/test_universal_language.py
git commit -m "docs: document universal biomedical api and language guardrails"
```
